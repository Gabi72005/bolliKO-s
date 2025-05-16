from robodk import robolink
from robodk.robomath import *
import time

RDK = robolink.Robolink()




# 1. Mover la cinta a posición (0,0,0)
conveyor = RDK.Item('cuartaConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)
if conveyor.Valid():
    conveyor.setJoints([0.0])  # HOME = posición inicial del eje
    print("🏁 Cinta movida a posición HOME (0.0)")
else:
    print("❌ No se encontró la cinta")
# 2. Eliminar objetos del frame 'colocacion'
frame_colocacion = RDK.Item("Frame Bolsas", robolink.ITEM_TYPE_FRAME)
if frame_colocacion.Valid():
    children = frame_colocacion.Childs()
    for child in children:
        child.Delete()
    print(f"🗑️ Objetos eliminados del frame 'colocacion': {len(children)}")
else:
    print("❌ No se encontró el frame 'colocacion'.")

# 3. Establecer variables de estación
