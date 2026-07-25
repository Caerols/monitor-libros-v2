import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
import uvicorn
from pydantic import BaseModel
from typing import Optional

# --- IMPORTACIONES DE LA ARQUITECTURA ---
from src.adapters.database.connection import DatabasePool
from src.adapters.scrapers.buscalibre import BuscalibreScraper
from src.adapters.database.repository import LibroRepository
from src.adapters.discord.webhook import DiscordNotifier
from src.use_cases.process_books import GeneradorAlertasBuscalibre

# Cargar variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class ExpedienteLibro(BaseModel):
    titulo: str
    autor: str
    genero: Optional[str] = ""
    anio_publicacion: Optional[str] = ""
    editorial: Optional[str] = ""
    num_paginas: Optional[int] = 0
    palabras: Optional[int] = 0
    isbn: Optional[str] = ""
    observaciones: Optional[str] = ""
    estado_lectura: str = "No iniciado"
    calificacion: int = 0

# =====================================================================
# CAPA DE DATOS (DAL Aislada, Optimización en C mediante RealDictCursor)
# =====================================================================
class BotDatabaseOperations:
    """Encapsula todas las consultas SQL directas. Optimizada para bajo consumo de RAM."""
    
    @staticmethod
    def inicializar_tablas():
        """Ejecuta DDLs pesados una sola vez en el Cold Start."""
        crear_tabla_sql = """
        CREATE TABLE IF NOT EXISTS biblioteca_personal (
            id SERIAL PRIMARY KEY,
            titulo VARCHAR(255) NOT NULL,
            autor VARCHAR(255) NOT NULL,
            genero VARCHAR(100),
            anio_publicacion VARCHAR(20),
            editorial VARCHAR(150),
            num_paginas INT,
            palabras INT,
            isbn VARCHAR(50),
            observaciones TEXT,
            estado_lectura VARCHAR(50),
            calificacion INT,
            fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(crear_tabla_sql)
            conn.commit()

    @staticmethod
    def obtener_historial_api():
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # TO_CHAR delega el formateo de fecha a la BD, ahorrando CPU en Python
                query = """
                    SELECT l.titulo, TO_CHAR(f.fecha_exacta, 'YYYY-MM-DD') as fecha, p.precio
                    FROM fact_precio p
                    JOIN dim_libro l ON p.id_libro = l.id_libro
                    JOIN dim_fecha f ON p.id_fecha = f.id_fecha
                    ORDER BY l.titulo, f.fecha_exacta;
                """
                cursor.execute(query)
                return cursor.fetchall()

    @staticmethod
    def agregar_lista(link: str):
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = "INSERT INTO listas_monitoreo (url_lista) VALUES (%s) ON CONFLICT (url_lista) DO NOTHING;"
                cursor.execute(query, (link,))
            conn.commit()

    @staticmethod
    def obtener_ofertas():
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    WITH Minimos AS (
                        SELECT id_libro, MIN(precio) as min_historico FROM fact_precio GROUP BY id_libro
                    ),
                    UltimosPrecios AS (
                        SELECT p.id_libro, p.precio as precio_actual 
                        FROM fact_precio p
                        JOIN dim_fecha f ON p.id_fecha = f.id_fecha
                        WHERE f.fecha_exacta = (SELECT MAX(fecha_exacta) FROM dim_fecha)
                    )
                    SELECT l.titulo, u.precio_actual
                    FROM UltimosPrecios u
                    JOIN Minimos m ON u.id_libro = m.id_libro
                    JOIN dim_libro l ON u.id_libro = l.id_libro
                    WHERE u.precio_actual <= m.min_historico;
                """
                cursor.execute(query)
                return cursor.fetchall()

    @staticmethod
    def actualizar_ficha_lectura(titulo: str, autor: str, estado: str):
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO fichas_lectura (titulo, autor, estado_lectura) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (titulo) 
                    DO UPDATE SET estado_lectura = EXCLUDED.estado_lectura, 
                                  autor = COALESCE(EXCLUDED.autor, fichas_lectura.autor), 
                                  fecha_actualizacion = CURRENT_TIMESTAMP;
                """
                cursor.execute(query, (titulo, autor, estado))
            conn.commit()

    @staticmethod
    def obtener_estante():
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = "SELECT titulo, autor, estado_lectura FROM fichas_lectura ORDER BY fecha_actualizacion DESC;"
                cursor.execute(query)
                return cursor.fetchall()

    @staticmethod
    def consultar_precio(nombre_libro: str):
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT l.titulo, f.precio, l.precio_target, 
                           (SELECT MIN(precio) FROM fact_precio WHERE id_libro = l.id_libro) as precio_minimo
                    FROM dim_libro l
                    JOIN fact_precio f ON l.id_libro = f.id_libro
                    WHERE l.titulo ILIKE %s
                    ORDER BY f.id_fecha DESC, f.hora_monitoreo DESC
                    LIMIT 1;
                """
                cursor.execute(query, (f"%{nombre_libro}%",))
                return cursor.fetchone()

    @staticmethod
    def agregar_libro(titulo: str, link: str):
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO dim_libro (titulo, url_buscalibre, estado)
                    VALUES (%s, %s, 'Activo')
                    ON CONFLICT (url_buscalibre) DO UPDATE SET titulo = EXCLUDED.titulo;
                """
                cursor.execute(query, (titulo, link))
            conn.commit()

    @staticmethod
    def fijar_target(precio: int, nombre_libro: str) -> int:
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = "UPDATE dim_libro SET precio_target = %s WHERE titulo ILIKE %s;"
                cursor.execute(query, (precio, f"%{nombre_libro}%"))
                rowcount = cursor.rowcount
            conn.commit()
            return rowcount

    @staticmethod
    def obtener_resumen():
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    WITH PreciosActuales AS (
                        SELECT l.id_libro, l.titulo, f.precio AS precio_actual,
                               RANK() OVER(PARTITION BY l.id_libro ORDER BY f.id_fecha DESC, f.hora_monitoreo DESC) as rank_fecha
                        FROM dim_libro l
                        JOIN fact_precio f ON l.id_libro = f.id_libro
                    ),
                    PreciosMinimos AS (
                        SELECT id_libro, MIN(precio) AS precio_minimo FROM fact_precio GROUP BY id_libro
                    )
                    SELECT pa.titulo, pa.precio_actual, pm.precio_minimo
                    FROM PreciosActuales pa
                    JOIN PreciosMinimos pm ON pa.id_libro = pm.id_libro
                    WHERE pa.rank_fecha = 1
                    ORDER BY pa.precio_actual ASC
                    LIMIT 3;
                """
                cursor.execute(query)
                return cursor.fetchall()

    @staticmethod
    def obtener_catalogo_biblioteca():
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT 
                        b.titulo, COALESCE(a.nombre, 'Autor Desconocido') as autor, 
                        COALESCE(g.nombre, 'Sin clasificar') as genero, b.editorial,
                        b.num_paginas, b.isbn, b.formato, b.estado_lectura,
                        b.calificacion, b.observaciones, c.precio_pagado,
                        c.tienda, TO_CHAR(c.fecha_compra, 'DD-Mon-YYYY') as fecha_compra
                    FROM bib_libros b
                    LEFT JOIN bib_autores a ON b.id_autor = a.id_autor
                    LEFT JOIN bib_generos g ON b.id_genero = g.id_genero
                    LEFT JOIN bib_compras c ON b.id_bib = c.id_bib
                    ORDER BY b.fecha_agregado DESC;
                """
                cursor.execute(query)
                return cursor.fetchall()

    @staticmethod
    def guardar_expediente(libro: ExpedienteLibro):
        """Maneja la inserción del libro optimizando la apertura/cierre de cursores."""
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cur:
                insert_sql = """
                INSERT INTO biblioteca_personal 
                (titulo, autor, genero, anio_publicacion, editorial, num_paginas, palabras, isbn, observaciones, estado_lectura, calificacion) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (
                    libro.titulo, libro.autor, libro.genero, libro.anio_publicacion, 
                    libro.editorial, libro.num_paginas, libro.palabras, libro.isbn, 
                    libro.observaciones, libro.estado_lectura, libro.calificacion
                )
                cur.execute(insert_sql, valores)
            conn.commit()

