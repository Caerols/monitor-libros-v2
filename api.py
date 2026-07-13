from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Cargar credenciales
load_dotenv()

# Inicializar la API
app = FastAPI(title="API Monitor de Libros")

# Configurar CORS (Vital para que tu frontend HTML pueda consumir esta API sin bloqueos de seguridad)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def obtener_conexion():
    """Crea la conexión a Supabase"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

@app.get("/api/historial")
def obtener_historial():
    """Endpoint que devuelve el historial de precios de todos los libros"""
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    # Consulta SQL profesional: Unimos la tabla de hechos con las dimensiones
    query = """
        SELECT 
            l.titulo, 
            f.fecha_exacta, 
            p.precio
        FROM fact_precio p
        JOIN dim_libro l ON p.id_libro = l.id_libro
        JOIN dim_fecha f ON p.id_fecha = f.id_fecha
        ORDER BY l.titulo, f.fecha_exacta;
    """
    
    cursor.execute(query)
    resultados = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Transformamos el resultado de SQL a una lista de diccionarios (JSON)
    datos = []
    for fila in resultados:
        datos.append({
            "titulo": fila[0],
            "fecha": str(fila[1]),
            "precio": fila[2]
        })
        
    return {"historial": datos}