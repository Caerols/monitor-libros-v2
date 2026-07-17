import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
import uvicorn

# --- IMPORTACIONES DE LA ARQUITECTURA ---
from src.config.settings import config
from src.adapters.database.connection import DatabasePool
from src.adapters.scrapers.buscalibre import BuscalibreScraper
from src.adapters.database.repository import LibroRepository
from src.adapters.discord.webhook import DiscordNotifier
from src.use_cases.process_books import GeneradorAlertasBuscalibre

# Cargar variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# =====================================================================
# CAPA DE DATOS (Aislada de los comandos de Discord)
# =====================================================================
class BotDatabaseOperations:
    """Encapsula todas las consultas SQL directas que el Bot y la API necesitan."""
    
    @staticmethod
    def obtener_historial_api():
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT l.titulo, f.fecha_exacta, p.precio
                    FROM fact_precio p
                    JOIN dim_libro l ON p.id_libro = l.id_libro
                    JOIN dim_fecha f ON p.id_fecha = f.id_fecha
                    ORDER BY l.titulo, f.fecha_exacta;
                """
                cursor.execute(query)
                return [{"titulo": f[0], "fecha": str(f[1]), "precio": f[2]} for f in cursor.fetchall()]

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
                conn.commit()
                return cursor.rowcount

    @staticmethod
    def obtener_resumen():
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    WITH PreciosActuales AS (
                        SELECT 
                            l.id_libro,
                            l.titulo,
                            f.precio AS precio_actual,
                            RANK() OVER(PARTITION BY l.id_libro ORDER BY f.id_fecha DESC, f.hora_monitoreo DESC) as rank_fecha
                        FROM dim_libro l
                        JOIN fact_precio f ON l.id_libro = f.id_libro
                    ),
                    PreciosMinimos AS (
                        SELECT id_libro, MIN(precio) AS precio_minimo
                        FROM fact_precio
                        GROUP BY id_libro
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
        """Extrae todos los libros de la biblioteca personal cruzando las tablas relacionales."""
        with DatabasePool.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT 
                        b.titulo, 
                        COALESCE(a.nombre, 'Autor Desconocido') as autor, 
                        COALESCE(g.nombre, 'Sin clasificar') as genero,
                        b.editorial,
                        b.num_paginas,
                        b.isbn,
                        b.formato,
                        b.estado_lectura,
                        b.calificacion,
                        b.observaciones,
                        c.precio_pagado,
                        c.tienda,
                        TO_CHAR(c.fecha_compra, 'DD-Mon-YYYY') as fecha_compra
                    FROM bib_libros b
                    LEFT JOIN bib_autores a ON b.id_autor = a.id_autor
                    LEFT JOIN bib_generos g ON b.id_genero = g.id_genero
                    LEFT JOIN bib_compras c ON b.id_bib = c.id_bib
                    ORDER BY b.fecha_agregado DESC;
                """
                cursor.execute(query)
                return cursor.fetchall()
            
    @staticmethod
    def buscar_info_libro(titulo: str, autor: str):
        """Consulta Google Books API para completar la ficha técnica."""
        url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{titulo}+inauthor:{autor}&maxResults=1"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if 'items' not in data:
                return None
            
            info = data['items'][0]['volumeInfo']
            
            # Cálculo estimado de palabras: promedio 250 palabras por página
            paginas = info.get('pageCount', 0)
            
            return {
                "titulo": info.get('title'),
                "editorial": info.get('publisher', 'Desconocido'),
                "anio": str(info.get('publishedDate', '0000'))[:4],
                "paginas": paginas,
                "palabras": paginas * 250, # Estimación estándar
                "resumen": info.get('description', 'Sin resumen disponible.'),
                "isbn": info.get('industryIdentifiers', [{}])[0].get('identifier', 'N/A')
            }
        except Exception:
            return None

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
    """Endpoint que alimenta la cuadrícula de Flip Cards del frontend"""
    try:
        datos = BotDatabaseOperations.obtener_catalogo_biblioteca()
        return {"catalogo": datos}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/biblioteca/investigar")
def investigar_libro_api(titulo: str, autor: str):
    """Endpoint para que el frontend consulte la API de Google Books"""
    try:
        datos = BotDatabaseOperations.buscar_info_libro(titulo, autor)
        if datos:
            return {"exito": True, "datos": datos}
        else:
            return {"exito": False, "error": "No encontré registros en los archivos mundiales para ese título y autor."}
    except Exception as e:
        return {"exito": False, "error": str(e)}

