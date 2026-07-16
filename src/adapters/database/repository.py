# src/adapters/database/repository.py
import logging
from typing import List
from src.core.models import Libro
from src.adapters.database.connection import DatabasePool

logger = logging.getLogger(__name__)

class LibroRepository:
    """Encapsula todas las operaciones de persistencia para la entidad Libro."""

    def guardar_libros(self, libros: List[Libro]) -> None:
        """Guarda o actualiza los libros en la base de datos de manera masiva (Batch)."""
        if not libros:
            logger.warning("No hay libros para guardar. Operación omitida.")
            return

        # Utilizamos UPSERT (ON CONFLICT) para crear o actualizar en una sola operación atómica.
        # Asume que tienes un constraint UNIQUE en la columna 'url' o 'id_tienda'.
        query = """
            INSERT INTO libros (id_tienda, titulo, url, precio_actual, fecha_extraccion)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE 
            SET precio_actual = EXCLUDED.precio_actual,
                fecha_extraccion = EXCLUDED.fecha_extraccion;
        """

        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # Preparamos los datos para la inserción masiva
                    datos = [
                        (l.id_tienda, l.titulo, l.url, l.precio_actual, l.fecha_extraccion)
                        for l in libros
                    ]
                    
                    # executemany es órdenes de magnitud más rápido que iterar un INSERT
                    cursor.executemany(query, datos)
                    
                    # Confirmamos la transacción
                    conn.commit()
                    logger.info(f"Se han guardado/actualizado {len(libros)} libros en PostgreSQL.")
                    
                except Exception as e:
                    # Si algo falla (ej. un tipo de dato incorrecto), deshacemos toda la transacción
                    conn.rollback()
                    logger.error(f"Error en transacción SQL al guardar libros: {str(e)}")
                    raise

    def obtener_listas_activas(self) -> List[str]:
        """Obtiene las URLs de las listas de Buscalibre desde la base de datos."""
        query = "SELECT url_lista FROM listas_monitoreo WHERE estado = 'Activo';"
        urls = []
        
        try:
            with DatabasePool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    resultados = cursor.fetchall()
                    # Extraemos solo la URL de la tupla devuelta por psycopg2
                    urls = [fila[0] for fila in resultados]
                    
            logger.info(f"Se obtuvieron {len(urls)} listas activas desde la BD.")
            return urls
            
        except Exception as e:
            logger.error(f"Error al leer listas_monitoreo: {str(e)}")
            raise