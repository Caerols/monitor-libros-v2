import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime

DATA_FILE = "historial_libros.json"

# Leer la URL secreta de Discord desde las variables de entorno
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def enviar_alerta_discord(mensaje):
    if not DISCORD_WEBHOOK_URL:
        print("Aviso: No se configuró la URL del Webhook de Discord. Alerta solo en consola.")
        return
        
    payload = {
        "content": mensaje
    }
    try:
        respuesta = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        respuesta.raise_for_status()
    except Exception as e:
        print(f"Error al enviar mensaje a Discord: {e}")

def cargar_historial():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_historial(historial):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

def evaluar_notificacion(titulo, precio_anterior, precio_nuevo):
    if precio_anterior is None:
        return f"📌 **{titulo}** ha sido agregado al monitoreo.\nPrecio inicial: ${precio_nuevo:,}"
    
    if precio_nuevo < precio_anterior:
        descuento = precio_anterior - precio_nuevo
        return f"📉 **¡OFERTA!** El libro **{titulo}** BAJÓ de precio.\nDe ~~${precio_anterior:,}~~ a **${precio_nuevo:,}**\n(Ahorras ${descuento:,})"
    elif precio_nuevo > precio_anterior:
        aumento = precio_nuevo - precio_anterior
        return f"🔺 **Alerta:** El libro **{titulo}** SUBIÓ de precio.\nDe ~~${precio_anterior:,}~~ a **${precio_nuevo:,}** (+${aumento:,})"
    
    return None

def registrar_precios_lista(url_lista):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        respuesta = requests.get(url_lista, headers=headers)
        sopa = BeautifulSoup(respuesta.text, 'html.parser')
        cajas_libros = sopa.find_all('div', class_='contenedorProducto')
        
        historial_completo = cargar_historial()
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for caja in cajas_libros:
            enlace = caja.find('a')
            titulo = enlace.get('title') if enlace else "Desconocido"
            precio_elemento = caja.find(class_='precioAhora')
            
            if precio_elemento:
                precio_nuevo = int(re.sub(r'[^\d]', '', precio_elemento.text.strip()))
                estado = "Disponible"
            else:
                precio_nuevo = 0
                estado = "Agotado"

            if titulo not in historial_completo:
                historial_completo[titulo] = {"precio_actual": precio_nuevo, "estado": estado, "historial": []}
                precio_anterior = None
            else:
                precio_anterior = historial_completo[titulo]["precio_actual"]

            if estado == "Disponible" and precio_nuevo != precio_anterior:
                alerta = evaluar_notificacion(titulo, precio_anterior, precio_nuevo)
                if alerta:
                    enviar_alerta_discord(alerta)

            historial_completo[titulo]["precio_actual"] = precio_nuevo
            historial_completo[titulo]["estado"] = estado
            historial_completo[titulo]["historial"].append({
                "fecha": fecha_actual,
                "precio": precio_nuevo
            })

        guardar_historial(historial_completo)
        print("Proceso de actualización completado.")

    except Exception as e:
        print(f"Error en el proceso: {e}")

if __name__ == "__main__":
    registrar_precios_lista("https://www.buscalibre.cl/v2/por-comprar_3413286_l.html")