import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
from fastapi import FastAPI
import uvicorn
import threading

# Cargar el token desde tu archivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- SISTEMA DE SOPORTE VITAL (KEEP-ALIVE) ---
app = FastAPI()

@app.get("/")
def home():
    return {"status": "La Bibliotecaria está en línea y vigilando los archivos."}

def run_api():
    # Las plataformas Cloud asignan el puerto dinámicamente
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

def mantener_vivo():
    hilo = threading.Thread(target=run_api)
    hilo.start()

# --- CONEXIÓN A BASE DE DATOS ---
def conectar_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '6543') # <--- Ajustado a tu puerto
        )
        return conn
    except Exception as e:
        print(f"❌ Error al conectar con Supabase: {e}")
        return None

intents = discord.Intents.default()
intents.message_content = True

# IMPORTANTE: Desactivamos el 'help' por defecto de Discord para poner el nuestro
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)



@bot.event
async def on_ready():
    print(f'❄️ {bot.user.name} ha iniciado el sistema. Archivos en orden.')

@bot.command()
async def ayuda(ctx):
    """Muestra la lista de comandos disponibles actualizados"""
    mensaje = (
        "📜 **Manual de Usuario de la Biblioteca** 📜\n"
        "Soy tu asistente de archivo. Aquí tienes las directrices para interactuar conmigo:\n\n"
        "**📚 Gestión de Lectura:**\n"
        "🔹 `!estante` - Muestra tu ficha con los libros leídos y pendientes.\n"
        "🔹 `!leido [título] | [autor]` - Registra un libro terminado (el autor es opcional).\n"
        "🔹 `!pendiente [título] | [autor]` - Añade un libro a tu lista de espera.\n"
        "🔹 `!terminar [título]` - Mueve un título de 'pendientes' a 'leídos'.\n\n"
        "**⚙️ Monitoreo de Mercado (Buscalibre):**\n"
        "🔹 `!lista [link]` - Agrega una nueva lista compartida al escáner central.\n"
        "🔹 `!agregar [link] | [título]` - Ingresa un enlace individual y su título a la base de datos.\n"
        "🔹 `!target [precio en números] [título]` - Fija una alerta de presupuesto estricta.\n"
        "🔹 `!precio [título]` - Activa mi radar de precios en la base de datos central.\n"
        "🔹 `!resumen` - Muestra el top 3 de mejores ofertas del día.\n\n"
        "**🛠️ Sistema:**\n"
        "🔹 `!escanear` - Fuerza al scraper a realizar un barrido de mercado inmediato.\n"
        "🔹 `!saludar` - Inicia el protocolo de saludo básico.\n"
        "🔹 `!ping` - Verifica si mis sistemas están en línea.\n\n"
        "*Intenta no olvidar los formatos correctos... aunque si lo haces, siempre puedes volver a preguntarme. Aquí estaré para apañarte.*"
    )
    await ctx.send(mensaje)

@bot.command()
async def lista(ctx, link: str):
    """Agrega una nueva lista compartida de Buscalibre al scraper"""
    if "buscalibre" not in link.lower():
        await ctx.send("❌ Ese no parece un enlace válido de Buscalibre.")
        return
        
    conn = conectar_db()
    if not conn: return

    try:
        cursor = conn.cursor()
        query = "INSERT INTO listas_monitoreo (url_lista) VALUES (%s) ON CONFLICT (url_lista) DO NOTHING;"
        cursor.execute(query, (link,))
        conn.commit()
        await ctx.send("🔗 Lista compartida añadida con éxito a los archivos. El scraper la revisará en su próxima ronda.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")
    finally:
        cursor.close()
        conn.close()

