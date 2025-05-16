from robodk import robolink, robomath
import time
import threading

RDK = robolink.Robolink()
RDK.setSelection([])

# ------------------- FLAGS -------------------
sensor_ya_gestionado = False
robot_en_movimiento = False
esperar_attach = False

# ------------------- FUNCIONES DE LOCK -------------------
def modificar_parametro_con_lock(param_name, funcion_modificadora, lock_name=None, intentos=20, espera=0.05):
    if lock_name is None:
        lock_name = f'lock_{param_name}'
    for _ in range(intentos):
        if str(RDK.getParam(lock_name)) != '1':
            RDK.setParam(lock_name, 1)
            try:
                valor_actual = float(RDK.getParam(param_name) or 0)
                nuevo_valor = funcion_modificadora(valor_actual)
                RDK.setParam(param_name, str(nuevo_valor))
                return nuevo_valor
            finally:
                RDK.setParam(lock_name, 0)
        time.sleep(espera)
    raise Exception(f'No se pudo obtener el lock para {param_name}')

# ------------------- SETUP RDK -------------------
ref_box = RDK.Item('bolsa', robolink.ITEM_TYPE_OBJECT)
if not ref_box.Valid():
    RDK.ShowMessage('No se encontró el objeto "bolsa"')
    quit()
ref_box.setVisible(False)
ref_box.Parent().setParam('Tree', 'Collapse')

