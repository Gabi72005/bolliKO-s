from robodk import robolink, robomath
from robodk.robomath import *
import time

# Inicializar conexión con RoboDK
RDK = robolink.Robolink()

# Obtener referencias clave en la estación
frame_cinta = RDK.Item('Reference Copias Bolsa', robolink.ITEM_TYPE_FRAME)
frame_mesa = RDK.Item('2UR16e Base', robolink.ITEM_TYPE_FRAME)
conveyor = RDK.Item('segundaConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)
robot = RDK.Item('2UR16e', robolink.ITEM_TYPE_ROBOT)

# Verificar que todos los elementos necesarios existen
for item, name in [(frame_cinta, 'frame de la cinta'), (conveyor, 'cinta'), (robot, 'robot 2UR16e')]:
    if not item.Valid():
        raise Exception(f"No se encontró el {name}")

# Eliminar objetos tipo 'bolsa' o 'Objetivo' dentro del frame de la cinta
for obj in frame_cinta.Childs():
    if obj.Type() == robolink.ITEM_TYPE_OBJECT and obj.Name() in ['bolsa', 'Objetivo']:
        RDK.Delete(obj)

# Resetear la posición de la cinta
RDK.setParam('POS_CINTA', 0.0)

# Mover el robot al target 'Home2'
home_target = RDK.Item('Home2', robolink.ITEM_TYPE_TARGET)
if not home_target.Valid():
    raise Exception("No se encontró el target 'Home2'")
robot.MoveJ(home_target)

# Eliminar objetos tipo 'bolsa' o 'Objetivo' que estén sobre la mesa del robot
for obj in frame_mesa.Childs():
    if obj.Type() == robolink.ITEM_TYPE_OBJECT and obj.Name() in ['bolsa', 'Objetivo']:
        RDK.Delete(obj)

# Obtener y limpiar el frame de colocación original
frame_colocacion = RDK.Item("colocacion", robolink.ITEM_TYPE_FRAME)
if frame_colocacion.Valid():
    for child in frame_colocacion.Childs():
        RDK.Delete(child)

# Obtener y limpiar el frame "Frame Bolsas" de la cuarta cinta
frame_bolsas = RDK.Item("Frame Bolsas", robolink.ITEM_TYPE_FRAME)
if frame_bolsas.Valid():
    for child in frame_bolsas.Childs():
        RDK.Delete(child)

# Resetear posición de la cuarta cinta
cuarta_cinta = RDK.Item('cuartaConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)
if cuarta_cinta.Valid():
    cuarta_cinta.setJoints([0.0])

# Establecer valores iniciales para las variables de la estación
RDK.setParam("caja_disponible", "1")
RDK.setParam("bolsas_en_caja", "0")
