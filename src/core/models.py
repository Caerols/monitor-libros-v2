# src/core/models.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Libro:
    """Entidad principal que representa un libro extraído de la tienda."""
    id_tienda: str            # ID único o SKU de Buscalibre
    titulo: str
    url: str
    precio_actual: float
    precio_anterior: Optional[float] = None
    descuento_porcentaje: Optional[float] = None
    en_stock: bool = True
    fecha_extraccion: datetime = None

    def __post_init__(self):
        """Validaciones de negocio inmediatamente después de crear el objeto."""
        if self.fecha_extraccion is None:
            self.fecha_extraccion = datetime.now()
            
        if self.precio_actual < 0:
            raise ValueError(f"El precio no puede ser negativo para el libro {self.titulo}")

@dataclass
class ListaMonitoreo:
    """Entidad que representa una URL objetivo a scrapear."""
    id: int
    url: str
    activa: bool = True