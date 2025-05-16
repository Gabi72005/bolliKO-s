from robodk import robolink
from robodk.robomath import *
import time

RDK = robolink.Robolink()

# Referencias
frame_copias = RDK.Item('Frame Copias Cajas', robolink.ITEM_TYPE_FRAME)
cinta = RDK.Item('terceraConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)

if not (frame_copias.Valid() and cinta.Valid()):
    RDK.ShowMessage("❌ No se encontraron todos los elementos necesarios (cintas o frame)")
    quit()

sensor_final_gestionado = False

# Eliminar objetos llamados 'bolsa' recursivamente
def eliminar_objetos_borrar_en_subarbol(item):
    for hijo in item.Childs():
        if hijo.Type() == robolink.ITEM_TYPE_OBJECT and hijo.Name() == 'bolsa':
            hijo.Delete()
        else:
            eliminar_objetos_borrar_en_subarbol(hijo)

# Gestión del sensor final
def gestionar_sensor_final():
    global sensor_final_gestionado
    sensor_final = float(RDK.getParam('sensor_final_produccion', True)) == 1

    if sensor_final and not sensor_final_gestionado:
        sensor_final_gestionado = True

        frame_colocacion = RDK.Item('colocacion', robolink.ITEM_TYPE_FRAME)
        if frame_colocacion.Valid():
            eliminar_objetos_borrar_en_subarbol(frame_colocacion)

        caja = None
        for hijo in frame_copias.Childs():
            if hijo.Name() == 'Caja' and hijo.Valid():
                caja = hijo
                break

        if caja and caja.Valid():
            eliminar_objetos_borrar_en_subarbol(caja)
            caja.Delete()

        RDK.setParam('bolsas_en_caja', 0)
        RDK.setParam('caja_disponible', 1)

    elif not sensor_final:
        sensor_final_gestionado = False

# Bucle principal
while True:
    time.sleep(0.05)
    parada_emergencia = float(RDK.getParam("stop") or 0)
    while parada_emergencia == 1:
        RDK.ShowMessage("PARADA EMERGENCIA ACTIVADA", False)
        parada_emergencia = float(RDK.getParam("stop") or 0)

    gestionar_sensor_final()

    sensor_activo = float(RDK.getParam('sensor_robot_dos', True))
    contador = float(RDK.getParam('bolsas_en_caja', True) or 0)
    caja_disponible = float(RDK.getParam('caja_disponible', True) or 0)

    if contador >= 3 and caja_disponible == 1:
        RDK.setParam('caja_disponible', 0)

        pos = 0.0
        speed = 300
        interval = 0.05

        while float(RDK.getParam('caja_disponible', True)) == 0:
            time.sleep(interval)
            gestionar_sensor_final()
            pos += speed * interval
            cinta.setJoints([float(pos)])

        # Recolocar la cinta a la posición inicial
        cinta.setJoints([0.0])

        # 👉 Copiar objeto 'Nada' desde 'original_caja_frame' y pegarlo como 'Caja' en 'Frame Copias Cajas'
        frame_origen = RDK.Item('original_caja_frame', robolink.ITEM_TYPE_FRAME)
        objeto_nada = RDK.Item('Nada', robolink.ITEM_TYPE_OBJECT)

        if frame_origen.Valid() and objeto_nada.Valid():
            RDK.Render(False)
            objeto_nada.Copy()
            nueva_caja = frame_origen.Paste()
            nueva_caja.setName('Caja')
            nueva_caja.setVisible(True)
            nueva_caja.setParentStatic(frame_copias)
            RDK.Render(True)
