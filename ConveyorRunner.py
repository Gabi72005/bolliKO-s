from robodk import robolink, robomath
import time


# ---------- Inicializar RoboDK ----------
RDK = robolink.Robolink()
RDK.setSelection([])

# ---------- Función de acceso seguro ----------
def modificar_parametro_con_lock(param_name, funcion_modificadora, lock_name=None, intentos=20, espera=0.05):
    if lock_name is None:
        lock_name = f'lock_{param_name}'
    for _ in range(intentos):
        if str(RDK.getParam(lock_name)) != '1':
            RDK.setParam(lock_name, 1)
            try:
                valor_actual = float(RDK.getParam(param_name) or 0)
                nuevo_valor = funcion_modificadora(valor_actual)
                RDK.setParam(param_name, nuevo_valor)
                return nuevo_valor
            finally:
                RDK.setParam(lock_name, 0)
        time.sleep(espera)
    raise Exception(f'No se pudo obtener el lock para {param_name}')

# ---------- Obtener objetos ----------
SENSOR_IO = 'sensor_robot_uno'
SENSOR_FINAL_IO = 'sensor_final_uno'

robot = RDK.Item('UR16e', robolink.ITEM_TYPE_ROBOT)
programa = RDK.Item('Relleno', robolink.ITEM_TYPE_PROGRAM)
sensor = RDK.Item(SENSOR_IO, robolink.ITEM_TYPE_OBJECT)
sensor_final = RDK.Item(SENSOR_FINAL_IO, robolink.ITEM_TYPE_OBJECT)

boxes = [x for x in RDK.ItemList(robolink.ITEM_TYPE_OBJECT) if 'box' in x.Name().lower() and 'ref' in x.Name().lower()]
if not boxes:
    RDK.ShowMessage('No reference box found.')
    quit()
ref_box = boxes[0]
ref_box.setVisible(False)
ref_box.Parent().setParam('Tree', 'Collapse')

conveyors = [x for x in RDK.ItemList(robolink.ITEM_TYPE_ROBOT_AXES) if len(x.Joints().tolist()) == 1 and 'conveyor' in x.Name().lower()]
if not conveyors:
    RDK.ShowMessage('No conveyor found.')
    quit()
conveyor = conveyors[0]

frames = [x for x in conveyor.Childs() if x.Type() == robolink.ITEM_TYPE_FRAME]
if not frames:
    frames = [RDK.AddFrame(conveyor.Name() + ' Frame', conveyor)]
conveyor_frame = frames[0]

# ---------- Validación ----------
for item, name in [(robot, 'robot'), (programa, 'programa'), (conveyor, 'cinta'),
                   (sensor, 'sensor principal'), (sensor_final, 'sensor final'), (conveyor_frame, 'frame')]:
    if not item.Valid():
        raise Exception(f'No se encontró el {name}')

# ---------- Funciones ----------
def fijar_z_a_4mm(objeto):
    pose = objeto.Pose()
    xyz = pose.Pos()
    xyz[2] = -1.5
    pose.setPos(xyz)
    objeto.setPose(pose)

def sensor_activo_con_box_cercano():
    if str(RDK.getParam(SENSOR_IO)) != "1.0":
        return None
    cajas = [b for b in conveyor_frame.Childs()
             if b.Type() == robolink.ITEM_TYPE_OBJECT and b.Valid(True) and b.Name().lower().startswith('box')]
    if not cajas:
        return None
    sensor_pose = sensor.Pose().Pos()
    return min(cajas, key=lambda c: sum((sensor_pose[i] - c.Pose().Pos()[i]) ** 2 for i in range(3)) ** 0.5)