@app.get("/api/historial")
def obtener_historial():
    """Endpoint que devuelve el historial de precios para el frontend"""
    try:
        datos = BotDatabaseOperations.obtener_historial_api()
        return {"historial": datos}
    except Exception as e:
        return {"error": str(e)}

async def start_api():
    """Lanza FastAPI de manera cooperativa dentro del Event Loop de Discord"""
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
    """Muestra la lista de comandos disponibles actualizados"""
    mensaje = (
        "📜 **Manual de Usuario del Archivo** 📜\n"
        "Soy la encargada de tu catálogo. Por favor, revisa estas directrices y mantén los formatos correctos para no desordenar la base de datos:\n\n"
        "**📚 Gestión de Lectura:**\n"
        "🔹 `!estante` - Muestra tu ficha con los libros leídos y pendientes.\n"
        "🔹 `!leido [título] | [autor]` - Registra un libro terminado (el autor es opcional).\n"
        "🔹 `!pendiente [título] | [autor]` - Añade un libro a tu lista de espera.\n"
        "🔹 `!terminar [título]` - Mueve un título de 'pendientes' a 'leídos'.\n\n"
        "**⚙️ Monitoreo de Mercado (Buscalibre):**\n"
        "🔹 `!lista [link]` - Agrega una nueva lista compartida al escáner central.\n"
        "🔹 `!agregar [link] | [título]` - Ingresa un enlace individual y su título.\n"
        "🔹 `!target [precio en números] [título]` - Fija una alerta de presupuesto estricta.\n"
        "🔹 `!precio [título]` - Activa mi radar de precios en la matriz.\n"
        "🔹 `!resumen` - Muestra el top 3 de mejores ofertas del día.\n"
        "🔹 `!ofertas` - Consulta qué ejemplares del archivo han tocado su mínimo histórico.\n\n"
        "**🛠️ Sistema:**\n"
        "🔹 `!escanear` - Fuerza al scraper a realizar un barrido de mercado inmediato.\n"
        "🔹 `!saludar` - Inicia el protocolo de saludo básico.\n"
        "🔹 `!ping` - Verifica el estado de latencia y si mis sistemas están en línea.\n\n"
        "*Intenta memorizar los comandos... aunque si los olvidas, supongo que puedes volver a preguntarme. Solo trata de no consultar a deshora, los sistemas también necesitan reposo.*"
    )
    await ctx.send(mensaje)

@bot.command()
async def lista(ctx, link: str):
    """Agrega una nueva lista compartida de Buscalibre al scraper"""
    if "buscalibre" not in link.lower():
        await ctx.send("❌ Ese no parece un enlace válido de Buscalibre.")
        return
    try:
        await asyncio.to_thread(BotDatabaseOperations.agregar_lista, link)
        await ctx.send("🔗 Lista compartida añadida con éxito a los archivos. El scraper la revisará en su próxima ronda.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command()
async def escanear(ctx):
    """Fuerza al scraper a ejecutarse en este instante usando la nueva arquitectura"""
    await ctx.send("⚙️ Protocolo de escaneo manual activado. Despertando al scraper... ten paciencia, esto tomará unos minutos.")
    
    try:
        def ejecutar_scraping():
            scraper = BuscalibreScraper()
            repo = LibroRepository()
            notifier = DiscordNotifier()
            app_orquestador = GeneradorAlertasBuscalibre(scraper, repo, notifier)
            urls = repo.obtener_listas_activas()
            if urls:
                app_orquestador.ejecutar(urls)

        await asyncio.to_thread(ejecutar_scraping)
        await ctx.send("✅ Barrido de mercado completado. Los archivos han sido actualizados.\n"
                       "Si hubo bajones históricos de precio, deberías ver las alertas arriba. O puedes usar `!resumen`.")
            
    except Exception as e:
        await ctx.send("⚠️ El scraper encontró resistencia y falló en su tarea.\n"
                       f"Revisa los logs internos del sistema. Código de error: {str(e)}")

@bot.command()
async def saludar(ctx):
    mensaje = (
        "Saludos. Soy la encargada del archivo y la gestión de tu catálogo. 👓\n"
        "Mantengamos las interacciones breves y eficientes, por favor. \n"
        "...Aunque si tienes alguna duda, supongo que puedo ayudarte. Asegúrate de tener buena luz si vas a leer hasta tarde."
    )
    await ctx.send(mensaje)

@bot.command()
async def ofertas(ctx):
    """Solicita a la Bibliotecaria un informe de los precios mínimos actuales"""
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_ofertas)
        
        if not resultados:
            await ctx.send("He consultado el archivo. No hay fluctuaciones relevantes hoy; ningún ejemplar está en su mínimo histórico. \nPuedes volver a tus asuntos. ...Y no te frustres, los números del mercado siempre terminan bajando eventualmente.")
        else:
            mensaje = (
                "Revisión completada. Los siguientes ejemplares han tocado su piso histórico.\n"
                "Toma nota rápido, por favor. Tengo otros catálogos que ordenar:\n\n"
            )
            for fila in resultados:
                precio_formateado = f"${int(fila[1]):,}".replace(",", ".")
                mensaje += f"📖 **{fila[0]}** — {precio_formateado}\n"
            
            mensaje += "\nAhí lo tienes. Si vas a comprar alguno, espero que al menos te hagas el tiempo para leerlo con calma y no lo dejes juntando polvo en la repisa."
            await ctx.send(mensaje)
            
    except Exception as e:
        await ctx.send(f"Se ha producido un error de lectura en los registros: {str(e)}. \nCálmate, no es grave. Yo me encargaré de aislar el fallo para que los archivos no se corrompan.")

