from robodk import robolink, robomath

# Conexión con RoboDK
RDK = robolink.Robolink()

# Obtener elementos clave
robot = RDK.Item('UR16e', robolink.ITEM_TYPE_ROBOT)
frame_cinta = RDK.Item('Conveyor Belt (2m) Frame', robolink.ITEM_TYPE_FRAME)
conveyor = RDK.Item('Conveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)

# Validaciones
for item, name in [(robot, 'robot'), (frame_cinta, 'frame de la cinta'), (conveyor, 'cinta')]:
    if not item.Valid():
        raise Exception(f"No se encontró el {name}")

# 1. Mover el robot a posición inicial
home_target = RDK.Item('Home', robolink.ITEM_TYPE_TARGET)
if not home_target.Valid():
    raise Exception("No se encontró la posición 'Home' del robot")

robot.MoveJ(home_target)

# 2. Borrar todos los objetos llamados 'Box' o 'Objetivo' en el frame de la cinta
for obj in frame_cinta.Childs():
    if obj.Type() == robolink.ITEM_TYPE_OBJECT and obj.Name() in ['Box', 'Objetivo']:
        RDK.Delete(obj)

# Eliminar también cajas personalizadas que empiecen por 'Box_pedido'
for obj in frame_cinta.Childs():
    if obj.Type() == robolink.ITEM_TYPE_OBJECT and obj.Name().startswith('Box_pedido'):
        RDK.Delete(obj)

print("✅ Objetos eliminados: Box y Objetivo")

# 3. Resetear parámetro de la cinta
RDK.setParam('POS_CINTA', 0.0)  # Puedes cambiar el nombre del parámetro si usas otro
print("✅ Parámetro de cinta reiniciado")

RDK.setParam('empaquetados_normal', 0.0)

print("🚀 Estación reseteada correctamente")
from robodk import robolink


# Obtener todas las variables de estación como lista de pares [clave, valor]
parametros = RDK.getParams()

# Filtrar y eliminar las que empiezan por "pedido_"
eliminadas = 0
for clave, _ in parametros:
    if isinstance(clave, str) and clave.startswith("pedido_"):
        RDK.setParam(clave, "")  # Vaciar valor elimina la variable
        eliminadas += 1
        print(f"🗑️ Variable eliminada: {clave}")

for clave, _ in RDK.getParams():
    if clave.startswith("envoltorios_") or clave.startswith("lock_envoltorios_") or clave.startswith("rellenados_") or clave.startswith("seguro_"):
        print(f"🗑️ Eliminando parámetro: {clave}")
        RDK.setParam(clave, "")


RDK.setParam("stop", 0)
