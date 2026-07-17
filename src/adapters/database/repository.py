# src/adapters/database/repository.py
import logging
from typing import List
from datetime import date
from psycopg2.extras import execute_values
from src.core.models import Libro
from src.adapters.database.connection import DatabasePool

logger = logging.getLogger(__name__)

class LibroRepository:
    """Encapsula todas las operaciones de persistencia para la entidad Libro."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _asegurar_fecha_actual(self, cursor) -> int:
        """
        Garantiza que la fecha actual exista en dim_fecha y retorna su ID.
        Si no existe, la crea al vuelo. (Lazy Loading)
        """
        hoy = date.today()
        cursor.execute("SELECT id_fecha FROM dim_fecha WHERE fecha_exacta = %s;", (hoy,))
        resultado = cursor.fetchone()
        
        if resultado:
            return resultado[0]
            
        # Si no existe, la insertamos
        query_insert_fecha = """
            INSERT INTO dim_fecha (fecha_exacta, anio, mes, dia) 
            VALUES (%s, %s, %s, %s) RETURNING id_fecha;
        """
        cursor.execute(query_insert_fecha, (hoy, hoy.year, hoy.month, hoy.day))
        return cursor.fetchone()[0]

    def guardar_libros(self, libros: List[Libro]) -> None:
        """Guarda los libros usando Star Schema mediante Bulk Inserts atómicos."""
        if not libros:
            self.logger.warning("No hay libros para guardar. Operación omitida.")
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
                    
                    # FIX APLICADO: Agregamos fetch=True y capturamos los resultados directamente
                    resultados_dim = execute_values(
                        cursor, 
                        query_dim, 
                        datos_dim_libro, 
                        template="(%s, %s, 'Activo')",
                        fetch=True
                    )
                    
                    # Validamos que obtuvimos resultados para evitar errores de clave
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

                    # Confirmamos la transacción completa
                    conn.commit()
                    self.logger.info(f"Se procesaron masivamente {len(libros)} libros en el Star Schema.")
                    
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Error fatal en transacción SQL masiva: {str(e)}")
                    raise

    def obtener_listas_activas(self) -> List[str]:
        """Obtiene las URLs de las listas de Buscalibre desde la base de datos."""
        query = "SELECT url_lista FROM listas_monitoreo WHERE estado = 'Activo';"
        
        try:
            with DatabasePool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                    urls = [fila[0] for fila in resultados]
            
            if not urls:
                self.logger.warning("No se encontraron listas activas en 'listas_monitoreo'.")
            else:
                self.logger.info(f"Se obtuvieron {len(urls)} listas activas desde la BD.")
                
            return urls
            
        except Exception as e:
            self.logger.error(f"Error al leer listas_monitoreo: {str(e)}")
            raise