conveyor = RDK.Item('segundaConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)
if not conveyor.Valid():
    RDK.ShowMessage('No se encontró la cinta')
    quit()

conveyor_frame = RDK.Item('Reference Copias Bolsa', robolink.ITEM_TYPE_FRAME)
if not conveyor_frame.Valid():
    RDK.ShowMessage('No se encontró el frame')
    quit()

def spawn_box():
    RDK.Render(False)
    selection = RDK.Selection()
    ref_box.Copy(copy_children=False)
    new_box = ref_box.Parent().Paste()
    RDK.setSelection(selection)
    new_box.setVisible(False)
    new_box.setName('bolsa')
    new_box.setPose(ref_box.Pose())
    new_box.setParentStatic(conveyor_frame)
    new_box.setVisible(True)
    RDK.Render(True)
    return new_box

def pick_and_place_robot_dos():
    global robot_en_movimiento, esperar_attach
    robot_en_movimiento = True
    esperar_attach = True
    try:
        while float(RDK.getParam('caja_disponible', True) or 0) == 0.0:
            time.sleep(0.1)

        robot = RDK.Item('2UR16e', robolink.ITEM_TYPE_ROBOT)
        tcp = robot.getLink(robolink.ITEM_TYPE_TOOL)
        frame_bolsas = RDK.Item('Reference Copias Bolsa', robolink.ITEM_TYPE_FRAME)
        frame_cajas = RDK.Item('colocacion', robolink.ITEM_TYPE_FRAME)
        caja_receptora = RDK.Item('Caja', robolink.ITEM_TYPE_OBJECT)
        targets_nombres = ['Home2', 'prePick2', 'Pick2', 'PrePlace2', 'Place2', 'Place2.2', 'Place2.3']
        targets = [RDK.Item(nombre, robolink.ITEM_TYPE_TARGET) for nombre in targets_nombres]

        while not all([robot.Valid(), tcp.Valid(), frame_bolsas.Valid(), frame_cajas.Valid(), caja_receptora.Valid()] + [t.Valid() for t in targets]):
            time.sleep(0.1)
            return

        VEL_NORMAL_LIN, VEL_NORMAL_JNT = 200, 30
        VEL_LENTA_LIN, VEL_LENTA_JNT = 50, 10

        robot.setSpeed(VEL_NORMAL_LIN, VEL_NORMAL_JNT)
        robot.MoveJ(targets[0], False)  # Home
        while robot.Busy(): time.sleep(0.01)

        robot.MoveJ(targets[1], False)  # prePick
        while robot.Busy(): time.sleep(0.01)

        robot.setSpeed(VEL_LENTA_LIN, VEL_LENTA_JNT)
        robot.MoveL(targets[2], False)  # Pick
        while robot.Busy(): time.sleep(0.01)

        bolsas = frame_bolsas.Childs()
        tcp_pos = tcp.Pose().Pos()
        bolsa_mas_cercana = min(
            (b for b in bolsas if b.Valid() and b.Type() == robolink.ITEM_TYPE_OBJECT),
            key=lambda b: robomath.norm(robomath.subs3(b.Pose().Pos(), tcp_pos)),
            default=None
        )

        if not bolsa_mas_cercana:
            RDK.ShowMessage('❌ No se encontró ninguna bolsa para recoger')
            return

        # 👉 Pausar la cinta antes del attach
        RDK.Render(False)
        bolsa_mas_cercana.setParent(RDK.Item('', robolink.ITEM_TYPE_STATION))
        bolsa_mas_cercana.setParentStatic(tcp)
        RDK.Render(True)
        print(f"✅ Bolsa '{bolsa_mas_cercana.Name()}' pegada al TCP")
        esperar_attach = False

        robot.MoveL(targets[1], False)  # Volver a prePick
        while robot.Busy(): time.sleep(0.01)

        robot.setSpeed(VEL_NORMAL_LIN, VEL_NORMAL_JNT)
        robot.MoveJ(targets[3], False)  # PrePlace
        while robot.Busy(): time.sleep(0.01)

        robot.setSpeed(VEL_LENTA_LIN, VEL_LENTA_JNT)

        contador = float(RDK.getParam('bolsas_en_caja', True) or 0)
        if contador == 0:
            target_destino = targets[4]  # Place2
            offset_y = 0
        elif contador == 1:
            target_destino = targets[5]  # Place2.2
            offset_y = 100
        elif contador == 2:
            target_destino = targets[6]  # Place2.3
            offset_y = 200
        else:
            print("⚠️ La caja ya tiene 3 bolsas")
            return

        pose_destino = target_destino.Pose()
        robot.MoveL(pose_destino, False)
        while robot.Busy(): time.sleep(0.01)

        tcp.DetachAll()
        bolsa_mas_cercana.setParentStatic(frame_cajas)

        pose_final = robomath.transl(0, offset_y, 0)
        bolsa_mas_cercana.setPose(pose_final)

        RDK.setParam('bolsas_en_caja', str(int(contador + 1)))
        print(f"📦 Bolsa '{bolsa_mas_cercana.Name()}' colocada en posición 0,{offset_y},0 del frame 'colocacion'.")

        robot.setSpeed(VEL_NORMAL_LIN, VEL_NORMAL_JNT)
        robot.MoveJ(targets[3], False)
        while robot.Busy(): time.sleep(0.01)

        robot.MoveJ(targets[0], False)
        while robot.Busy(): time.sleep(0.01)

    finally:
        robot_en_movimiento = False

# ------------------- VARIABLES -------------------
pos = 0.0
speed = 300
interval = 0.1

# ------------------- BUCLE PRINCIPAL -------------------
while True:
    parada_emergencia = float(RDK.getParam("stop") or 0)
    while parada_emergencia == 1:
        RDK.ShowMessage("PARADA EMERGENCIA ACTIVADA", False)
        parada_emergencia = float(RDK.getParam("stop") or 0)
    time.sleep(interval)

    sensor_activado = str(RDK.getParam('sensor_robot_dos')) == '1.0'

    if sensor_activado and not sensor_ya_gestionado and not robot_en_movimiento:
        sensor_ya_gestionado = True
        RDK.ShowMessage("🚨 Sensor activado: ejecutando pick and place con robot 2UR16e...", False)
        threading.Thread(target=pick_and_place_robot_dos).start()
        continue

    if not sensor_activado:
        sensor_ya_gestionado = False

    if not esperar_attach:
        pos += speed * interval
        conveyor.setJoints([pos])

    box_queue = conveyor_frame.Childs()

    childs = conveyor_frame.Childs()
    for box in box_queue[:]:
        if not box.Valid(True) or box not in childs:
            box_queue.remove(box)

    empaquetados_normal = float(RDK.getParam('empaquetados_normal') or 0)

    if empaquetados_normal > 0:
        if not box_queue:
            box_queue.append(spawn_box())
            modificar_parametro_con_lock('empaquetados_normal', lambda v: v - 1 if v > 0 else 0)
            continue

        last_box = box_queue[-1]
        if last_box.Valid(True) and not RDK.Collision(last_box, ref_box):
            box_queue.append(spawn_box())
            modificar_parametro_con_lock('empaquetados_normal', lambda v: v - 1 if v > 0 else 0)
