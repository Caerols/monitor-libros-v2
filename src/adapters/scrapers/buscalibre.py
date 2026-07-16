# src/adapters/scrapers/buscalibre.py
import logging
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import List

from src.adapters.scrapers.base import BaseScraper
from src.core.models import Libro
from src.core.exceptions import BlockedIPError, EmptyDOMError
from src.config.settings import config

# Configuración de Logging Estructurado
logger = logging.getLogger(__name__)

class BuscalibreScraper(BaseScraper):
    def __init__(self):
        # Nivel 1: Headers para simular ser un navegador real y evitar detección temprana
        self.headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _verificar_bloqueo(self, html: str, status_code: int):
        """Audita la respuesta para detectar Firewalls o CAPTCHAs."""
        html_lower = html.lower()
        if status_code in (403, 429, 503) or "cloudflare" in html_lower or "just a moment" in html_lower:
            raise BlockedIPError("WAF o Cloudflare detectado. Acceso denegado por Buscalibre.")

    def _peticion_directa(self, url: str) -> str:
        """Estrategia 1: Coste 0. Petición directa simulando navegador."""
        logger.info(f"Intentando petición directa a: {url}")
        response = requests.get(url, headers=self.headers, timeout=15)
        
        # Nueva validación: Si la URL no existe, lanzamos un error de dominio que el orquestador sepa manejar
        if response.status_code == 404:
            raise EmptyDOMError(f"Error 404: La URL solicitada no existe o fue eliminada en Buscalibre ({url}).")
            
        self._verificar_bloqueo(response.text, response.status_code)
        response.raise_for_status()
        return response.text

    def _peticion_rescate_api(self, url: str) -> str:
        """Estrategia 2: Rescate. Usa ScraperAPI solo si la directa falló."""
        if not config.SCRAPER_API_KEY:
            raise BlockedIPError("Bloqueo detectado y no hay SCRAPER_API_KEY configurada para rescate.")
            
        logger.warning(f"Activando protocolo de rescate con ScraperAPI para: {url}")
        api_url = f"http://api.scraperapi.com/?api_key={config.SCRAPER_API_KEY}&url={url}&render=true"
        
        # Timeout más largo porque la API debe renderizar JS
        response = requests.get(api_url, timeout=45) 
        self._verificar_bloqueo(response.text, response.status_code)
        
        # Validar headers específicos de ScraperAPI que indican problemas
        sa_status = response.headers.get("sa-statuscode")
        if sa_status and int(sa_status) >= 400:
            raise BlockedIPError(f"ScraperAPI falló con sa-statuscode: {sa_status}")
            
        return response.text

    def _obtener_html_resiliente(self, url: str) -> str:
        """Orquesta las estrategias de obtención de HTML."""
        try:
            return self._peticion_directa(url)
        except BlockedIPError as e:
            logger.error(f"Fallo directo: {str(e)}")
            return self._peticion_rescate_api(url)
            
    # El decorador @retry envolverá todo el proceso de extracción.
    # Si detecta errores de red o bloqueos persistentes, esperará e intentará hasta 3 veces.
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=4, max=15),
        retry=retry_if_exception_type((requests.exceptions.RequestException, BlockedIPError)),
        reraise=True
    )
    def extraer_libros(self, url: str) -> List[Libro]:
        html = self._obtener_html_resiliente(url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Validaciones Defensivas
        cajas_libros = soup.find_all("div", class_="contenedorProducto")
        
        if not cajas_libros:
            # Observabilidad vital: Si falla, guardamos los primeros 1000 caracteres para depurar
            logger.error(f"HTML recibido (primeros 1000 chars): {html[:1000]}")
            raise EmptyDOMError(f"No se encontraron libros en {url}. Posible cambio de diseño en Buscalibre.")

        libros_extraidos = []
        for caja in cajas_libros:
            try:
                # 1. Extraer ID y Precio directo desde los atributos (mucho más seguro y rápido)
                id_tienda = caja.get("data-id_producto", "DESCONOCIDO")
                precio_str = caja.get("data-precio")
                
                # Si la caja no tiene precio (ej. libros agotados o error de carga), lo saltamos
                if not precio_str or not precio_str.isdigit():
                    continue 
                    
                precio_limpio = float(precio_str)
                
                # 2. Extraer Título y URL desde el enlace
                enlace = caja.find("a")
                if not enlace or not enlace.get("title"):
                    continue
                    
                titulo = enlace.get("title").strip()
                url_libro = enlace.get("href", url)
                
                # 3. Extraer Descuento (opcional, por si queremos enviarlo a Discord)
                descuento_porcentaje = None
                div_dcto = caja.find("div", class_="dcto")
                if div_dcto and "%" in div_dcto.text:
                    # Limpiamos el texto "- 45 %" para que quede solo "45.0"
                    dcto_limpio = div_dcto.text.replace("-", "").replace("%", "").strip()
                    try:
                        descuento_porcentaje = float(dcto_limpio)
                    except ValueError:
                        pass # Si falla al convertir, simplemente lo dejamos en None

                libro = Libro(
                    id_tienda=id_tienda,
                    titulo=titulo,
                    url=url_libro,
                    precio_actual=precio_limpio,
                    descuento_porcentaje=descuento_porcentaje
                )
                libros_extraidos.append(libro)
            except Exception as e:
                logger.warning(f"Error parseando un libro individual: {str(e)}. Saltando al siguiente.")

        logger.info(f"Extracción exitosa. {len(libros_extraidos)} libros encontrados.")
        return libros_extraidos