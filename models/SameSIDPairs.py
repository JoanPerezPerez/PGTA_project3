"""
SameSIDPairs.py
Modelo para parejas con misma SID
Proyecto 3 - PGTA
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SameSIDPair:
    """
    Representa una pareja de despegues consecutivos con la misma SID.
    
    Según diapositiva 44: Se evalúa si ambos aviones siguen la misma SID
    para análisis adicional de separaciones.
    
    Attributes:
        runway: Pista de despegue ('24L' o '06R')
        callsign_preceding: Callsign del avión precedente
        callsign_following: Callsign del avión siguiente
        sid: SID común a ambos aviones
        same_sid: Si ambos tienen la misma SID (True/False)
    """
    runway: str
    callsign_preceding: str
    callsign_following: str
    sid_preceding: str
    sid_following: str
    same_sid: bool = False
    
    def __post_init__(self):
        """Calcula automáticamente si tienen la misma SID."""
        self.same_sid = (self.sid_preceding == self.sid_following and 
                        self.sid_preceding not in ['NO_SID', '', None])
    
    def __repr__(self):
        status = "✓ Misma SID" if self.same_sid else "✗ SIDs diferentes"
        return f"SameSIDPair({self.callsign_preceding} → {self.callsign_following}: {status})"
    
    def __str__(self):
        if self.same_sid:
            return f"{self.callsign_preceding} → {self.callsign_following} [{self.sid_preceding}]"
        else:
            return f"{self.callsign_preceding} [{self.sid_preceding}] → {self.callsign_following} [{self.sid_following}]"
