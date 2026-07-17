# src/adapters/scrapers/buscalibre.py
import logging
import random
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import List

from src.adapters.scrapers.base import BaseScraper
from src.core.models import Libro
from src.core.exceptions import BlockedIPError, EmptyDOMError
from src.config.settings import config

# Configuración de Logging Estructurado
logger = logging.getLogger(__name__)

# Pool de User-Agents modernos para evasión de fingerprinting (WAF)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Safari/605.1.15"
]

class BuscalibreScraper(BaseScraper):
    def __init__(self):
        # Nivel 1: Usar una Sesión reutiliza la conexión TCP subyacente (mucho más rápido)
        self.session = requests.Session()
        
    def _get_random_headers(self) -> dict:
        """Genera cabeceras dinámicas para cada petición, evitando baneos por huella."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1" # Do Not Track flag
        }

    def _verificar_bloqueo(self, html: str, status_code: int):
        """Audita la respuesta para detectar Firewalls o CAPTCHAs."""
        html_lower = html.lower()
        if status_code in (403, 429, 503) or "cloudflare" in html_lower or "just a moment" in html_lower:
            raise BlockedIPError("WAF o Cloudflare detectado. Acceso temporalmente denegado por Buscalibre.")

    def _peticion_directa(self, url: str) -> str:
        """Estrategia 1: Coste 0. Petición directa simulando un navegador real."""
        logger.info(f"🌐 Intentando petición directa a: {url}")
        
        # Timeout compuesto: (5s para conectar al servidor, 15s para descargar el HTML)
        response = self.session.get(url, headers=self._get_random_headers(), timeout=(5, 15))
        
        if response.status_code == 404:
            raise EmptyDOMError(f"Error 404: La URL solicitada no existe o fue eliminada ({url}).")
            
        self._verificar_bloqueo(response.text, response.status_code)
        response.raise_for_status()
        return response.text

    def _peticion_rescate_api(self, url: str) -> str:
        """Estrategia 2: Rescate proxy. Usa ScraperAPI solo si la directa falló."""
        if not getattr(config, 'SCRAPER_API_KEY', None):
            raise BlockedIPError("Bloqueo detectado y no hay SCRAPER_API_KEY configurada para protocolo de rescate.")
            
        logger.warning(f"🚨 Activando protocolo de rescate con ScraperAPI para: {url}")
        api_url = f"http://api.scraperapi.com/?api_key={config.SCRAPER_API_KEY}&url={url}&render=true"
        
        response = self.session.get(api_url, timeout=(10, 45)) 
        self._verificar_bloqueo(response.text, response.status_code)
        
        sa_status = response.headers.get("sa-statuscode")
        if sa_status and int(sa_status) >= 400:
            raise BlockedIPError(f"ScraperAPI falló con sa-statuscode: {sa_status}")
            
        return response.text

    def _obtener_html_resiliente(self, url: str) -> str:
        """Orquesta las estrategias de obtención de HTML."""
        try:
            return self._peticion_directa(url)
        except BlockedIPError as e:
            logger.error(f"⚠️ Fallo directo: {str(e)}. Intentando evasión...")
            return self._peticion_rescate_api(url)
            
    # Exponential Backoff: Si falla por red o bloqueo, espera 4s, 8s, 16s...
    @retry(
        stop=stop_after_attempt(getattr(config, 'MAX_RETRIES', 3)),
        wait=wait_exponential(multiplier=2, min=4, max=15),
        retry=retry_if_exception_type((requests.exceptions.RequestException, BlockedIPError)),
        reraise=True
    )
    def extraer_libros(self, url: str) -> List[Libro]:
        html = self._obtener_html_resiliente(url)
        soup = BeautifulSoup(html, "html.parser")
        
        cajas_libros = soup.find_all("div", class_="contenedorProducto")
        
        # Data Quality Gate 1: Validación del DOM
        if not cajas_libros:
            logger.error(f"HTML recibido (primeros 500 chars): {html[:500]}")
            raise EmptyDOMError(f"No se encontraron contenedores en {url}. Posible cambio de diseño CSS en Buscalibre.")

        libros_extraidos = []
        for caja in cajas_libros:
            try:
                id_tienda = caja.get("data-id_producto", "DESCONOCIDO")
                precio_str = caja.get("data-precio")
                
                # Data Quality Gate 2: Precio válido
                if not precio_str or not precio_str.replace('.', '').isdigit():
                    continue 
                    
                precio_limpio = float(precio_str)
                
                enlace = caja.find("a")
                if not enlace or not enlace.get("title") or not enlace.get("href"):
                    continue
                    
                titulo = enlace.get("title").strip()
                # Data Quality Gate 3: Sanitización de URL (Asegura formato https://...)
                url_libro = urljoin("https://www.buscalibre.cl", enlace.get("href"))
                
                descuento_porcentaje = None
                div_dcto = caja.find("div", class_="dcto")
                if div_dcto and "%" in div_dcto.text:
                    dcto_limpio = div_dcto.text.replace("-", "").replace("%", "").strip()
                    try:
                        descuento_porcentaje = float(dcto_limpio)
                    except ValueError:
                        pass 

                libro = Libro(
                    id_tienda=id_tienda,
                    titulo=titulo,
                    url=url_libro,
                    precio_actual=precio_limpio,
                    descuento_porcentaje=descuento_porcentaje
                )
                libros_extraidos.append(libro)
            except Exception as e:
                logger.warning(f"Error extrayendo caja individual (ID: {id_tienda}): {str(e)}. Saltando.")

        logger.info(f"✅ Extracción exitosa. {len(libros_extraidos)} libros encontrados.")
        return libros_extraidos