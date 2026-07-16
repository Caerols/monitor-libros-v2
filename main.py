# main.py
import sys
import logging
from src.config.settings import config
from src.adapters.scrapers.buscalibre import BuscalibreScraper
from src.adapters.database.repository import LibroRepository
from src.adapters.discord.webhook import DiscordNotifier
from src.use_cases.process_books import GeneradorAlertasBuscalibre

# Configuración básica de Logging a la consola para que GitHub Actions lo capture
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def main():
    logger.info("Iniciando aplicación...")

    # Instanciamos nuestras herramientas técnicas
    scraper = BuscalibreScraper()
    repo = LibroRepository()
    notifier = DiscordNotifier()

    # Armamos el orquestador
    app = GeneradorAlertasBuscalibre(scraper, repo, notifier)

    # Obtenemos las listas a monitorear DIRECTAMENTE DESDE TU TABLA EN AWS
    try:
        urls_objetivo = repo.obtener_listas_activas()
    except Exception as e:
        logger.critical("No se pudieron cargar las listas de monitoreo. Abortando.")
        return

    if not urls_objetivo:
        logger.warning("No hay listas activas en 'listas_monitoreo'. Terminando ejecución.")
        return

    # Ejecutamos el scraping
    app.ejecutar(urls_objetivo)

if __name__ == "__main__":
    main()