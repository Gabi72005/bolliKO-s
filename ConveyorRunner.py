from robodk import robolink, robomath
import time
import threading

# ---------- Flags y variables globales ----------
RDK = None
parada_activada = False
procesando = False
sensor_activo = False
rechazando = False

spawn_lock = threading.Lock()
pos = 0.0
interval = 0.3
speed = 200
tray_queue = []

# ---------- Lock de estación ----------
def adquirir_lock(nombre_lock, intentos=20, espera=0.1):
    for _ in range(intentos):
        estado = str(RDK.getParam(nombre_lock) or "0").lower()
        if estado in ["", "0", "false", "none"]:
            RDK.setParam(nombre_lock, "1")
            return True
        time.sleep(espera)
    return False

def liberar_lock(nombre_lock):
    RDK.setParam(nombre_lock, "0")

def usar_lock(nombre_lock):
    def decorador(func):
        def wrapper(*args, **kwargs):
            if adquirir_lock(nombre_lock):
                try:
                    return func(*args, **kwargs)
                finally:
                    liberar_lock(nombre_lock)
        return wrapper
    return decorador

# ---------- Inicialización ----------
def inicializar_entorno():
    global RDK, ref_tray, conveyor_frame, conveyor, programa, robot, sensor, sensor_final, tray_queue, SENSOR_IO, SENSOR_FINAL_IO

    RDK = robolink.Robolink()
    RDK.setSelection([])

    SENSOR_IO = "sensor_robot_uno"
    SENSOR_FINAL_IO = "sensor_final_uno"

    robot = RDK.Item('UR16e', robolink.ITEM_TYPE_ROBOT)
    programa = RDK.Item('Relleno', robolink.ITEM_TYPE_PROGRAM)
    sensor = RDK.Item(SENSOR_IO, robolink.ITEM_TYPE_OBJECT)
    sensor_final = RDK.Item(SENSOR_FINAL_IO, robolink.ITEM_TYPE_OBJECT)

    ref_tray = next((x for x in RDK.ItemList(robolink.ITEM_TYPE_OBJECT) if 'tray' in x.Name().lower() and 'ref' in x.Name().lower()), None)
    if not ref_tray:
        RDK.ShowMessage('No reference tray found.')
        quit()
    ref_tray.setVisible(False)
    ref_tray.Parent().setParam('Tree', 'Collapse')

    conveyor = next((x for x in RDK.ItemList(robolink.ITEM_TYPE_ROBOT_AXES) if len(x.Joints().tolist()) == 1 and 'conveyor' in x.Name().lower()), None)
    if not conveyor:
        RDK.ShowMessage('No conveyor found.')
        quit()

    conveyor_frame = RDK.Item('tray_conveyor_frame', robolink.ITEM_TYPE_FRAME)
    if not conveyor_frame.Valid():
        RDK.ShowMessage('No se encontró el frame "tray_conveyor_frame".')
        quit()

    for item in [robot, programa, conveyor, sensor, sensor_final, conveyor_frame]:
        if not item.Valid():
            raise Exception('Elemento no encontrado en el entorno')

    tray_queue = [b for b in conveyor_frame.Childs() if b.Type() == robolink.ITEM_TYPE_OBJECT and b.Valid(True)]

# ---------- Funciones auxiliares ----------
def sensor_activo_con_tray_cercano():
    if str(RDK.getParam(SENSOR_IO)) != "1.0":
        return None
    trays = [b for b in conveyor_frame.Childs() if b.Type() == robolink.ITEM_TYPE_OBJECT and b.Valid(True) and b.Name().lower().startswith('tray')]
    if not trays:
        return None
    sensor_pose = sensor.Pose().Pos()
    return min(trays, key=lambda c: sum((sensor_pose[i] - c.Pose().Pos()[i]) ** 2 for i in range(3)) ** 0.5)

