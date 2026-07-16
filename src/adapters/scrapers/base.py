# src/adapters/scrapers/base.py
from abc import ABC, abstractmethod
from typing import List
from src.core.models import Libro

class BaseScraper(ABC):
    """Contrato estricto para cualquier scraper en el sistema."""
    
    @abstractmethod
    def extraer_libros(self, url: str) -> List[Libro]:
        """Debe recibir una URL y devolver una lista de objetos Libro validos."""
        pass