@bot.command()
async def escanear(ctx):
    """Fuerza al scraper a ejecutarse en este instante"""
    await ctx.send("⚙️ Protocolo de escaneo manual activado. Despertando al scraper... ten paciencia, esto tomará unos minutos.")
    
    try:
        # Ejecuta tu archivo app-libros.py en segundo plano sin congelar el bot
        proceso = await asyncio.create_subprocess_exec(
            'python', 'app-libros.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proceso.communicate()
        
        if proceso.returncode == 0:
            await ctx.send("✅ Barrido de mercado completado. Los archivos han sido actualizados.\n"
                           "Si hubo bajones históricos de precio, deberías ver las alertas arriba. O puedes usar `!resumen`.")
        else:
            await ctx.send("⚠️ El scraper encontró resistencia y falló en su tarea.\n"
                           f"Revisa los logs internos del sistema. Código de error: {stderr.decode('utf-8')}")
            
    except Exception as e:
        await ctx.send(f"❌ Error crítico al intentar iniciar la secuencia de escaneo: {e}")

@bot.command()
async def saludar(ctx):
    mensaje = (
        "Saludos. Soy la encargada del archivo y la gestión de tu catálogo. 👓\n"
        "Mantengamos las interacciones breves y eficientes, por favor. \n"
        "...Aunque si tienes alguna duda, supongo que puedo ayudarte. Asegúrate de tener buena luz si vas a leer hasta tarde."
    )
    await ctx.send(mensaje)

@bot.command(aliases=['leído'])
async def leido(ctx, *, texto: str):
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de sistema: No hay conexión a los archivos centrales.")
        return
        
    # Separamos el título del autor si el usuario usó el símbolo "|"
    if "|" in texto:
        partes = texto.split("|", 1)
        titulo = partes[0].strip()
        autor = partes[1].strip()
    else:
        titulo = texto.strip()
        autor = None # Si no pone autor, queda en blanco

    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO fichas_lectura (titulo, autor, estado_lectura) 
            VALUES (%s, %s, 'leido')
            ON CONFLICT (titulo) 
            DO UPDATE SET estado_lectura = 'leido', autor = COALESCE(EXCLUDED.autor, fichas_lectura.autor), fecha_actualizacion = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (titulo, autor))
        conn.commit()
        
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"📄 Expediente actualizado. **'{titulo}'**{texto_autor} ha sido clasificado como completado.\n"
                       f"Es un ritmo de lectura aceptable. Buen trabajo... sé que a veces cansa caleta mantener la concentración.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía al registrar el libro: {e}")
    finally:
        cursor.close()
        conn.close()

@bot.command()
async def pendiente(ctx, *, texto: str):
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de sistema.")
        return
        
    if "|" in texto:
        partes = texto.split("|", 1)
        titulo = partes[0].strip()
        autor = partes[1].strip()
    else:
        titulo = texto.strip()
        autor = None

    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO fichas_lectura (titulo, autor, estado_lectura) 
            VALUES (%s, %s, 'pendiente')
            ON CONFLICT (titulo) 
            DO UPDATE SET estado_lectura = 'pendiente', autor = COALESCE(EXCLUDED.autor, fichas_lectura.autor), fecha_actualizacion = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (titulo, autor))
        conn.commit()
        
        texto_autor = f" (de {autor})" if autor else ""
        await ctx.send(f"🖋️ Ingresado a Supabase. **'{titulo}'**{texto_autor} está ahora en tu lista de espera.\n"
                       f"Procura no acumular demasiados títulos. Yo me encargaré de vigilar que no gastes de más cuando decidas comprarlo.")
    except Exception as e:
        await ctx.send(f"⚠️ Anomalía en el registro: {e}")
    finally:
        cursor.close()
        conn.close()

@bot.command()
async def estante(ctx):
    """Muestra tu estantería completa leyendo desde Supabase"""
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de conexión.")
        return
        
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT titulo, autor, estado_lectura FROM fichas_lectura ORDER BY fecha_actualizacion DESC;"
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        mensaje = "📋 **Reporte de Estado: Ficha de Lectura**\n\n"
        
        # Filtramos y armamos el texto incluyendo al autor si existe
        leidos = []
        for f in resultados:
            if f['estado_lectura'] == 'leido':
                texto_item = f"**{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "")
                leidos.append(texto_item)
                
        pendientes = []
        for f in resultados:
            if f['estado_lectura'] == 'pendiente':
                texto_item = f"**{f['titulo']}**" + (f" - *{f['autor']}*" if f['autor'] else "")
                pendientes.append(texto_item)

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
    finally:
        cursor.close()
        conn.close()

