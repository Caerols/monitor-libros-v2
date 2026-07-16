# src/config/settings.py
import os
from dotenv import load_dotenv

# Cargamos el archivo .env si estamos en local (en GitHub Actions usará los Secrets)
load_dotenv()

class ConfigurationError(Exception):
    """Excepción lanzada cuando falta una variable de entorno crítica."""
    pass

def _get_env_var(var_name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(var_name)
    if required and not value:
        raise ConfigurationError(f"Variable de entorno faltante y obligatoria: {var_name}")
    return value or default

class Settings:
    """Configuración global de la aplicación."""
    
    # Base de Datos
    DB_HOST = _get_env_var("DB_HOST")
    DB_PORT = _get_env_var("DB_PORT", default="6543")
    DB_NAME = _get_env_var("DB_NAME")
    DB_USER = _get_env_var("DB_USER")
    DB_PASSWORD = _get_env_var("DB_PASSWORD")
    
    # Scraper & APIs
    SCRAPER_API_KEY = _get_env_var("SCRAPER_API_KEY", required=False) # Ahora es opcional para la estrategia Coste 0
    
    # Notificaciones
    DISCORD_WEBHOOK_URL = _get_env_var("DISCORD_WEBHOOK")
    
    # Parámetros de Scraping
    MAX_RETRIES = int(_get_env_var("MAX_RETRIES", required=False, default="3"))
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Instancia global para ser importada en el resto del proyecto
config = Settings()