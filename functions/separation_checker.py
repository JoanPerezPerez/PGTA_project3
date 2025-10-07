"""
separation_checker.py - Funciones para verificar separaciones mínimas
Proyecto 3 - PGTA
"""

from typing import Tuple, Optional
import constants
import math


def check_radar_separation(distance_nm: float, zone: str = 'TWR') -> bool:
    """
    Verifica si se cumple la mínima separación radar según la zona.
    
    Args:
        distance_nm: Distancia en millas náuticas
        zone: Zona donde se evalúa ('TWR' o 'TMA')
    
    Returns:
        True si hay incumplimiento (distancia < mínima), False si se cumple
        
    Raises:
        ValueError: Si zone no es válida o distance_nm es inválida
    """
    # Validar entrada
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


# Mapeo de categorías de estela (extraído como constante para mejor mantenimiento)
WAKE_CATEGORY_MAPPING = {
    'PESADA': 'HEAVY',
    'HEAVY': 'HEAVY',
    'MEDIA': 'MEDIUM',
    'MEDIUM': 'MEDIUM',
    'LIGERA': 'LIGHT',
    'LIGHT': 'LIGHT',
    'SUPER': 'SUPER',
    'UNKNOWN': 'UNKNOWN',
}


def normalize_wake_category(wake: Optional[str]) -> str:
    """
    Normaliza la categoría de estela a formato estándar.
    
    Args:
        wake: Categoría de estela (puede ser None o string)
    
    Returns:
        Categoría normalizada ('SUPER', 'HEAVY', 'MEDIUM', 'LIGHT', 'UNKNOWN')
    """
    if not wake or wake == '-':
        return 'UNKNOWN'
    
    wake_upper = wake.strip().upper()
    return WAKE_CATEGORY_MAPPING.get(wake_upper, 'UNKNOWN')


def check_wake_turbulence_separation(
    preceding_wake: str,
    following_wake: str,
    distance_nm: float
) -> Tuple[bool, Optional[float]]:
    """
    Verifica si se cumple la separación por estela turbulenta.
    Aplicable tanto en TWR como en TMA.
    
    Args:
        preceding_wake: Categoría de estela precedente
        following_wake: Categoría de estela siguiente
        distance_nm: Distancia actual en NM
    
    Returns:
        Tuple (incumplimiento, separación_requerida)
        - incumplimiento: True si no se cumple la separación
        - separación_requerida: Separación mínima en NM, None si no aplica
    """
    # Normalizar categorías
    prec_wake = normalize_wake_category(preceding_wake)
    foll_wake = normalize_wake_category(following_wake)
    
    # Si alguna es desconocida, no aplica separación por estela
    if prec_wake == 'UNKNOWN' or foll_wake == 'UNKNOWN':
        return False, None
    
    key = (prec_wake, foll_wake)
    
    if key not in constants.WAKE_TURBULENCE_SEPARATION:
        return False, None  # No aplica separación por estela
    
    required_separation = constants.WAKE_TURBULENCE_SEPARATION[key]
    incumplimiento = distance_nm < required_separation
    
    return incumplimiento, required_separation


def get_wake_category_priority(wake: str) -> int:
    """
    Devuelve un valor numérico de prioridad para la categoría de estela.
    Útil para ordenamiento y comparaciones.
    
    Args:
        wake: Categoría de estela
    
    Returns:
        Valor numérico (mayor = más pesado): 4=SUPER, 3=HEAVY, 2=MEDIUM, 1=LIGHT, 0=UNKNOWN
    """
    wake_normalized = normalize_wake_category(wake)
    
    priorities = {
        'SUPER': 4,
        'HEAVY': 3,
        'MEDIUM': 2,
        'LIGHT': 1,
        'UNKNOWN': 0
    }
    
    return priorities[wake_normalized]