@bot.command()
async def precio(ctx, *, nombre_libro: str):
    """Busca el precio actual de un libro específico en la base de datos"""
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de sistema: No pude establecer conexión con la base de datos.")
        return

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Cruzamos la dimensión libro con la tabla de hechos para sacar el último precio
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
        resultado = cursor.fetchone()

        if resultado:
            titulo = resultado['titulo']
            precio_actual = resultado['precio']
            target = resultado['precio_target']
            minimo = resultado['precio_minimo']
            
            mensaje = f"📊 **Consulta de Archivo:**\nEl último valor registrado para **'{titulo}'** es de **${precio_actual}**.\n"
            mensaje += f"📉 *Mínimo histórico detectado: ${minimo}*\n"
            
            # La bibliotecaria analiza si te conviene comprarlo según tu target
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
    finally:
        cursor.close()
        conn.close()

async def ping(ctx):
    # Calcula el tiempo de respuesta del bot en milisegundos
    latencia = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong. Conexión estable. Latencia: {latencia}ms.\n"
                   f"Estoy en línea y monitoreando el archivo. Todo en orden.")

@bot.command()
async def agregar(ctx, *, texto: str):
    """Ej: !agregar https://buscalibre.cl/... | Obras de Helvétius"""
    # Verificamos que use la barra para separar
    if "|" not in texto:
        await ctx.send("⚠️ Error de formato. Necesito el enlace y el título separados por el símbolo `|`.\n"
                       "Ejemplo: `!agregar https://www.buscalibre.cl/... | 1984`")
        return
        
    partes = texto.split("|", 1)
    link = partes[0].strip()
    titulo = partes[1].strip()

    # Validación básica de seguridad
    if "buscalibre" not in link.lower():
        await ctx.send("❌ Error de formato. Ese enlace no pertenece al catálogo oficial que monitoreo.\n"
                       "Asegúrate de enviarme un link válido, por favor. No indexo basura en los archivos.")
        return
        
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de conexión con la base de datos principal.")
        return

    try:
        cursor = conn.cursor()
        # Insertamos en dim_libro. Si el título ya existe, solo actualizamos el link.
        query = """
            INSERT INTO dim_libro (titulo, url_buscalibre, estado)
            VALUES (%s, %s, 'Activo')
            ON CONFLICT (titulo) 
            DO UPDATE SET url_buscalibre = EXCLUDED.url_buscalibre;
        """
        cursor.execute(query, (titulo, link))
        conn.commit()
        
        await ctx.send(f"🔗 Enlace recibido y validado en la matriz central.\n"
                       f"He añadido **'{titulo}'** al catálogo de rastreo. El scraper lo revisará a medianoche.\n"
                       f"Estaré atenta a sus fluctuaciones... no te preocupes, yo me encargo de que no te estafen.")
    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía en el guardado: {e}")
    finally:
        cursor.close()
        conn.close()

@bot.command()
async def target(ctx, precio: int, *, nombre_libro: str):
    """Fija un precio objetivo. Ej: !target 15000 El mito de Sísifo"""
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de conexión con la base de datos principal.")
        return
        
    try:
        cursor = conn.cursor()
        # Buscamos el libro con ILIKE y los % para que funcione aunque no escriba el nombre perfecto
        query = "UPDATE dim_libro SET precio_target = %s WHERE titulo ILIKE %s;"
        cursor.execute(query, (precio, f"%{nombre_libro}%"))
        conn.commit()
        
        # Revisamos si el UPDATE realmente encontró el libro
        if cursor.rowcount > 0:
            await ctx.send(f"🎯 Parámetro establecido. He fijado una alerta estricta para **'{nombre_libro}'** a **${precio}**.\n"
                           f"Solo te notificaré si el valor cae por debajo de esa cifra. Puedes descansar, yo mantendré la vigilancia por ti.")
        else:
            await ctx.send(f"⚠️ Revisión fallida. No encontré **'{nombre_libro}'** en mi registro de monitoreo (dim_libro).\n"
                           f"Asegúrate de haberlo ingresado primero con el comando `!agregar`.")
    except Exception as e:
        await ctx.send(f"⚠️ Error de sistema: {e}")
    finally:
        cursor.close()
        conn.close()

