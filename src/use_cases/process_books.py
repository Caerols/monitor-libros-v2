import logging
from typing import List, Dict, Any, Optional
from src.core.exceptions import ScraperBaseError, DatabaseConnectionError
from src.ports.notifier import BaseNotifier
from src.adapters.database.repository import LibroRepository
from src.adapters.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class GeneradorAlertasBuscalibre:
    """Orquestador central del flujo de caza, extracción y notificación."""

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
        """Ejecuta la temporada de caza completa para las zonas (URLs) objetivo."""
        logger.info("🐺 Iniciando temporada de caza en Buscalibre...")
        
        todos_los_libros_extraidos = []

        for url in urls:
            try:
                # 1. Extracción (Rastreo de presas)
                libros = self.scraper.extraer_libros(url)
                todos_los_libros_extraidos.extend(libros)
                
            except ScraperBaseError as e:
                logger.error(f"Rastro perdido en {url}: {str(e)}")
                self.notifier.enviar_alerta_sistema(
                    f"⚠️ El Gremio informa: Rastro perdido en territorio de caza ({url}):\n{str(e)}", 
                    nivel="error"
                )
                continue 

        if not todos_los_libros_extraidos:
            logger.warning("La cacería terminó. No se avistaron presas hoy.")
            return

        try:
            alertas_a_enviar = []

            # 2. Análisis Táctico de Presas (Evaluación de precios)
            for libro in todos_los_libros_extraidos:
                # Simulamos que el repositorio nos da el historial antes de guardar el precio nuevo.
                # Asegúrate de que tu LibroRepository tenga este método.
                stats_historicas = self.repository.obtener_estadisticas_historicas(libro.url)
                
                alerta = self._evaluar_presa(libro, stats_historicas)
                if alerta:
                    alertas_a_enviar.append(alerta)

            # 3. Persistencia (Guardar trofeos y registros nuevos en BD)
            self.repository.guardar_libros(todos_los_libros_extraidos)
            
            # 4. Notificación al Gremio (Discord)
            if alertas_a_enviar:
                for alerta in alertas_a_enviar:
                    self.notifier.enviar_alerta_optimizada(**alerta)
                logger.info(f"🎯 Cacería exitosa: Se enviaron {len(alertas_a_enviar)} reportes de movimiento al Gremio.")
            else:
                logger.info("Cacería silenciosa. Las presas no se han movido de su precio actual. (Cero Spam)")
                
        except DatabaseConnectionError as db_err:
            logger.critical("Fallo en los archivos del Gremio (Base de Datos).")
            self.notifier.enviar_alerta_sistema("Error crítico: Los pergaminos del Gremio (BD) no responden.", nivel="error")

    def _evaluar_presa(self, libro: Any, stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Evalúa si la presa merece una flecha (notificación) basándose en su historial.
        Retorna un diccionario con la alerta formateada o None si es spam.
        """
        precio_actual = libro.precio
        precio_anterior = stats.get('precio_anterior')
        precio_maximo = stats.get('precio_maximo', precio_actual)
        precio_minimo = stats.get('precio_minimo', precio_actual)

        # 1. REGLA ANTI-SPAM: Si la presa no se movió, ignoramos el rastro.
        if precio_anterior and precio_actual == precio_anterior:
            return None

        # 2. DIRECCIÓN DEL MOVIMIENTO
        if not precio_anterior:
            return None # Ignoramos libros 100% nuevos para no saturar en el primer escaneo
        elif precio_actual < precio_anterior:
            fluctuacion = "BAJA"
        else:
            fluctuacion = "SUBE"

        # 3. ESTADO DE CAZA (La regla de cuartiles y recomendación UI)
        if precio_actual <= precio_minimo and precio_maximo > precio_minimo:
            estado_texto = "🟢 Tiro Limpio - ¡Cazar ahora!"
            color_discord = 0x2e7d32 # Verde
        elif precio_actual >= precio_maximo and precio_maximo > precio_minimo:
            estado_texto = "🔴 Presa Alerta - Esperar en las sombras"
            color_discord = 0xd32f2f # Rojo
        else:
            estado_texto = "🟡 Rastro tibio - Observar a la presa"
            color_discord = 0xff9800 # Naranja

        # 4. AHORRO REAL (Contra el peor escenario)
        ahorro_real = precio_maximo - precio_actual

        return {
            "titulo": libro.titulo,
            "url": libro.url,
            "precio_actual": precio_actual,
            "precio_anterior": precio_anterior,
            "precio_maximo": precio_maximo,
            "fluctuacion": fluctuacion,
            "estado_texto": estado_texto,
            "ahorro_real": ahorro_real,
            "color": color_discord
        }