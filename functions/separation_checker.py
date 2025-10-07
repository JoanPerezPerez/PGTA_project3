"""
separation_checker.py - Funciones para verificar separaciones mínimas
Proyecto 3 - PGTA
"""

from typing import Tuple, Optional
import constants
import math


def check_radar_separation(distance_nm: float, zone: str = 'TWR') -> bool:
    """Verifica si se cumple la mínima separación radar según la zona."""
    if math.isnan(distance_nm) or math.isinf(distance_nm):
        raise ValueError(f"Distancia inválida: {distance_nm}")
    
    if distance_nm < 0:
        raise ValueError(f"Distancia negativa: {distance_nm} NM")
    
    zone_upper = zone.upper()
    
    if zone_upper == 'TWR':
        minima_nm = constants.MINIMA_RADAR_TWR_NM  # 3 NM
    elif zone_upper == 'TMA':
        minima_nm = constants.MINIMA_RADAR_TMA_NM  # 5 NM
    else:
        raise ValueError(f"Zona no válida: '{zone}'. Debe ser 'TWR' o 'TMA'")
    
    return distance_nm < minima_nm


# Mapeo COMPLETO de categorías de estela
WAKE_CATEGORY_MAPPING = {
    # Español
    'PESADA': 'HEAVY',
    'MEDIA': 'MEDIUM',
    'LIGERA': 'LIGHT',
    # Inglés
    'HEAVY': 'HEAVY',
    'MEDIUM': 'MEDIUM',
    'LIGHT': 'LIGHT',
    'SUPER': 'SUPER',
    # Abreviaturas ICAO (las más comunes)
    'H': 'HEAVY',
    'M': 'MEDIUM',
    'L': 'LIGHT',
    'J': 'SUPER',  # Super/Jumbo
    'S': 'SUPER',
    # Otras variantes
    'UPPER': 'SUPER',
    'UNKNOWN': 'UNKNOWN',
    '': 'UNKNOWN',
    'N/A': 'UNKNOWN',
}


def normalize_wake_category(wake: Optional[str]) -> str:
    """Normaliza la categoría de estela a formato estándar."""
    if wake is None or wake == '-' or wake == '':
        return 'UNKNOWN'
    
    wake_upper = str(wake).strip().upper()
    
    # Intentar mapeo directo
    if wake_upper in WAKE_CATEGORY_MAPPING:
        return WAKE_CATEGORY_MAPPING[wake_upper]
    
    # Si no existe, devolver UNKNOWN
    return 'UNKNOWN'


def check_wake_turbulence_separation(
    preceding_wake: str,
    following_wake: str,
    distance_nm: float,
    debug: bool = False
) -> Tuple[bool, Optional[float]]:
    """
    Verifica si se cumple la separación por estela turbulenta.
    Aplicable tanto en TWR como en TMA.
    """
    # Normalizar categorías
    prec_wake = normalize_wake_category(preceding_wake)
    foll_wake = normalize_wake_category(following_wake)
    
    if debug:
        print(f"    [WAKE] Prec={preceding_wake}→{prec_wake}, Foll={following_wake}→{foll_wake}, Dist={distance_nm:.2f} NM")
    
    # Si alguna es desconocida, no aplica separación por estela
    if prec_wake == 'UNKNOWN' or foll_wake == 'UNKNOWN':
        if debug:
            print(f"    [WAKE] ❌ Alguna categoría UNKNOWN → No aplica separación")
        return False, None
    
    key = (prec_wake, foll_wake)
    
    if key not in constants.WAKE_TURBULENCE_SEPARATION:
        if debug:
            print(f"    [WAKE] ⚠️  Combinación {key} NO está en tabla → No aplica separación")
        return False, None  # No aplica separación por estela
    
    required_separation = constants.WAKE_TURBULENCE_SEPARATION[key]
    incumplimiento = distance_nm < required_separation
    
    if debug:
        status = "❌ INCUMPLIMIENTO" if incumplimiento else "✅ OK"
        print(f"    [WAKE] {status}: {distance_nm:.2f} < {required_separation} NM")
    
    return incumplimiento, required_separation


def get_wake_category_priority(wake: str) -> int:
    """Devuelve un valor numérico de prioridad para la categoría de estela."""
    wake_normalized = normalize_wake_category(wake)
    
    priorities = {
        'SUPER': 4,
        'HEAVY': 3,
        'MEDIUM': 2,
        'LIGHT': 1,
        'UNKNOWN': 0
    }
    
    return priorities[wake_normalized]
