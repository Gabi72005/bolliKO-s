from robodk import robolink, robomath
from robodk.robomath import *
import time
import threading

RDK = robolink.Robolink()

# ---------- Semáforo compartido ----------
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

# ---------- Referencias ----------
frame_copias = RDK.Item('Frame Copias Cajas', robolink.ITEM_TYPE_FRAME)
cinta = RDK.Item('terceraConveyor Belt (2m)', robolink.ITEM_TYPE_ROBOT)

if not (frame_copias.Valid() and cinta.Valid()):
    RDK.ShowMessage("❌ No se encontraron todos los elementos necesarios (cintas o frame)")
    quit()

sensor_final_gestionado = threading.Event()
parada_emergencia_event = threading.Event()

# ---------- Funciones ----------
def eliminar_objetos_borrar_en_subarbol(item):
    for hijo in item.Childs():
        if hijo.Type() == robolink.ITEM_TYPE_OBJECT and hijo.Name() == 'bolsa':
            hijo.Delete()
        else:
            eliminar_objetos_borrar_en_subarbol(hijo)

# ---------- Hilos ----------

def hilo_sensor_final():
    while True:
        if float(RDK.getParam('sensor_final_produccion', True)) == 1:
            if not sensor_final_gestionado.is_set():
                sensor_final_gestionado.set()

                frame_colocacion = RDK.Item('colocacion', robolink.ITEM_TYPE_FRAME)
                if frame_colocacion.Valid():
                    eliminar_objetos_borrar_en_subarbol(frame_colocacion)

                caja = next((h for h in frame_copias.Childs() if h.Name() == 'Caja' and h.Valid()), None)
                if caja:
                    eliminar_objetos_borrar_en_subarbol(caja)
                    caja.Delete()

                RDK.setParam('bolsas_en_caja', 0)
                RDK.setParam('caja_disponible', 1)
        else:
            sensor_final_gestionado.clear()
        time.sleep(0.05)

def hilo_cinta():
    pos = 0.0
    while True:
        if parada_emergencia_event.is_set():
            time.sleep(0.1)
            continue

        sensor_activo = float(RDK.getParam('sensor_robot_dos', True))
        contador = float(RDK.getParam('bolsas_en_caja', True) or 0)
        caja_disponible = float(RDK.getParam('caja_disponible', True) or 0)

        if contador >= 3 and caja_disponible == 1:
            RDK.setParam('caja_disponible', 0)

            speed = 200
            interval = 0.1

            while float(RDK.getParam('caja_disponible', True)) == 0:
                if parada_emergencia_event.is_set():
                    time.sleep(0.1)
                    continue
                time.sleep(interval)
                pos += speed * interval
                cinta.setJoints([float(pos)])

            cinta.setJoints([0.0])
            pos = 0.0

            frame_origen = RDK.Item('original_caja_frame', robolink.ITEM_TYPE_FRAME)
            objeto_nada = RDK.Item('Nada', robolink.ITEM_TYPE_OBJECT)

            if frame_origen.Valid() and objeto_nada.Valid():
                if adquirir_lock("lock_spawn_tray"):
                    try:
                        RDK.Render(False)
                        objeto_nada.Copy()
                        nueva_caja = frame_origen.Paste()
                        nueva_caja.setName('Caja')
                        nueva_caja.setVisible(True)
                        nueva_caja.setParentStatic(frame_copias)
                        RDK.Render(True)
                    finally:
                        liberar_lock("lock_spawn_tray")
        time.sleep(0.05)

def hilo_parada_emergencia():
    while True:
        parada = float(RDK.getParam("stop") or 0)
        if parada == 1:
            parada_emergencia_event.set()
            RDK.ShowMessage("⛔ PARADA EMERGENCIA ACTIVADA", False)
            while float(RDK.getParam("stop") or 0) == 1:
                time.sleep(0.1)
        else:
            parada_emergencia_event.clear()
        time.sleep(0.2)

# ---------- Main ----------
def main():
    RDK.setParam("lock_spawn_tray", "0")
    threading.Thread(target=hilo_sensor_final, daemon=True).start()
    threading.Thread(target=hilo_cinta, daemon=True).start()
    threading.Thread(target=hilo_parada_emergencia, daemon=True).start()
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
