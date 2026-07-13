import os
import re
import requests
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# --- CONFIGURACIÓN ---
URL_BUSCALIBRE = "https://www.buscalibre.cl/v2/por-comprar_3413286_l.html"

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
    # 1. EXTRACT (Extracción)
    # -----------------------------------------
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        respuesta = requests.get(URL_BUSCALIBRE, headers=headers)
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
            # Buscar si el libro ya existe en dim_libro
            cursor.execute("SELECT id_libro FROM dim_libro WHERE titulo = %s", (libro["titulo"],))
            resultado_libro = cursor.fetchone()
            
            if resultado_libro:
                id_libro = resultado_libro[0]
            else:
                # Si no existe, lo insertamos en dim_libro y obtenemos su nuevo ID
                cursor.execute("""
                    INSERT INTO dim_libro (titulo, estado)
                    VALUES (%s, %s) RETURNING id_libro
                """, (libro["titulo"], libro["estado"]))
                id_libro = cursor.fetchone()[0]
                print(f"Nuevo libro registrado en BD: {libro['titulo']}")
                
            # C. Insertar el precio del día en la Tabla de Hechos (fact_precio)
            cursor.execute("""
                INSERT INTO fact_precio (id_libro, id_fecha, precio)
                VALUES (%s, %s, %s)
            """, (id_libro, id_fecha_hoy, libro["precio"]))
            
            print(f"Precio registrado: {libro['titulo']} a ${libro['precio']}")

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