import os
import re
import requests
import cloudscraper
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def enviar_alerta_discord(titulo, precio_actual, precio_referencia, motivo="minimo"):
    if not WEBHOOK_URL:
        print("Falta el Webhook de Discord.")
        return

    # Formatear los números para que se vean como plata chilena (ej: $15.000)
    precio_clp = f"${precio_actual:,.0f}".replace(",", ".")
    ref_clp = f"${precio_referencia:,.0f}".replace(",", ".")

    # Personalizamos el mensaje según el tipo de alerta
    if motivo == "target":
        color = 15105570 # Naranja
        desc = "¡El libro bajó de tu presupuesto objetivo! Es el momento de comprarlo."
        titulo_embed = "🎯 ¡OBJETIVO DE PRECIO ALCANZADO! 🎯"
        nombre_ref = "Tu Presupuesto"
    else:
        color = 3066993 # Verde oscuro
        desc = "El bot detectó el precio más bajo registrado hasta ahora. ¡Ideal para reventar la tarjeta!"
        titulo_embed = "🚨 ¡ALERTA DE GANGA! MÍNIMO HISTÓRICO 🚨"
        nombre_ref = "Mejor Precio Anterior"

    mensaje = {
        "content": f"**{titulo_embed}**",
        "embeds": [{
            "title": titulo,
            "description": desc,
            "color": color,
            "fields": [
                {"name": "💰 Precio Actual", "value": precio_clp, "inline": True},
                {"name": f"📉 {nombre_ref}", "value": ref_clp, "inline": True}
            ]
        }]
    }

    respuesta = requests.post(WEBHOOK_URL, json=mensaje)
    if respuesta.status_code in [200, 204]:
        print(f"✅ Alerta enviada a Discord por {titulo} ({motivo})")
    else:
        print(f"❌ Error al enviar alerta: {respuesta.status_code}")

def obtener_conexion():
    """Crea la conexión a la base de datos PostgreSQL en Supabase"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", "6543"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conn
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def ejecutar_etl():
    print("🚀 Iniciando pipeline ETL...")
    conn = obtener_conexion()
    if not conn:
        return

    cursor = conn.cursor()

    # -----------------------------------------
    # 0. OBTENER LISTAS DINÁMICAS DESDE SUPABASE
    # -----------------------------------------
    try:
        cursor.execute("SELECT url_lista FROM listas_monitoreo WHERE estado = 'Activo'")
        urls_bd = cursor.fetchall()
        listas_a_raspar = [fila[0] for fila in urls_bd]
    except Exception as e:
        print(f"❌ Error al leer listas de monitoreo. Asegúrate de haber creado la tabla: {e}")
        conn.close()
        return

    if not listas_a_raspar:
        print("⚠️ No hay listas activas en la base de datos. Agrega una desde Discord.")
        cursor.close()
        conn.close()
        return

    # -----------------------------------------
    # 1 y 2. EXTRACT & TRANSFORM (Múltiples Listas)
    # -----------------------------------------
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    libros_procesados = {} # Usamos un diccionario para evitar duplicados

    for url in listas_a_raspar:
        print(f"🕵️‍♂️ Raspando lista: {url}")
        try:
            respuesta = scraper.get(url)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, 'html.parser')
            libros_html = soup.find_all('div', class_='producto')

            for libro in libros_html:
                caja_titulo = libro.find('div', class_='titulo')
                caja_precio = libro.find('div', class_='precioAhora')
                
                if not caja_titulo or not caja_precio:
                    continue # Saltamos los agotados o defectuosos
                    
                titulo = caja_titulo.text.strip()
                precio_limpio = int(re.sub(r'[^\d]', '', caja_precio.text))
                
                # Si el libro ya lo vimos en otra lista, nos quedamos con el que tenga el precio más bajo
                if titulo not in libros_procesados or precio_limpio < libros_procesados[titulo]["precio"]:
                    libros_procesados[titulo] = {
                        "titulo": titulo,
                        "precio": precio_limpio,
                        "estado": "Disponible"
                    }
        except Exception as e:
            print(f"⚠️ Error al extraer datos de la lista {url}: {e}")

    print(f"📚 Se procesaron {len(libros_procesados)} libros únicos en total.")

    # -----------------------------------------
    # 3. LOAD (Carga en Data Mart Kimball)
    # -----------------------------------------
    if not libros_procesados:
        print("No se extrajeron libros en ninguna lista.")
        cursor.close()
        conn.close()
        return

    try:
        hoy = datetime.now()
        id_fecha_hoy = int(hoy.strftime("%Y%m%d"))
        
        # A. Dimensión Fecha
        cursor.execute("SELECT id_fecha FROM dim_fecha WHERE id_fecha = %s", (id_fecha_hoy,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO dim_fecha (id_fecha, fecha_exacta, anio, mes, dia)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_fecha_hoy, hoy.date(), hoy.year, hoy.month, hoy.day))
        
        # B. Iterar sobre cada libro único procesado
        for data in libros_procesados.values():
            titulo = data["titulo"]
            precio_actual = data["precio"]

            # Buscar si el libro existe y sacar su precio_target
            cursor.execute("SELECT id_libro, precio_target FROM dim_libro WHERE titulo = %s", (titulo,))
            resultado_libro = cursor.fetchone()
            
            if resultado_libro:
                id_libro = resultado_libro[0]
                precio_target = resultado_libro[1]
            else:
                cursor.execute("""
                    INSERT INTO dim_libro (titulo, estado)
                    VALUES (%s, %s) RETURNING id_libro
                """, (titulo, data["estado"]))
                id_libro = cursor.fetchone()[0]
                precio_target = None
                print(f"📖 Nuevo libro registrado en BD: {titulo}")
                
            # C. Lógica de Alertas Inteligentes
            cursor.execute("SELECT MIN(precio) FROM fact_precio WHERE id_libro = %s", (id_libro,))
            resultado_min = cursor.fetchone()
            precio_minimo_historico = resultado_min[0]

            # Alerta 1: Cumplió tu Target de presupuesto
            if precio_target and precio_actual <= precio_target:
                enviar_alerta_discord(titulo, precio_actual, precio_target, motivo="target")
            
            # Alerta 2: Es un nuevo Mínimo Histórico absoluto
            elif precio_minimo_historico is not None and precio_actual < precio_minimo_historico:
                enviar_alerta_discord(titulo, precio_actual, precio_minimo_historico, motivo="minimo")

            # D. Insertar el hecho
            cursor.execute("""
                INSERT INTO fact_precio (id_libro, id_fecha, precio)
                VALUES (%s, %s, %s)
            """, (id_libro, id_fecha_hoy, precio_actual))
            
            print(f"💰 Precio guardado: {titulo} a ${precio_actual}")

        conn.commit()
        print("✅ ETL finalizado con éxito.")
        
    except Exception as e:
        print(f"❌ Error durante la inserción en la base de datos: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    ejecutar_etl()