def eliminar_objetivo_si_sensor_activo():
    if str(RDK.getParam(SENSOR_FINAL_IO)) != "1.0":
        return
    objetivos = [o for o in conveyor_frame.Childs()
                 if o.Type() == robolink.ITEM_TYPE_OBJECT and o.Valid(True) and o.Name().lower().startswith('objetivo')]
    if not objetivos:
        return
    sensor_pose = sensor_final.Pose().Pos()
    objetivo_cercano = min(objetivos, key=lambda c: sum((sensor_pose[i] - c.Pose().Pos()[i]) ** 2 for i in range(3)) ** 0.5)

    # Si el objetivo pertenece a un pedido, aumentar contador rellenados
    nombre_obj = objetivo_cercano.Name().lower()
    if 'pedido' in nombre_obj:
        partes = nombre_obj.replace('objetivo_', '').split('_')
        if len(partes) >= 2:
            nombre = '_'.join(partes[:-1])
            sabor = partes[-1]
            param_rellenados = f"rellenados_{nombre}_{sabor}"
            valor_actual = RDK.getParam(param_rellenados)
            valor_actual = float(valor_actual or 0)
            RDK.setParam(param_rellenados, valor_actual + 1)

    RDK.Delete(objetivo_cercano)
    modificar_parametro_con_lock('empaquetados_normal', lambda v: v + 1)

def spawn_box():
    RDK.Render(False)
    selection = RDK.Selection()
    parametros = RDK.getParams()
    pedido_param = None
    for clave, valor in parametros:
        if clave.startswith("pedido_"):
            if valor in [None, '', 'None']:
                RDK.setParam(clave, None)
                print(f"🧹 Eliminada variable inválida: {clave}")
                continue
            try:
                if float(valor) > 0:
                    pedido_param = clave
                    break
            except (ValueError, TypeError):
                RDK.setParam(clave, None)
                print(f"🧹 Eliminada variable corrupta: {clave}")
                continue

    if pedido_param:
        print(f"🎯 Generando caja personalizada: {pedido_param}")
        sabor = pedido_param.split('_')[-1]
        nombre = '_'.join(pedido_param.split('_')[1:-1])
        sabor_normalizado = sabor.lower().replace(" ", "").replace("_", "")
        ref_caja = None
        for item in RDK.ItemList(robolink.ITEM_TYPE_OBJECT):
            nombre_item = item.Name().lower().replace(" ", "").replace("_", "")
            if nombre_item == f"reference{sabor_normalizado}":
                ref_caja = item
                break
        if not ref_caja or not ref_caja.Valid():
            print(f"⚠️ No se encontró Reference_{sabor}, usando caja normal")
            ref_caja = ref_box

        # Guardar cantidad original del pedido si no se ha guardado
        seguro_param = f"seguro_pedido_{nombre}_{sabor}"
        if RDK.getParam(seguro_param) is None:
            valor_original = float(RDK.getParam(pedido_param) or 0)
            RDK.setParam(seguro_param, valor_original)
            print(f"📌 Guardado seguro original: {seguro_param} = {valor_original}")

        # Decrementar el pedido
        valor_actual = float(RDK.getParam(pedido_param) or 0)
        nuevo_valor = valor_actual - 1
        RDK.setParam(pedido_param, nuevo_valor)

        # Si llega a 0, borrar la variable
        if nuevo_valor <= 0:
            RDK.setParam(pedido_param, None)
            print(f"🗑️ Pedido completado. Eliminado: {pedido_param}")
    else:
        ref_caja = ref_box
        nombre = None
        sabor = None

    ref_caja.Copy(copy_children=False)
    time.sleep(0.05)
    new_box = ref_caja.Parent().Paste()
    RDK.setSelection(selection)

    if not new_box.Valid():
        RDK.ShowMessage("❌ Error: no se pudo crear una nueva caja.")
        return None

    new_box.setVisible(False)
    if pedido_param and nombre and sabor:
        new_box.setName(f'Box_pedido_{nombre}_{sabor}')
    else:
        new_box.setName('Box')

    new_box.setParentStatic(conveyor_frame)
    new_box.setVisible(True)
    RDK.Render(True)
    return new_box


