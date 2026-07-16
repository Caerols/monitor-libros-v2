# src/use_cases/process_books.py
import logging
from typing import List
from src.core.exceptions import ScraperBaseError, DatabaseConnectionError
from src.ports.notifier import BaseNotifier
from src.adapters.database.repository import LibroRepository
from src.adapters.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class GeneradorAlertasBuscalibre:
    """Orquestador central del flujo de extracción y notificación."""

    def __init__(
        self, 
        scraper: BaseScraper, 
        repository: LibroRepository, 
        notifier: BaseNotifier
    ):
        self.scraper = scraper
        self.repository = repository
        self.notifier = notifier

    def ejecutar(self, urls: List[str]) -> None:
        """Ejecuta el ciclo de vida completo para una lista de URLs objetivo."""
        logger.info("Iniciando ciclo de escaneo de Buscalibre...")
        
        todos_los_libros_extraidos = []

        for url in urls:
            try:
                # 1. Extracción (El scraper decide si usa directa o API por debajo)
                libros = self.scraper.extraer_libros(url)
                todos_los_libros_extraidos.extend(libros)
                
            except ScraperBaseError as e:
                # Si falla el scraper (ej. Buscalibre cambió el diseño), alertamos al administrador
                logger.error(f"Fallo en la extracción para {url}: {str(e)}")
                self.notifier.enviar_alerta_sistema(f"Fallo crítico en URL {url}:\n{str(e)}", nivel="error")
                continue # Continuamos con la siguiente URL para no detener todo el proceso

        if not todos_los_libros_extraidos:
            logger.warning("No se extrajo ningún libro en este ciclo.")
            return

        try:
            # 2. Persistencia
            self.repository.guardar_libros(todos_los_libros_extraidos)
            
            # Aquí iría tu lógica real de negocio para comparar el 'precio_anterior'
            # y decidir qué libros son "ofertas". Por ahora asumiremos una lista filtrada.
            libros_en_oferta = [libro for libro in todos_los_libros_extraidos if libro.descuento_porcentaje and libro.descuento_porcentaje > 10]
            
            # 3. Notificación
            if libros_en_oferta:
                self.notifier.enviar_ofertas(libros_en_oferta)
                logger.info(f"Se notificaron {len(libros_en_oferta)} ofertas a Discord.")
            else:
                logger.info("Escaneo completado. No hay ofertas relevantes hoy.")
                
        except DatabaseConnectionError as db_err:
            logger.critical("Fallo de base de datos.")
            self.notifier.enviar_alerta_sistema("Error de Base de Datos impidió guardar los libros.", nivel="error")