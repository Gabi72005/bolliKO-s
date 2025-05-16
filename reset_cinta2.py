from robodk import robolink, robomath

# Conexión con RoboDK
RDK = robolink.Robolink()

# Obtener elementos clave
frame_cinta = RDK.Item('Reference Copias Bolsa', robolink.ITEM_TYPE_FRAME)
conveyor = RDK.Item('segundaConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)
robot = RDK.Item('2UR16e', robolink.ITEM_TYPE_ROBOT)

# Validaciones
for item, name in [(frame_cinta, 'frame de la cinta'), (conveyor, 'cinta'), (robot, 'robot 2UR16e')]:
    if not item.Valid():
        raise Exception(f"No se encontró el {name}")

# 1. Borrar todos los objetos llamados 'bolsa' o 'Objetivo' en el frame de la cinta
for obj in frame_cinta.Childs():
    if obj.Type() == robolink.ITEM_TYPE_OBJECT and obj.Name() in ['bolsa', 'Objetivo']:
        RDK.Delete(obj)

# 2. Resetear parámetro de la cinta
RDK.setParam('POS_CINTA', 0.0)
print("✅ Parámetro de cinta reiniciado")

# 3. Mover el robot a Home2
home_target = RDK.Item('Home2', robolink.ITEM_TYPE_TARGET)
if not home_target.Valid():
    raise Exception("❌ No se encontró el target 'Home2'")
robot.MoveJ(home_target)
print("🤖 Robot movido a Home2")

print("🚀 Estación reseteada correctamente")
