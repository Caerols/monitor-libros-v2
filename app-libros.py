import os
import re
import requests
import cloudscraper
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# --- CONFIGURACIÓN ---
URL_BUSCALIBRE = "https://www.buscalibre.cl/v2/por-comprar_3413286_l.html"

def enviar_alerta_discord(titulo, precio_actual, precio_minimo):
    if not WEBHOOK_URL:
        print("Falta el Webhook de Discord.")
        return

    # Formatear los números para que se vean como plata chilena (ej: $15.000)
    precio_clp = f"${precio_actual:,.0f}".replace(",", ".")
    minimo_clp = f"${precio_minimo:,.0f}".replace(",", ".")

    mensaje = {
        "content": "🚨 **¡ALERTA DE GANGA! MÍNIMO HISTÓRICO ALCANZADO** 🚨",
        "embeds": [{
            "title": titulo,
            "description": "El bot detectó el precio más bajo registrado hasta ahora. ¡Ideal para reventar la tarjeta!",
            "color": 3066993, # Verde oscuro
            "fields": [
                {"name": "💰 Precio Actual", "value": precio_clp, "inline": True},
                {"name": "📉 Mejor Precio Anterior", "value": minimo_clp, "inline": True}
            ]
        }]
    }

    respuesta = requests.post(WEBHOOK_URL, json=mensaje)
    if respuesta.status_code in [200, 204]:
        print(f"✅ Alerta enviada a Discord por {titulo}")
    else:
        print(f"❌ Error al enviar alerta: {respuesta.status_code}")

def obtener_conexion():
    """Crea la conexión a la base de datos PostgreSQL en Supabase"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conn
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def ejecutar_etl():
    print("Iniciando pipeline ETL...")
    
    # -----------------------------------------
    # 1. EXTRACT (Extracción Blindada Anti-Bot)
    # -----------------------------------------
    try:
        # Creamos un scraper que simula un navegador real para saltar protecciones
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # Usamos el scraper en vez de requests normal
        respuesta = scraper.get(URL_BUSCALIBRE)
        respuesta.raise_for_status()
        
    except Exception as e:
        print(f"Error al conectar con Buscalibre: {e}")
        return
        
    soup = BeautifulSoup(respuesta.text, 'html.parser')
    
    # IMPORTANTE: Si la web de Buscalibre cambió, estas clases podrían ser distintas.
    # Si te detecta 0 libros, revisa cómo tenías estas líneas en tu scraper original.
    libros_html = soup.find_all('div', class_='producto')
    
   # -----------------------------------------
    # 2. TRANSFORM (Transformación)
    # -----------------------------------------
    libros_procesados = []
    for libro in libros_html:
        try:
            # NUEVO: Buscamos el título en la nueva etiqueta div
            caja_titulo = libro.find('div', class_='titulo')
            if not caja_titulo:
                continue
            
            titulo_raw = caja_titulo.text
            
            # NUEVO: Buscamos el precio en la nueva clase precioAhora
            caja_precio = libro.find('div', class_='precioAhora')
            
            # Si el libro está Agotado, no tendrá caja de precioAhora, así que lo saltamos
            if not caja_precio:
                continue
                
            precio_raw = caja_precio.text
            estado_raw = "Disponible" 
            
            # Limpiamos los datos (quitamos espacios extra, saltos de línea y símbolos)
            titulo = titulo_raw.strip()
            precio_limpio = int(re.sub(r'[^\d]', '', precio_raw))
            
            libros_procesados.append({
                "titulo": titulo,
                "precio": precio_limpio,
                "estado": estado_raw
            })
        except AttributeError:
            # Si un libro tiene una estructura rara, lo saltamos
            continue

    print(f"Se encontraron {len(libros_procesados)} libros procesados correctamente.")
    # -----------------------------------------
    # 3. LOAD (Carga en Data Mart Kimball)
    # -----------------------------------------
    if not libros_procesados:
        print("No se extrajeron libros. Es probable que las etiquetas HTML de Buscalibre hayan cambiado.")
        return

    conn = obtener_conexion()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        hoy = datetime.now()
        
        # A. Cargar o recuperar la Dimensión Fecha (YYYYMMDD)
        id_fecha_hoy = int(hoy.strftime("%Y%m%d"))
        
        cursor.execute("SELECT id_fecha FROM dim_fecha WHERE id_fecha = %s", (id_fecha_hoy,))
        if not cursor.fetchone():
            # Si la fecha no existe, la insertamos
            cursor.execute("""
                INSERT INTO dim_fecha (id_fecha, fecha_exacta, anio, mes, dia)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_fecha_hoy, hoy.date(), hoy.year, hoy.month, hoy.day))
        
        # B. Iterar sobre cada libro procesado
        for libro in libros_procesados:
            titulo = libro["titulo"]
            precio_actual = libro["precio"]

            # Buscar si el libro ya existe en dim_libro
            cursor.execute("SELECT id_libro FROM dim_libro WHERE titulo = %s", (titulo,))
            resultado_libro = cursor.fetchone()
            
            if resultado_libro:
                id_libro = resultado_libro[0]
            else:
                # Si no existe, lo insertamos en dim_libro y obtenemos su nuevo ID
                cursor.execute("""
                    INSERT INTO dim_libro (titulo, estado)
                    VALUES (%s, %s) RETURNING id_libro
                """, (titulo, libro["estado"]))
                id_libro = cursor.fetchone()[0]
                print(f"Nuevo libro registrado en BD: {titulo}")
                
            # -------------------------------------------------------------
            # C. Lógica de Alertas Inteligentes (Discord)
            # -------------------------------------------------------------
            
            # 1. Buscar el precio más bajo histórico en la tabla de hechos
            cursor.execute("SELECT MIN(precio) FROM fact_precio WHERE id_libro = %s", (id_libro,))
            resultado_min = cursor.fetchone()
            
            # Si el libro ya tenía precios guardados, sacamos el mínimo. Si es nuevo, es None.
            precio_minimo_historico = resultado_min[0] if resultado_min[0] is not None else precio_actual
            
            # 2. Si el precio de hoy es menor o igual al histórico (y el libro no es nuevo), alertamos!
            if precio_actual <= precio_minimo_historico and resultado_min[0] is not None:
                enviar_alerta_discord(titulo, precio_actual, precio_minimo_historico)

            # -------------------------------------------------------------
            # D. Insertar el precio del día en la Tabla de Hechos
            # -------------------------------------------------------------
            cursor.execute("""
                INSERT INTO fact_precio (id_libro, id_fecha, precio)
                VALUES (%s, %s, %s)
            """, (id_libro, id_fecha_hoy, precio_actual))
            
            print(f"Precio registrado: {titulo} a ${precio_actual}")

        # Guardar los cambios (Commit) y cerrar la conexión
        conn.commit()
        print("ETL finalizado con éxito.")
        
    except Exception as e:
        print(f"Error durante la inserción en la base de datos: {e}")
        conn.rollback() # Si algo falla, deshace los cambios para no dejar datos a medias
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    ejecutar_etl()