from robodk import robolink
import paho.mqtt.client as mqtt
import json

RDK = robolink.Robolink()

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "richi5/giirob/esp32/enviar"
CLIENT_ID = "robodk_display_client"

pedido_count = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC)
        client.publish(TOPIC, "READY")

def on_message(client, userdata, msg):
    global pedido_count

    texto = msg.payload.decode()
    RDK.ShowMessage(f"📩 Mensaje MQTT recibido:\n\n{texto}", False)

    try:
        datos = json.loads(texto)
        if datos.get("evento") == "nuevo_pedido":
            sabor = datos.get("sabor", "desconocido")
            cantidad = int(datos.get("cantidad", 0))
            nombre = datos.get("nombre", "x")
            pedido_count += 1

            nombre_variable = f"pedido_{nombre}_{sabor}"
            RDK.setParam(nombre_variable, cantidad)

        elif datos.get("evento") == "bollo_defectuoso":
            RDK.setParam("rechazar", "true")

        elif datos.get("evento") == "stop":
            RDK.setParam("stop", 1)

        elif datos.get("evento") == "start":
            RDK.setParam("stop", 0)

    except:
        pass

client = mqtt.Client(client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
