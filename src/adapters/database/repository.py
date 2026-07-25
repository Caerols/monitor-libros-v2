# src/adapters/database/repository.py
import logging
from typing import List, Dict, Any
from datetime import date
from psycopg2.extras import execute_values, RealDictCursor

from src.core.models import Libro
from src.adapters.database.connection import DatabasePool

class LibroRepository:
    """
    Encapsula todas las operaciones de persistencia para la entidad Libro.
    Actúa como el archivero del Gremio, gestionando el Star Schema en la Matriz.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _asegurar_fecha_actual(self, cursor) -> int:
        """
        Garantiza que la fecha actual exista en dim_fecha y retorna su ID.
        Si no existe, la crea al vuelo usando un Smart Key (AAAAMMDD).
        """
        hoy = date.today()
        # Creamos un ID inteligente numérico (ej. 17 de Julio de 2026 -> 20260717)
        id_fecha_smart = int(hoy.strftime("%Y%m%d"))
        
        cursor.execute("SELECT id_fecha FROM dim_fecha WHERE fecha_exacta = %s;", (hoy,))
        resultado = cursor.fetchone()
        
        if resultado:
            return resultado[0]
            
        # Si no existe, la insertamos pasando explícitamente el id_fecha_smart
        query_insert_fecha = """
            INSERT INTO dim_fecha (id_fecha, fecha_exacta, anio, mes, dia) 
            VALUES (%s, %s, %s, %s, %s) RETURNING id_fecha;
        """
        cursor.execute(query_insert_fecha, (id_fecha_smart, hoy, hoy.year, hoy.month, hoy.day))
        return cursor.fetchone()[0]

    def guardar_libros(self, libros: List[Libro]) -> None:
        """Guarda los libros usando Star Schema mediante Bulk Inserts atómicos."""
        if not libros:
            self.logger.warning("No hay presas para guardar. Operación omitida.")
            return

        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # 1. Aseguramos la dimensión de tiempo
                    id_fecha_actual = self._asegurar_fecha_actual(cursor)

                    # 2. BULK UPSERT en dim_libro
                    datos_dim_libro = [(l.titulo, l.url) for l in libros]
                    
                    query_dim = """
                        INSERT INTO dim_libro (titulo, url_buscalibre, estado)
                        VALUES %s
                        ON CONFLICT (url_buscalibre) DO UPDATE 
                        SET titulo = EXCLUDED.titulo
                        RETURNING id_libro, url_buscalibre;
                    """
                    
                    # Ejecución optimizada en bloque
                    resultados_dim = execute_values(
                        cursor, 
                        query_dim, 
                        datos_dim_libro, 
                        template="(%s, %s, 'Activo')",
                        fetch=True
                    )
                    
                    if not resultados_dim:
                        self.logger.warning("No se insertaron ni actualizaron dimensiones de libros.")
                        return

                    mapa_urls_ids = {row[1]: row[0] for row in resultados_dim}

                    # 3. BULK INSERT en fact_precio
                    datos_fact_precio = []
                    for l in libros:
                        id_libro = mapa_urls_ids.get(l.url)
                        if id_libro:
                            datos_fact_precio.append((id_libro, l.precio_actual, id_fecha_actual))

                    if datos_fact_precio:
                        query_fact = """
                            INSERT INTO fact_precio (id_libro, precio, id_fecha, hora_monitoreo)
                            VALUES %s;
                        """
                        execute_values(
                            cursor, 
                            query_fact, 
                            datos_fact_precio, 
                            template="(%s, %s, %s, CURRENT_TIMESTAMP)"
                        )

                    # Confirmamos la transacción completa (Commit atómico)
                    conn.commit()
                    self.logger.info(f"Se procesaron masivamente {len(libros)} presas en los archivos.")
                    
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Error fatal en transacción SQL masiva: {str(e)}")
                    raise

    def obtener_listas_activas(self) -> List[str]:
        """Obtiene los territorios de caza (URLs de listas) desde la base de datos."""
        query = "SELECT url_lista FROM listas_monitoreo WHERE estado = 'Activo';"
        
        try:
            with DatabasePool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                    urls = [fila[0] for fila in resultados]
            
            if not urls:
                self.logger.warning("No se encontraron territorios activos en 'listas_monitoreo'.")
            else:
                self.logger.info(f"Se obtuvieron {len(urls)} territorios de caza desde la BD.")
                
            return urls
            
        except Exception as e:
            self.logger.error(f"Error al leer listas_monitoreo: {str(e)}")
            raise

    def obtener_estadisticas_historicas(self, url: str) -> Dict[str, Any]:
        """
        Consulta los archivos históricos para obtener el precio anterior, 
        máximo y mínimo de una presa antes de que se registre su nuevo movimiento.
        """
        query = """
            SELECT 
                (SELECT precio FROM fact_precio WHERE id_libro = l.id_libro ORDER BY id_fecha DESC, hora_monitoreo DESC LIMIT 1) as precio_anterior,
                (SELECT MAX(precio) FROM fact_precio WHERE id_libro = l.id_libro) as precio_maximo,
                (SELECT MIN(precio) FROM fact_precio WHERE id_libro = l.id_libro) as precio_minimo
            FROM dim_libro l
            WHERE l.url_buscalibre = %s;
        """
        
        try:
            with DatabasePool.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (url,))
                    resultado = cursor.fetchone()
                    
                    # Validamos si el libro ya existía y tiene precios previos
                    if resultado and resultado['precio_anterior'] is not None:
                        return dict(resultado)
                    
                    # Si la presa es nueva, devolvemos un historial vacío
                    return {}
                    
        except Exception as e:
            self.logger.error(f"Error consultando estadísticas históricas para {url}: {e}")
            return {}