import time
import logging
import requests
from typing import List

from src.ports.notifier import BaseNotifier
from src.core.models import Libro
from src.config.settings import config

logger = logging.getLogger(__name__)

class DiscordNotifier(BaseNotifier):
    """Implementación robusta para notificar vía webhooks de Discord con temática del Gremio."""
    
    def __init__(self):
        self.webhook_url = config.DISCORD_WEBHOOK_URL
        # Nombre y Avatar temáticos por defecto para los reportes de caza
        self.default_username = "Cazador De Libros"
        self.default_avatar = "https://cdn-icons-png.flaticon.com/512/3069/3069155.png" # Icono de lobo/cazador

    def _enviar_payload(self, payload: dict) -> None:
        """Método interno que maneja el envío real y el Rate Limiting con máxima resiliencia."""
        if not self.webhook_url:
            logger.warning("No hay URL de Discord configurada en las variables. Se omite el envío.")
            return

        # Inyectamos el diseño del bot si el payload no lo trae
        if "username" not in payload:
            payload["username"] = self.default_username
        if "avatar_url" not in payload:
            payload["avatar_url"] = self.default_avatar

        max_intentos = 3
        for intento in range(max_intentos):
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=10)
                
                # Manejo de Rate Limit (HTTP 429) de Discord
                if response.status_code == 429:
                    retry_after = response.json().get('retry_after', 2)
                    logger.warning(f"Rate limit de Discord alcanzado. El cazador espera en las sombras {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                    
                response.raise_for_status()
                logger.debug("Mensaje enviado a Discord correctamente.")
                break # Éxito, salimos del bucle
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de red enviando al Gremio: {str(e)}")
                if intento == max_intentos - 1:
                    logger.critical("Se agotaron los intentos para enviar el reporte de caza al webhook.")

    def enviar_alerta_optimizada(
        self, 
        titulo: str, 
        url: str, 
        precio_actual: int, 
        precio_anterior: int, 
        precio_maximo: int, 
        fluctuacion: str, 
        estado_texto: str, 
        ahorro_real: int, 
        color: int
    ) -> None:
        """Construye y dispara la alerta inteligente directamente al canal."""
        
        # Formateo de pesos chilenos limpios (Ej: $18.990)
        str_actual = f"${int(precio_actual):,}".replace(",", ".")
        str_anterior = f"${int(precio_anterior):,}".replace(",", ".")
        str_maximo = f"${int(precio_maximo):,}".replace(",", ".")
        str_ahorro = f"${int(ahorro_real):,}".replace(",", ".")

        # Configurar el Título temático
        if fluctuacion == "BAJA":
            titulo_embed = f"📉 ¡Rastro fresco! {titulo} BAJÓ de precio."
        else:
            titulo_embed = f"📈 ¡La presa huye! {titulo} SUBIÓ de precio."

        # Construcción modular de los campos de la tarjeta
        fields = [
            {"name": "🎯 Visión de Cazador", "value": f"**{estado_texto}**", "inline": False}
        ]

        # Campo 2: El Ahorro (Solo lo mostramos si hay un botín real)
        if ahorro_real > 0:
            fields.append({
                "name": "💰 Botín Estimado", 
                "value": f"(Te ahorras **{str_ahorro}** comparado con su época más cara de {str_maximo})", 
                "inline": False
            })

        payload = {
            "embeds": [{
                "title": titulo_embed,
                "url": url,
                "description": f"Variación: De **{str_anterior}** a **{str_actual}**",
                "color": color,
                "fields": fields,
                "footer": {"text": "Gremio de Cazadores • Monitoreo Implacable"}
            }]
        }
        
        self._enviar_payload(payload)

    def enviar_alerta_sistema(self, mensaje: str, nivel: str = "error") -> None:
        """Alerta específica para caídas, Cloudflare, IPs bloqueadas, etc."""
        color = 15158332 if nivel == "error" else 16776960 # Rojo o Amarillo
        emoji = "⚠️" if nivel == "warning" else "🚨"
        
        payload = {
            "username": "El Cuervo del Gremio", # Emisario temático para errores
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2952/2952224.png", # Icono de cuervo
            "embeds": [{
                "title": f"{emoji} Mensaje de emergencia del Gremio",
                "description": mensaje,
                "color": color
            }]
        }
        self._enviar_payload(payload)

    def enviar_ofertas(self, libros: List[Libro]) -> None:
        """
        Mantenido por compatibilidad con la interfaz BaseNotifier. 
        Este método se usa si fuerzas un escaneo masivo de ofertas antiguas sin el sistema inteligente.
        """
        if not libros:
            return

        embeds = []
        for libro in libros:
            precio_fmt = f"${libro.precio_actual:,.0f}".replace(",", ".")
            
            embeds.append({
                "title": f"🎯 Presa avistada: {libro.titulo}",
                "url": libro.url,
                "color": 3066993, # Verde éxito
                "fields": [
                    {"name": "💰 Precio Actual", "value": precio_fmt, "inline": True},
                    {"name": "🔖 Descuento", "value": f"{libro.descuento_porcentaje or 0}%", "inline": True}
                ],
                "footer": {"text": "Cacería automática completada"}
            })

        for i in range(0, len(embeds), 10):
            chunk = embeds[i:i + 10]
            payload = {
                "content": "🔥 **¡Nuevas presas vulnerables detectadas!**",
                "embeds": chunk
            }
            self._enviar_payload(payload)