@bot.command(aliases=['leído'])
async def leido(ctx, *, texto: str):
    partes = texto.split("|", 1)
    titulo = partes[0].strip()
    autor = partes[1].strip() if len(partes) > 1 else None 

    try:
        await asyncio.to_thread(BotDatabaseOperations.actualizar_ficha_lectura, titulo, autor, 'leido')
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"📄 Expediente actualizado. **'{titulo}'**{texto_autor} ha sido clasificado como completado.\n"
                       f"Es un ritmo de lectura aceptable. Buen trabajo... sé que a veces cansa caleta mantener la concentración.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía al registrar el libro: {e}")

@bot.command()
async def pendiente(ctx, *, texto: str):
    partes = texto.split("|", 1)
    titulo = partes[0].strip()
    autor = partes[1].strip() if len(partes) > 1 else None

    try:
        await asyncio.to_thread(BotDatabaseOperations.actualizar_ficha_lectura, titulo, autor, 'pendiente')
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"🖋️ Ingresado a Supabase. **'{titulo}'**{texto_autor} está ahora en tu lista de espera.\n"
                       f"Procura no acumular demasiados títulos. Yo me encargaré de vigilar que no gastes de más cuando decidas comprarlo.")
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía en el registro: {e}")

@bot.command()
async def estante(ctx):
    """Muestra tu estantería completa leyendo desde Supabase"""
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_estante)
        mensaje = "📋 **Reporte de Estado: Ficha de Lectura**\n\n"
        
        leidos = [f"**{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "") for f in resultados if f['estado_lectura'] == 'leido']
        pendientes = [f"**{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "") for f in resultados if f['estado_lectura'] == 'pendiente']

        mensaje += "✅ **Material Completado:**\n"
        if not leidos:
            mensaje += "  *Registro vacío.*\n"
        else:
            for libro in leidos:
                mensaje += f"  - {libro}\n"
                
        mensaje += "\n⏳ **Material Pendiente:**\n"
        if not pendientes:
            mensaje += "  *No hay elementos en espera. Orden perfecto.*\n"
        else:
            for libro in pendientes:
                mensaje += f"  - {libro}\n"

        await ctx.send(mensaje)
    except Exception as e:
        await ctx.send(f"⚠️ Error al leer los archivos: {e}")

@bot.command()
async def precio(ctx, *, nombre_libro: str):
    try:
        resultado = await asyncio.to_thread(BotDatabaseOperations.consultar_precio, nombre_libro)
        if resultado:
            titulo = resultado['titulo']
            precio_actual = resultado['precio']
            target = resultado['precio_target']
            minimo = resultado['precio_minimo']
            
            mensaje = f"📊 **Consulta de Archivo:**\nEl último valor registrado para **'{titulo}'** es de **${precio_actual}**.\n"
            mensaje += f"📉 *Mínimo histórico detectado: ${minimo}*\n"
            
            if target:
                if precio_actual <= target:
                    mensaje += f"\n🎯 ¡Atención! El precio actual está por debajo de tu presupuesto estricto (${target}). Autorizo la compra."
                else:
                    mensaje += f"\n⏳ El valor aún supera tu presupuesto de ${target}. Te aconsejo esperar."
            
            await ctx.send(mensaje)
        else:
            await ctx.send(f"⚠️ Búsqueda fallida. No encontré registros de precios recientes para **'{nombre_libro}'**.\n"
                           f"Asegúrate de haberlo agregado al catálogo y de que el scraper haya finalizado su barrido.")
            
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía al consultar los expedientes: {e}")

@bot.command()
async def ping(ctx):
    latencia = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong. Conexión estable. Latencia: {latencia}ms.\n"
                   f"Estoy en línea y monitoreando el archivo. Todo en orden.")

@bot.command()
async def agregar(ctx, *, texto: str):
    if "|" not in texto:
        await ctx.send("⚠️ Error de formato. Necesito el enlace y el título separados por el símbolo `|`.\n"
                       "Ejemplo: `!agregar https://www.buscalibre.cl/... | 1984`")
        return
        
    partes = texto.split("|", 1)
    link = partes[0].strip()
    titulo = partes[1].strip()

    if "buscalibre" not in link.lower():
        await ctx.send("❌ Error de formato. Ese enlace no pertenece al catálogo oficial que monitoreo.\n"
                       "Asegúrate de enviarme un link válido, por favor. No indexo basura en los archivos.")
        return

    try:
        await asyncio.to_thread(BotDatabaseOperations.agregar_libro, titulo, link)
        await ctx.send(f"🔗 Enlace recibido y validado en la matriz central.\n"
                       f"He añadido **'{titulo}'** al catálogo de rastreo. El scraper lo revisará a medianoche.\n"
                       f"Estaré atenta a sus fluctuaciones... no te preocupes, yo me encargo de que no te estafen.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía en el guardado: {e}")

@bot.command()
async def target(ctx, precio: int, *, nombre_libro: str):
    try:
        rowcount = await asyncio.to_thread(BotDatabaseOperations.fijar_target, precio, nombre_libro)
        
        if rowcount > 0:
            await ctx.send(f"🎯 Parámetro establecido. He fijado una alerta estricta para **'{nombre_libro}'** a **${precio}**.\n"
                           f"Solo te notificaré si el valor cae por debajo de esa cifra. Puedes descansar, yo mantendré la vigilancia por ti.")
        else:
            await ctx.send(f"⚠️ Revisión fallida. No encontré **'{nombre_libro}'** en mi registro de monitoreo (dim_libro).\n"
                           f"Asegúrate de haberlo ingresado primero con el comando `!agregar`.")
    except Exception as e:
        await ctx.send(f"⚠️ Error de sistema: {e}")

@target.error
async def target_error(ctx, error):
    if isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Error de sintaxis. El formato correcto requiere un número primero.\n"
                       "Ejemplo: `!target 20000 Tokio Blues`. Inténtalo de nuevo, por favor.")