def distancia_entre_ultimas():
    if not tray_queue:
        return 999
    last_tray = tray_queue[-1]
    return abs(last_tray.PoseAbs().Pos()[0] - ref_tray.PoseAbs().Pos()[0])

def es_pedido_unitario(nombre, sabor):
    clave_seguro = f"seguro_pedido_{nombre}_{sabor}"
    try:
        valor = float(RDK.getParam(clave_seguro) or 0)
        return valor <= 1
    except:
        return False 

def eliminar_objetivo_si_sensor_activo():
    if str(RDK.getParam(SENSOR_FINAL_IO)) != "1.0":
        return
    objetivos = [o for o in conveyor_frame.Childs() if o.Type() == robolink.ITEM_TYPE_OBJECT and o.Valid(True) and o.Name().lower().startswith('objetivo')]
    if not objetivos:
        return
    sensor_pose = sensor_final.Pose().Pos()
    objetivo_cercano = min(objetivos, key=lambda c: sum((sensor_pose[i] - c.Pose().Pos()[i]) ** 2 for i in range(3)) ** 0.5)
    nombre_obj = objetivo_cercano.Name().lower()
    if 'pedido' in nombre_obj:
        partes = nombre_obj.replace('objetivo_', '').split('_')
        if len(partes) >= 2:
            nombre = '_'.join(partes[:-1])
            sabor = partes[-1]
            param_rellenados = f"rellenados_{nombre}_{sabor}"
            valor_actual = float(RDK.getParam(param_rellenados) or 0)
            RDK.setParam(param_rellenados, valor_actual + 1)
    RDK.Delete(objetivo_cercano)
    valor_empaquetados = float(RDK.getParam('empaquetados_normal') or 0)
    RDK.setParam('empaquetados_normal', valor_empaquetados + 1)

def ejecutar_relleno(tray):
    global procesando
    try:
        nombre = tray.Name().lower().replace("tray_", "objetivo_") if "pedido" in tray.Name().lower() else "Objetivo"
        tray.setName(nombre)
        programa.RunProgram()
        while programa.Busy():
            time.sleep(0.1)
        pose = tray.Pose()
        pose.setPos([*pose.Pos()[:2], -1.5])
        tray.setPose(pose)
        procesando = True
    except:
        pass

def spawn_tray():
    if adquirir_lock("lock_spawn_tray"):
        try:
            return _spawn_tray()
        finally:
            liberar_lock("lock_spawn_tray")
    return None

def _spawn_tray():
    RDK.Render(False)
    selection = RDK.Selection()
    parametros = RDK.getParams()
    pedido_param = None
    for clave, valor in parametros:
        if clave.startswith("pedido_"):
            try:
                if float(valor) > 0:
                    pedido_param = clave
                    break
            except:
                RDK.setParam(clave, None)

    ref_caja = ref_tray
    nombre = sabor = None

    if pedido_param:
        sabor = pedido_param.split('_')[-1]
        nombre = '_'.join(pedido_param.split('_')[1:-1])
        ref_nombre = f"referencetray{sabor.lower().replace(' ', '').replace('_', '')}"
        ref_encontrada = next((item for item in RDK.ItemList(robolink.ITEM_TYPE_OBJECT) if item.Name().lower().replace(" ", "").replace("_", "") == ref_nombre), None)
        if ref_encontrada and ref_encontrada.Valid():
            ref_caja = ref_encontrada
        seguro_param = f"seguro_pedido_{nombre}_{sabor}"
        if RDK.getParam(seguro_param) is None:
            RDK.setParam(seguro_param, float(RDK.getParam(pedido_param) or 0))
        valor_actual = float(RDK.getParam(pedido_param) or 0) - 1
        RDK.setParam(pedido_param, valor_actual if valor_actual > 0 else None)

    ref_caja.Copy(copy_children=False)
    time.sleep(0.05)
    new_tray = ref_caja.Parent().Paste()
    RDK.setSelection(selection)

    if not new_tray.Valid():
        return None

    new_tray.setVisible(False)
    new_tray.setName(f'Tray_pedido_{nombre}_{sabor}' if nombre and sabor else 'Tray')
    new_tray.setParentStatic(conveyor_frame)
    new_tray.setVisible(True)
    RDK.Render(True)
    return new_tray