@target.error
async def target_error(ctx, error):
    """Maneja el error si el usuario olvida poner el número"""
    if isinstance(error, commands.BadArgument) or isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Error de sintaxis. El formato correcto requiere un número primero.\n"
                       "Ejemplo: `!target 20000 Tokio Blues`. Inténtalo de nuevo, por favor.")
@bot.command()
async def resumen(ctx):
    """Muestra el top 3 de ofertas actuales cruzando el Data Mart"""
    await ctx.send("⚙️ Procesando solicitud... cruzando la tabla de hechos con las dimensiones. Dame un segundo.")
    
    conn = conectar_db()
    if not conn:
        await ctx.send("❌ Error de sistema: No pude establecer conexión con la base de datos principal. Revisaré mis cables más tarde.")
        return

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Consulta SQL avanzada para modelo en estrella (Star Schema)
        query = """
            WITH PreciosActuales AS (
                -- Obtenemos el precio más reciente de cada libro
                SELECT 
                    l.id_libro,
                    l.titulo,
                    f.precio AS precio_actual,
                    RANK() OVER(PARTITION BY l.id_libro ORDER BY f.id_fecha DESC, f.hora_monitoreo DESC) as rank_fecha
                FROM dim_libro l
                JOIN fact_precio f ON l.id_libro = f.id_libro
            ),
            PreciosMinimos AS (
                -- Calculamos el precio mínimo histórico por libro
                SELECT 
                    id_libro, 
                    MIN(precio) AS precio_minimo
                FROM fact_precio
                GROUP BY id_libro
            )
            -- Cruzamos la info y sacamos el Top 3 más barato hoy
            SELECT 
                pa.titulo, 
                pa.precio_actual, 
                pm.precio_minimo
            FROM PreciosActuales pa
            JOIN PreciosMinimos pm ON pa.id_libro = pm.id_libro
            WHERE pa.rank_fecha = 1
            ORDER BY pa.precio_actual ASC
            LIMIT 3;
        """
        
        cursor.execute(query)
        resultados = cursor.fetchall()
        
        if not resultados:
            await ctx.send("🗂️ Los archivos están vacíos. Tu tabla de hechos no tiene registros recientes.")
            return

        mensaje = "📊 **Reporte de Mercado: Top 3 Libros Más Baratos**\n\n"
        medallas = ["🥇", "🥈", "🥉"]
        
        for i, fila in enumerate(resultados):
            titulo = fila['titulo']
            precio_actual = fila['precio_actual']
            precio_historico = fila['precio_minimo']
            
            # Análisis de la bibliotecaria
            if precio_actual <= precio_historico:
                analisis = "¡Mínimo Histórico! Es el momento óptimo para adquirirlo."
            else:
                analisis = f"El valor histórico más bajo registrado es ${precio_historico}."
                
            mensaje += f"{medallas[i]} **{titulo}** - **${precio_actual}**\n   └ *{analisis}*\n\n"
            
        mensaje += "*Nota: Análisis de dimensiones completado. Usa esta información sabiamente; no me gusta verte gastar plata de más en cosas que puedes conseguir baratas.*"
        await ctx.send(mensaje)

    except Exception as e:
        await ctx.send(f"⚠️ Ocurrió una anomalía al cruzar los expedientes: {e}")
    finally:
        cursor.close()
        conn.close()

# Despertar a la bibliotecaria
if __name__ == "__main__":
    if TOKEN:
        mantener_vivo() # Activa el servidor web en segundo plano (FastAPI)
        bot.run(TOKEN)
    else:
        print("❌ Error de sistema: No se detectó el DISCORD_TOKEN.")