# =====================================================================
# SISTEMA DE SOPORTE VITAL Y API CENTRAL (FastAPI)
# =====================================================================
app = FastAPI(title="Matriz Central: Bot & API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "La Bibliotecaria está en línea y vigilando los archivos."}

@app.get("/api/biblioteca/catalogo")
def obtener_catalogo_api():
    try:
        return {"catalogo": BotDatabaseOperations.obtener_catalogo_biblioteca()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/historial")
def obtener_historial():
    try:
        return {"historial": BotDatabaseOperations.obtener_historial_api()}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/biblioteca/guardar")
def guardar_libro_api(libro: ExpedienteLibro):
    """Endpoint limpio (Controller). La lógica de datos se movió a la DAL."""
    try:
        BotDatabaseOperations.guardar_expediente(libro)
        return {"exito": True, "mensaje": "Expediente guardado exitosamente"}
    except Exception as e:
        print(f"Error persistiendo libro: {e}")
        return {"exito": False, "detail": "Error interno en la base de datos."}

async def start_api():
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# =====================================================================
# CONFIGURACIÓN DEL BOT DE DISCORD
# =====================================================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'❄️ {bot.user.name} ha iniciado el sistema. Archivos en orden.')

@bot.command()
async def ayuda(ctx):
    mensaje = (
        "📜 **Manual de Usuario del Archivo** 📜\n"
        "Soy la encargada de tu catálogo. Por favor, revisa estas directrices:\n\n"
        "**📚 Gestión de Lectura:**\n"
        "🔹 `!estante` - Muestra tu ficha con los libros leídos y pendientes.\n"
        "🔹 `!leido [título] | [autor]` - Registra un libro terminado (el autor es opcional).\n"
        "🔹 `!pendiente [título] | [autor]` - Añade un libro a tu lista de espera.\n"
        "🔹 `!terminar [título]` - Mueve un título de 'pendientes' a 'leídos'.\n\n"
        "**⚙️ Monitoreo de Mercado:**\n"
        "🔹 `!lista [link]` - Agrega una nueva lista compartida al escáner central.\n"
        "🔹 `!agregar [link] | [título]` - Ingresa un enlace individual y su título.\n"
        "🔹 `!target [precio] [título]` - Fija una alerta de presupuesto estricta.\n"
        "🔹 `!precio [título]` - Activa mi radar de precios.\n"
        "🔹 `!resumen` - Muestra el top 3 de mejores ofertas del día.\n"
        "🔹 `!ofertas` - Consulta qué ejemplares han tocado su mínimo histórico.\n\n"
        "**🛠️ Sistema:**\n"
        "🔹 `!escanear` - Fuerza al scraper a realizar un barrido inmediato.\n"
        "🔹 `!ping` - Verifica latencia."
    )
    await ctx.send(mensaje)

@bot.command()
async def lista(ctx, link: str):
    if "buscalibre" not in link.lower():
        await ctx.send("❌ Ese no parece un enlace válido de Buscalibre.")
        return
    try:
        await asyncio.to_thread(BotDatabaseOperations.agregar_lista, link)
        await ctx.send("🔗 Lista compartida añadida con éxito.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command()
async def escanear(ctx):
    await ctx.send("⚙️ Protocolo de escaneo manual activado. Despertando al scraper...")
    try:
        def ejecutar_scraping():
            repo = LibroRepository()
            urls = repo.obtener_listas_activas()
            if urls:
                # Instanciación Lazy para que el GC (Garbage Collector) las destruya al terminar
                app_orquestador = GeneradorAlertasBuscalibre(BuscalibreScraper(), repo, DiscordNotifier())
                app_orquestador.ejecutar(urls)

        await asyncio.to_thread(ejecutar_scraping)
        await ctx.send("✅ Barrido de mercado completado.")
    except Exception as e:
        await ctx.send(f"⚠️ El scraper falló. Código de error: {str(e)}")

@bot.command()
async def saludar(ctx):
    await ctx.send("Saludos. Soy la encargada del archivo. Mantengamos las interacciones eficientes. 👓")

@bot.command()
async def ofertas(ctx):
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_ofertas)
        if not resultados:
            await ctx.send("No hay fluctuaciones relevantes hoy; ningún ejemplar está en su mínimo histórico.")
        else:
            mensaje = "Revisión completada. Los siguientes ejemplares han tocado su piso histórico:\n\n"
            for fila in resultados:
                precio_formateado = f"${int(fila[1]):,}".replace(",", ".")
                mensaje += f"📖 **{fila[0]}** — {precio_formateado}\n"
            await ctx.send(mensaje)
    except Exception as e:
        await ctx.send(f"Se ha producido un error de lectura: {str(e)}.")

@bot.command(aliases=['leído'])
async def leido(ctx, *, texto: str):
    partes = texto.split("|", 1)
    titulo = partes[0].strip()
    autor = partes[1].strip() if len(partes) > 1 else None 
    try:
        await asyncio.to_thread(BotDatabaseOperations.actualizar_ficha_lectura, titulo, autor, 'leido')
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"📄 Expediente actualizado. **'{titulo}'**{texto_autor} ha sido clasificado como completado.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía: {e}")

@bot.command()
async def pendiente(ctx, *, texto: str):
    partes = texto.split("|", 1)
    titulo = partes[0].strip()
    autor = partes[1].strip() if len(partes) > 1 else None
    try:
        await asyncio.to_thread(BotDatabaseOperations.actualizar_ficha_lectura, titulo, autor, 'pendiente')
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"🖋️ **'{titulo}'**{texto_autor} está ahora en tu lista de espera.")
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía en el registro: {e}")

