# src/adapters/database/connection.py
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from src.config.settings import config
from src.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

class DatabasePool:
    """Singleton para manejar el pool de conexiones a PostgreSQL."""
    _pool = None

    @classmethod
    def initialize(cls):
        if cls._pool is None:
            try:
                # ThreadedConnectionPool es seguro si en el futuro usamos concurrencia
                cls._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=5,
                    host=config.DB_HOST,
                    port=config.DB_PORT,
                    dbname=config.DB_NAME,
                    user=config.DB_USER,
                    password=config.DB_PASSWORD
                )
                logger.info("Pool de conexiones a PostgreSQL inicializado correctamente.")
            except Exception as e:
                logger.critical(f"Error fatal al inicializar el pool de BD: {str(e)}")
                raise DatabaseConnectionError(f"No se pudo conectar a PostgreSQL: {str(e)}")

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Context manager para obtener y devolver conexiones de forma segura."""
        if cls._pool is None:
            cls.initialize()
            
        conn = cls._pool.getconn()
        try:
            yield conn
        finally:
            # Siempre se devuelve la conexión al pool, incluso si hay excepciones
            cls._pool.putconn(conn)