def rechazar_bollos():
    if str(RDK.getParam('rechazar')).lower() != 'true':
        return

    base_lift = RDK.Item('OnRobot Lift100 Base', robolink.ITEM_TYPE_FRAME)
    lift = RDK.Item('OnRobot Lift100', robolink.ITEM_TYPE_ROBOT_AXES)

    if not base_lift.Valid() or not lift.Valid():
        return

    trays = [b for b in conveyor_frame.Childs() if b.Type() == robolink.ITEM_TYPE_OBJECT and b.Valid(True) and b.Name().lower().startswith('tray')]
    if not trays:
        return

    base_pos = base_lift.PoseAbs().Pos()
    tray_cercana = min(trays, key=lambda c: sum((base_pos[i] - c.PoseAbs().Pos()[i]) ** 2 for i in range(3)) ** 0.5)

    nombre_tray = tray_cercana.Name().lower()
    if 'pedido' in nombre_tray:
        partes = nombre_tray.replace('tray_pedido_', '').split('_')
        if len(partes) >= 2:
            nombre = '_'.join(partes[:-1])
            sabor = partes[-1]
            if es_pedido_unitario(nombre, sabor):
                RDK.setParam('rechazar', 'false')
                return
            variable_seguro = f"seguro_pedido_{nombre}_{sabor}"
            valor_seguro = float(RDK.getParam(variable_seguro) or 0)
            RDK.setParam(variable_seguro, valor_seguro - 1 if valor_seguro > 1 else None)

    pos_lift = 0.0
    velocidad = 500.0
    intervalo = 0.05
    while pos_lift < 500.0:
        pos_lift += velocidad * intervalo
        lift.setJoints([min(pos_lift, 500)])
        time.sleep(intervalo)

    RDK.Delete(tray_cercana)

    while pos_lift > 0.0:
        pos_lift -= velocidad * intervalo
        lift.setJoints([max(pos_lift, 0)])
        time.sleep(intervalo)

    RDK.setParam('rechazar', 'false')

# ---------- Hilos ----------
def ciclo_principal():
    global procesando, sensor_activo, pos, parada_activada
    while True:
        parada = float(RDK.getParam("stop") or 0)
        parada_activada = parada == 1
        if parada_activada:
            time.sleep(0.5)
            continue

        sensor_val = str(RDK.getParam(SENSOR_IO)).strip().lower()
        sensor_activo = sensor_val in ("1", "1.0", "true")

        if sensor_activo:
            tray_detectada = sensor_activo_con_tray_cercano()
            if tray_detectada and not procesando:
                rechazar_bollos()
                ejecutar_relleno(tray_detectada)
        else:
            procesando = False

        eliminar_objetivo_si_sensor_activo()

        if not parada_activada and not sensor_activo and not procesando and not rechazando:
            pos += speed * interval
            conveyor.setJoints([pos])

        time.sleep(interval)

def ciclo_generacion():
    global tray_queue
    while True:
        if parada_activada:
            time.sleep(0.1)
            continue
        childs = conveyor_frame.Childs()
        tray_queue = [tray for tray in tray_queue if tray.Valid(True) and tray in childs]
        if not tray_queue or distancia_entre_ultimas() > 350:
            nueva = spawn_tray()
            if nueva:
                tray_queue.append(nueva)
        time.sleep(0.1)

# ---------- Main ----------
def main():
    inicializar_entorno()
    threading.Thread(target=ciclo_principal, daemon=True).start()
    threading.Thread(target=ciclo_generacion, daemon=True).start()
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
