"""
AircraftClassification.py
Modelo para clasificación de aeronaves
Proyecto 3 - PGTA
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AircraftClassification:
    """
    Representa la clasificación de una aeronave según su tipo OACI.
    
    Attributes:
        oaci_type: Tipo OACI de la aeronave (ej: 'A320', 'B738')
        wake_category: Categoría de estela turbulenta (LIGHT, MEDIUM, HEAVY, SUPER)
        engine_type: Tipo de motor (JET, TURBOPROP, PISTON)
        mtow_kg: Peso máximo al despegue en kg
        manufacturer: Fabricante de la aeronave
        model: Modelo de la aeronave
    """
    oaci_type: str
    wake_category: str
    engine_type: Optional[str] = None
    mtow_kg: Optional[float] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    
    def __repr__(self):
        return f"AircraftClassification({self.oaci_type}, {self.wake_category})"
    
    def __str__(self):
        return f"{self.oaci_type} [{self.wake_category}]"
