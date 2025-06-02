from robodk import robolink, robomath
from robodk.robomath import *
import paho.mqtt.client as mqtt
import json
import time
import threading
import re

RDK = robolink.Robolink()
RDK.setSelection([])
RDK.setParam("lock_spawn_tray", "0")

# ---------- MQTT Config ----------
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "richi5/giirob/esp32/recibir"
MQTT_CLIENT_ID = "robodk_produccion"
sensor = "sensor_pedidos_final"

mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

sensor_final = RDK.Item(sensor, robolink.ITEM_TYPE_OBJECT)
if not sensor_final.Valid():
    quit()

# ---------- Lock ----------
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

# ---------- MQTT Envío ----------
def enviar_mensaje(evento, nombre=None):
    mensaje = {"evento": evento}
    if nombre:
        mensaje["pedido"] = nombre
    mqtt_client.publish(MQTT_TOPIC, json.dumps(mensaje))

# ---------- Enviar READY ----------
enviar_mensaje("READY")

# ---------- Objetos necesarios ----------
ref_bag = next((x for x in RDK.ItemList(robolink.ITEM_TYPE_OBJECT)
                if 'reference' in x.Name().lower() and 'bag' in x.Name().lower()), None)
if not ref_bag:
    RDK.ShowMessage('No reference bag found.')
    quit()
ref_bag.setVisible(False)

conveyor = next((x for x in RDK.ItemList(robolink.ITEM_TYPE_ROBOT_AXES)
                 if len(x.Joints().tolist()) == 1 and 'cuarta' in x.Name().lower()), None)
if not conveyor:
    RDK.ShowMessage('No conveyor found.')
    quit()

frames = [x for x in conveyor.Childs() if x.Type() == robolink.ITEM_TYPE_FRAME]
conveyor_frame = frames[0] if frames else RDK.AddFrame("Frame Cuarta", conveyor)

# ---------- Variables ----------
pos = 0.0
speed = 300
interval = 0.1
box_queue = []
ref_box = ref_bag

# ---------- Generación de bolsa ----------
def spawn_bolsa(nombre, sabor, contador):
    if adquirir_lock("lock_spawn_tray"):
        try:
            RDK.Render(False)
            selection = RDK.Selection()

            sabor_norm = sabor.lower().strip()
            nombre_ref = f"referencebag_{sabor_norm}"
            ref_especifica = next((x for x in RDK.ItemList(robolink.ITEM_TYPE_OBJECT)
                                   if x.Name().lower() == nombre_ref), None)

            bolsa_base = ref_especifica if ref_especifica and ref_especifica.Valid() else ref_bag
            bolsa_base.Copy(copy_children=False)
            time.sleep(0.05)
            nueva = bolsa_base.Parent().Paste()
            RDK.setSelection(selection)

            if nueva and nueva.Valid():
                nueva.setParentStatic(conveyor_frame)
                nueva.setName(f"Bag_{nombre}_{sabor}_{contador}")
                nueva.setVisible(True)
                RDK.Render(True)
                return nueva
        finally:
            liberar_lock("lock_spawn_tray")
    return None

# ---------- Eliminar bolsa cercana al sensor ----------
def eliminar_bolsa_cercana():
    objetivos = [o for o in conveyor_frame.Childs()
                 if o.Type() == robolink.ITEM_TYPE_OBJECT and o.Valid(True) and o.Name().lower().startswith('bag')]
    if not objetivos:
        return
    sensor_pose = sensor_final.Pose().Pos()
    objetivo_cercano = min(objetivos, key=lambda c: sum((sensor_pose[i] - c.Pose().Pos()[i]) ** 2 for i in range(3)) ** 0.5)
    RDK.Delete(objetivo_cercano)

# ---------- Limpieza de variables ----------
def limpieza_variables():
    for clave, valor in RDK.getParams():
        if "eliminar" in clave.lower():
            RDK.setParam(clave, "")

# ---------- Bucle principal ----------
while True:
    if float(RDK.getParam("stop") or 0) == 1:
        while float(RDK.getParam("stop") or 0) == 1:
            RDK.ShowMessage("PARADA EMERGENCIA ACTIVADA", False)
        continue

    if int(float(RDK.getParam(sensor) or 0)) == 0:
        time.sleep(interval)
        pos += speed * interval
        conveyor.setJoints([pos])

        claves = [k for k, v in RDK.getParams() if v not in [None, '', 'None'] and k.startswith("rellenados_pedido_")]

        for clave in claves:
            match = re.match(r"rellenados_pedido_(.+)_(vainilla|fresa|chocolate)$", clave, re.IGNORECASE)
            if not match:
                continue
            nombre, sabor = match.groups()
            clave_rellenados = f"rellenados_pedido_{nombre}_{sabor}"
            clave_seguro = f"seguro_pedido_{nombre}_{sabor}"
            clave_pedido = f"pedido_{nombre}_{sabor}"

            try:
                rellenados = int(float(RDK.getParam(clave_rellenados) or 0))
                seguro = int(float(RDK.getParam(clave_seguro) or 0))
            except:
                continue

            if rellenados != seguro or rellenados <= 0:
                continue

            box_queue = [b for b in box_queue if b.Valid(True) and b in conveyor_frame.Childs()]

            if not box_queue or not RDK.Collision(box_queue[-1], ref_box):
                nueva = spawn_bolsa(nombre, sabor, rellenados)
                nuevo_valor = rellenados - 1
                nuevo_seguro = seguro - 1

                RDK.setParam(clave_rellenados, nuevo_valor)
                RDK.setParam(clave_seguro, nuevo_seguro)

                if nueva:
                    box_queue.append(nueva)

                if nuevo_valor <= 0:
                    enviar_mensaje("fin_produccion", nombre)
                    RDK.setParam(clave_rellenados, "")
                    RDK.setParam(clave_seguro, "")
                    RDK.setParam(clave_pedido, "")
                    RDK.setParam(f"eliminar_pedido_{nombre.lower()}_{sabor.lower()}", "0")
                    RDK.setParam(f"eliminar_seguro_{nombre.lower()}_{sabor.lower()}", "0")
    else:
        eliminar_bolsa_cercana()
        limpieza_variables()
