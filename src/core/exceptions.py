# src/core/exceptions.py

class ScraperBaseError(Exception):
    """Clase base para todos los errores del dominio del scraper."""
    pass

class BlockedIPError(ScraperBaseError):
    """Lanzada cuando se detecta un bloqueo por WAF (Cloudflare, CAPTCHA, etc)."""
    pass

class EmptyDOMError(ScraperBaseError):
    """Lanzada cuando el HTML carga, pero los selectores esperados no existen (Cambio de diseño)."""
    pass

class DatabaseConnectionError(ScraperBaseError):
    """Lanzada cuando falla la conexión al pool de PostgreSQL."""
    pass