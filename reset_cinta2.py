from robodk import robolink, robomath

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
