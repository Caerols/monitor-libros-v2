# src/adapters/discord/webhook.py
import time
import logging
import requests
from typing import List

from src.ports.notifier import BaseNotifier
from src.core.models import Libro
from src.config.settings import config

logger = logging.getLogger(__name__)

class DiscordNotifier(BaseNotifier):
    """Implementación robusta para notificar vía webhooks de Discord."""
    
    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL

    def _enviar_payload(self, payload: dict) -> None:
        """Método interno que maneja el envío real y el Rate Limiting."""
        if not self.webhook_url:
            logger.warning("No hay URL de Discord configurada en las variables. Se omite el envío.")
            return

        max_intentos = 3
        for intento in range(max_intentos):
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=10)
                
                # Manejo de Rate Limit (HTTP 429)
                if response.status_code == 429:
                    # Discord nos dice cuántos segundos esperar en el header o en el JSON
                    retry_after = response.json().get('retry_after', 2)
                    logger.warning(f"Rate limit de Discord alcanzado. Esperando {retry_after} segundos...")
                    time.sleep(retry_after)
                    continue
                    
                response.raise_for_status()
                logger.debug("Mensaje enviado a Discord correctamente.")
                break # Éxito, salimos del bucle
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de red enviando a Discord: {str(e)}")
                if intento == max_intentos - 1:
                    logger.critical("Se agotaron los intentos para enviar el webhook.")

    def enviar_ofertas(self, libros: List[Libro]) -> None:
        if not libros:
            return

        embeds = []
        for libro in libros:
            precio_fmt = f"${libro.precio_actual:,.0f}".replace(",", ".")
            
            embeds.append({
                "title": libro.titulo,
                "url": libro.url,
                "color": 3066993, # Verde éxito
                "fields": [
                    {"name": "💰 Precio Actual", "value": precio_fmt, "inline": True},
                    {"name": "🔖 Descuento", "value": f"{libro.descuento_porcentaje or 0}%", "inline": True}
                ],
                "footer": {"text": "Escaneo automático completado"}
            })

        # Discord limita a 10 embeds por mensaje. Dividimos la lista en "chunks".
        for i in range(0, len(embeds), 10):
            chunk = embeds[i:i + 10]
            payload = {
                "content": "🔥 **¡Nuevas Ofertas Detectadas en Buscalibre!**",
                "embeds": chunk
            }
            self._enviar_payload(payload)

    def enviar_alerta_sistema(self, mensaje: str, nivel: str = "error") -> None:
        """Alerta específica para caídas, Cloudflare, IPs bloqueadas, etc."""
        color = 15158332 if nivel == "error" else 16776960 # Rojo o Amarillo
        emoji = "⚠️" if nivel == "warning" else "🚨"
        
        payload = {
            "username": "Monitor de Infraestructura",
            "embeds": [{
                "title": f"{emoji} Alerta del Scraper",
                "description": mensaje,
                "color": color
            }]
        }
        self._enviar_payload(payload)