def rechazar_bollos():
    if str(RDK.getParam('rechazar')).lower() != 'true':
        return

    base_lift = RDK.Item('OnRobot Lift100 Base', robolink.ITEM_TYPE_FRAME)
    lift = RDK.Item('OnRobot Lift100', robolink.ITEM_TYPE_ROBOT_AXES)

    if not base_lift.Valid() or not lift.Valid():
        print("⚠️ No se encontró el actuador o su base.")
        return

    # Movimiento progresivo como la cinta
    pos_lift = 0.0
    velocidad = 500.0
    intervalo = 0.05
    while pos_lift < 500.0:
        pos_lift += velocidad * intervalo
        lift.setJoints([min(pos_lift, 500)])
        time.sleep(intervalo)

    cajas = [b for b in conveyor_frame.Childs()
             if b.Type() == robolink.ITEM_TYPE_OBJECT and b.Valid(True) and b.Name().lower().startswith('box')]
    if not cajas:
        print("❌ No se encontraron cajas para eliminar.")
        return

    base_pos = base_lift.PoseAbs().Pos()
    bandeja_cercana = min(cajas, key=lambda c: sum((base_pos[i] - c.PoseAbs().Pos()[i]) ** 2 for i in range(3)) ** 0.5)

    print(f"🗑️ Eliminando bandeja: {bandeja_cercana.Name()}")

    # Si es un pedido, reducir seguro
    nombre_caja = bandeja_cercana.Name().lower()
    if 'pedido' in nombre_caja:
        partes = nombre_caja.replace('box_pedido_', '').split('_')
        if len(partes) >= 2:
            nombre = '_'.join(partes[:-1])
            sabor = partes[-1]
            variable_seguro = f"seguro_pedido_{nombre}_{sabor}"
            print(f"🔁 Decrementando {variable_seguro}")
            modificar_parametro_con_lock(variable_seguro, lambda v: max(v - 1, 0))
    RDK.Delete(bandeja_cercana)

    # Retorno suave
    while pos_lift > 0.0:
        pos_lift -= velocidad * intervalo
        lift.setJoints([max(pos_lift, 0)])
        time.sleep(intervalo)

    RDK.setParam('rechazar', 'false')

# ---------- Variables de control ----------
pos = 0.0
speed = 300
interval = 0.1
procesando = False
box_queue = conveyor_frame.Childs()

# ---------- Loop principal ----------

while 1:
    time.sleep(interval)
    parada_emergencia = float(RDK.getParam("stop") or 0)
    while parada_emergencia == 1:
        RDK.ShowMessage("PARADA EMERGENCIA ACTIVADA", False)
        parada_emergencia = float(RDK.getParam("stop") or 0)
    pos += speed * interval
    conveyor.setJoints([pos])

    eliminar_objetivo_si_sensor_activo()
    caja_detectada = sensor_activo_con_box_cercano()

    if caja_detectada:
        rechazar_bollos()
        if not procesando:
            RDK.ShowMessage("🚨 Caja detectada. Ejecutando relleno...", False)
            nombre_caja = caja_detectada.Name().lower()
            if 'pedido' in nombre_caja:
                nombre_objetivo = nombre_caja.replace('box_', 'objetivo_')
            else:
                nombre_objetivo = 'Objetivo'
            caja_detectada.setName(nombre_objetivo)
            programa.RunProgram()
            while programa.Busy():
                time.sleep(0.1)
            fijar_z_a_4mm(caja_detectada)
            procesando = True
    else:
        procesando = False

    childs = conveyor_frame.Childs()
    for box in box_queue[:]:
        if not box.Valid(True) or box not in childs:
            box_queue.remove(box)

    if not box_queue:
        nueva = spawn_box()
        if nueva:
            box_queue.append(nueva)
        continue

    last_box = box_queue[-1]
    if last_box.Valid(True) and last_box.Name().lower().startswith('box'):
        pos_last = last_box.PoseAbs().Pos()[0]
        pos_ref = ref_box.PoseAbs().Pos()[0]
        distancia = abs(pos_last - pos_ref)
        if distancia > 350:
            nueva = spawn_box()
            if nueva:
                box_queue.append(nueva)