@bot.command()
async def estante(ctx):
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_estante)
        mensaje = "📋 **Reporte de Estado: Ficha de Lectura**\n\n✅ **Material Completado:**\n"
        
        leidos = [f"  - **{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "") for f in resultados if f['estado_lectura'] == 'leido']
        pendientes = [f"  - **{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "") for f in resultados if f['estado_lectura'] == 'pendiente']

        mensaje += "\n".join(leidos) if leidos else "  *Registro vacío.*"
        mensaje += "\n\n⏳ **Material Pendiente:**\n"
        mensaje += "\n".join(pendientes) if pendientes else "  *No hay elementos en espera.*"
        
        await ctx.send(mensaje)
    except Exception as e:
        await ctx.send(f"⚠️ Error al leer los archivos: {e}")

@bot.command()
async def precio(ctx, *, nombre_libro: str):
    try:
        resultado = await asyncio.to_thread(BotDatabaseOperations.consultar_precio, nombre_libro)
        if resultado:
            titulo, precio_actual = resultado['titulo'], resultado['precio']
            target, minimo = resultado['precio_target'], resultado['precio_minimo']
            
            mensaje = f"📊 **Consulta de Archivo:**\nEl último valor para **'{titulo}'** es **${precio_actual}**.\n📉 *Mínimo histórico: ${minimo}*\n"
            if target:
                if precio_actual <= target:
                    mensaje += f"\n🎯 ¡Atención! Precio bajo presupuesto (${target}). Autorizo la compra."
                else:
                    mensaje += f"\n⏳ El valor supera tu presupuesto de ${target}. Te aconsejo esperar."
            await ctx.send(mensaje)
        else:
            await ctx.send(f"⚠️ No encontré registros recientes para **'{nombre_libro}'**.")
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía al consultar: {e}")

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong. Latencia: {round(bot.latency * 1000)}ms.")

@bot.command()
async def agregar(ctx, *, texto: str):
    if "|" not in texto:
        await ctx.send("⚠️ Formato: `!agregar https://www.buscalibre.cl/... | 1984`")
        return
        
    partes = texto.split("|", 1)
    link, titulo = partes[0].strip(), partes[1].strip()

    if "buscalibre" not in link.lower():
        await ctx.send("❌ Ese enlace no pertenece al catálogo oficial.")
        return

    try:
        await asyncio.to_thread(BotDatabaseOperations.agregar_libro, titulo, link)
        await ctx.send(f"🔗 **'{titulo}'** añadido al catálogo de rastreo.")
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía en el guardado: {e}")

@bot.command()
async def target(ctx, precio: int, *, nombre_libro: str):
    try:
        rowcount = await asyncio.to_thread(BotDatabaseOperations.fijar_target, precio, nombre_libro)
        if rowcount > 0:
            await ctx.send(f"🎯 Alerta estricta para **'{nombre_libro}'** fijada a **${precio}**.")
        else:
            await ctx.send(f"⚠️ No encontré **'{nombre_libro}'** en mi registro. Agrégalo con `!agregar`.")
    except Exception as e:
        await ctx.send(f"⚠️ Error de sistema: {e}")

@target.error
async def target_error(ctx, error):
    if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
        await ctx.send("⚠️ Sintaxis incorrecta. Ejemplo: `!target 20000 1984`.")

@bot.command()
async def resumen(ctx):
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_resumen)
        if not resultados:
            await ctx.send("🗂️ Tu tabla de hechos no tiene registros recientes.")
            return

        mensaje = "📊 **Top 3 Libros Más Baratos**\n\n"
        medallas = ["🥇", "🥈", "🥉"]
        
        for i, fila in enumerate(resultados):
            analisis = "¡Mínimo Histórico! Momento óptimo para adquirirlo." if fila['precio_actual'] <= fila['precio_minimo'] else f"El mínimo registrado es ${fila['precio_minimo']}."
            mensaje += f"{medallas[i]} **{fila['titulo']}** - **${fila['precio_actual']}**\n  └ *{analisis}*\n\n"
            
        await ctx.send(mensaje)
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía al cruzar expedientes: {e}")

# =====================================================================
# INICIO DEL SISTEMA (Ejecución Cooperativa Optimizada)
# =====================================================================
async def main():
    # Inicializar Base de Datos de manera segura
    DatabasePool.initialize()
    # Ejecutamos los DDL pesados 1 sola vez durante el cold start (Ahorro crítico de CPU)
    BotDatabaseOperations.inicializar_tablas()
    
    # Iniciar bot y API
    async with bot:
        bot.loop.create_task(start_api())
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error: No se detectó el DISCORD_TOKEN.")
    else:
        asyncio.run(main())