@bot.command()
async def resumen(ctx):
    await ctx.send("⚙️ Procesando solicitud... cruzando la tabla de hechos con las dimensiones. Dame un segundo.")
    
    try:
        resultados = await asyncio.to_thread(BotDatabaseOperations.obtener_resumen)
        
        if not resultados:
            await ctx.send("🗂️ Los archivos están vacíos. Tu tabla de hechos no tiene registros recientes.")
            return

        mensaje = "📊 **Reporte de Mercado: Top 3 Libros Más Baratos**\n\n"
        medallas = ["🥇", "🥈", "🥉"]
        
        for i, fila in enumerate(resultados):
            titulo = fila['titulo']
            precio_actual = fila['precio_actual']
            precio_historico = fila['precio_minimo']
            
            if precio_actual <= precio_historico:
                analisis = "¡Mínimo Histórico! Es el momento óptimo para adquirirlo."
            else:
                analisis = f"El valor histórico más bajo registrado es ${precio_historico}."
                
            mensaje += f"{medallas[i]} **{titulo}** - **${precio_actual}**\n   └ *{analisis}*\n\n"
            
        mensaje += "*Nota: Análisis de dimensiones completado. Usa esta información sabiamente; no me gusta verte gastar plata de más en cosas que puedes conseguir baratas.*"
        await ctx.send(mensaje)

    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía al cruzar los expedientes: {e}")



# =====================================================================
# INICIO DEL SISTEMA (Ejecución Cooperativa)
# =====================================================================
async def main():
    # Inicializar Base de Datos de manera segura
    DatabasePool.initialize()
    
    # Iniciar el bot y la API de manera paralela dentro del mismo Event Loop
    async with bot:
        bot.loop.create_task(start_api())
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error de sistema: No se detectó el DISCORD_TOKEN en las variables de entorno.")
    else:
        # Aquí inicia la orquestación principal
        asyncio.run(main())