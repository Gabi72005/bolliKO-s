from robodk import robolink
import paho.mqtt.client as mqtt
import json

# Conexión con RoboDK
RDK = robolink.Robolink()

# Configuración del broker
BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "richi5/giirob/esp32/enviar"
CLIENT_ID = "robodk_display_client"

# Contador de pedidos recibidos
pedido_count = 0

# Callback al conectar
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado a EMQX")
        client.subscribe(TOPIC)
        client.publish(TOPIC, "READY")
        print("📤 READY publicado")
    else:
        print(f"❌ Error de conexión: {rc}")

# Callback al recibir mensaje
def on_message(client, userdata, msg):
    global pedido_count

    texto = msg.payload.decode()
    print(f"📨 [{msg.topic}] {texto}")
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
            print(f"🧾 Variable creada: {nombre_variable} = {cantidad}")

        elif datos.get("evento") == "bollo_defectuoso":
            RDK.setParam("rechazar", "true")
            print("🚨 Evento de bollo defectuoso recibido. Activando rechazo.")

        elif datos.get("evento") == "stop":
            RDK.setParam("stop", 1)
            print("STOP RECIBIDO")
        
        elif datos.get("evento") == "start":
            RDK.setParam("stop", 0)
            print("STOP RECIBIDO")

    except Exception as e:
        print(f"⚠️ Error procesando el mensaje JSON: {e}")


# Crear cliente MQTT
client = mqtt.Client(client_id=CLIENT_ID)
client.on_connect = on_connect
client.on_message = on_message

# Conectar y comenzar bucle
client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
