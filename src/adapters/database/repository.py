# src/adapters/database/repository.py
import logging
from typing import List
from src.core.models import Libro
from src.adapters.database.connection import DatabasePool

logger = logging.getLogger(__name__)

class LibroRepository:
    """Encapsula todas las operaciones de persistencia para la entidad Libro."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def guardar_libros(self, libros: List[Libro]) -> None:
        """
        Guarda o actualiza los libros en la base de datos usando Star Schema (Dimensiones y Hechos).
        Mantiene la atomicidad y el logging robusto original.
        """
        if not libros:
            logger.warning("No hay libros para guardar. Operación omitida.")
            return

        # Mantenemos tu estructura de conexión pool original
        with DatabasePool.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # Iteramos sobre los libros para manejar las relaciones (Star Schema)
                    for l in libros:
                        # 1. UPSERT en dim_libro: Aseguramos la existencia de la dimensión
                        # Usamos 'url' como clave única de conflicto tal como tenías en tu original
                        query_dim = """
                            INSERT INTO dim_libro (titulo, url_buscalibre, estado)
                            VALUES (%s, %s, 'Activo')
                            ON CONFLICT (url_buscalibre) DO UPDATE 
                            SET titulo = EXCLUDED.titulo
                            RETURNING id_libro;
                        """
                        cursor.execute(query_dim, (l.titulo, l.url))
                        id_libro = cursor.fetchone()[0]
                        
                        # 2. INSERT en fact_precio: Registramos el hecho vinculado a la fecha
                        # Vinculamos con la fecha actual desde la tabla dim_fecha
                        query_fact = """
                            INSERT INTO fact_precio (id_libro, precio, id_fecha)
                            VALUES (%s, %s, (SELECT id_fecha FROM dim_fecha WHERE fecha_exacta = CURRENT_DATE));
                        """
                        cursor.execute(query_fact, (id_libro, l.precio_actual))
                    
                    # Confirmamos la transacción masiva
                    conn.commit()
                    logger.info(f"Se han guardado/actualizado {len(libros)} libros en el Star Schema (Dimensiones y Hechos).")
                    
                except Exception as e:
                    # Si algo falla en cualquier punto de la iteración, deshacemos todo
                    conn.rollback()
                    logger.error(f"Error en transacción SQL al guardar libros: {str(e)}")
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
            
            # Validamos si encontramos listas o si la tabla devolvió algo vacío
            if not urls:
                logger.warning("No se encontraron listas activas en 'listas_monitoreo'.")
            else:
                logger.info(f"Se obtuvieron {len(urls)} listas activas desde la BD.")
                
            return urls
            
        except Exception as e:
            logger.error(f"Error al leer listas_monitoreo: {str(e)}")
            raise