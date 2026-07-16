# src/ports/notifier.py
from abc import ABC, abstractmethod
from typing import List
from src.core.models import Libro

class BaseNotifier(ABC):
    """Contrato estándar para el envío de notificaciones."""
    
    @abstractmethod
    def enviar_ofertas(self, libros: List[Libro]) -> None:
        """Envía notificaciones de los libros que bajaron de precio."""
        pass

    @abstractmethod
    def enviar_alerta_sistema(self, mensaje: str, nivel: str = "error") -> None:
        """Envía notificaciones sobre la salud del scraper (bloqueos, caídas, etc)."""
        pass