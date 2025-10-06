"""
separation_checker.py - Funciones para verificar separaciones mínimas
Proyecto 3 - PGTA
"""

from typing import Tuple, Dict, Optional 
import main
import constants


def check_radar_separation(distance_nm: float, 
                           minima_nm: float = constants.MINIMA_RADAR_NM) -> bool:
    """
    Verifica si se cumple la mínima separación radar.
    
    Args:
        distance_nm: Distancia en millas náuticas
        minima_nm: Mínima separación requerida en NM
    
    Returns:
        True si hay incumplimiento (distancia < mínima), False si se cumple
    """
    return distance_nm < minima_nm


def check_wake_turbulence_separation(preceding_wake: str, 
                                     following_wake: str, 
                                     distance_nm: float) -> Tuple[bool, Optional[float]]:
    """
    Verifica si se cumple la separación por estela turbulenta.
    
    Args:
        preceding_wake: Categoría de estela de la aeronave precedente (SUPER/HEAVY/MEDIUM/LIGHT)
        following_wake: Categoría de estela de la aeronave siguiente
        distance_nm: Distancia actual en NM
    
    Returns:
        Tuple (incumplimiento, separación_requerida)
        - incumplimiento: True si no se cumple la separación
        - separación_requerida: Separación mínima requerida en NM, None si no aplica
    """
    # Normalizar categorías
    prec_wake = preceding_wake.upper().strip() if preceding_wake else ''
    foll_wake = following_wake.upper().strip() if following_wake else ''
    
    key = (prec_wake, foll_wake)
    
    if key not in constants.WAKE_TURBULENCE_SEPARATION:
        return False, None  # No aplica separación por estela
    
    required_separation = constants.WAKE_TURBULENCE_SEPARATION[key]
    incumplimiento = distance_nm < required_separation
    
    return incumplimiento, required_separation


def check_loa_separation(preceding_category: str, 
                        preceding_motor: str,
                        following_category: str,
                        following_motor: str,
                        same_sid: bool,
                        distance_nm: float,
                        loa_table: Dict) -> Tuple[bool, Optional[float]]:
    """
    Verifica si se cumple la separación por Carta de Acuerdo (LoA) TWR-TMA.
    
    Args:
        preceding_category: Categoría del precedente (HP/LP/NR/NR-/NR--)
        preceding_motor: Motor del precedente (R/NR)
        following_category: Categoría del siguiente
        following_motor: Motor del siguiente
        same_sid: True si ambos vuelan la misma SID
        distance_nm: Distancia actual en NM
        loa_table: Diccionario con las separaciones LoA
    
    Returns:
        Tuple (incumplimiento, separación_requerida)
    """
    # Construir clave para la tabla LoA
    key = (preceding_category.upper(), preceding_motor.upper(),
           following_category.upper(), following_motor.upper())
    
    if key not in loa_table:
        return False, None  # No aplica LoA
    
    # Obtener separación requerida según si es misma SID o distinta SID
    loa_entry = loa_table[key]
    if same_sid:
        required_separation = loa_entry.get('same_sid', main.MINIMA_RADAR_NM)
    else:
        required_separation = loa_entry.get('different_sid', main.MINIMA_RADAR_NM)
    
    incumplimiento = distance_nm < required_separation
    
    return incumplimiento, required_separation


def is_moving_away_from_threshold(current_distance: float, 
                                  previous_distance: Optional[float] = None) -> bool:
    """
    Verifica si la aeronave se está alejando del umbral.
    
    Args:
        current_distance: Distancia actual al umbral en NM
        previous_distance: Distancia previa al umbral (opcional)
    
    Returns:
        True si se está alejando del umbral
    """
    if previous_distance is None:
        return current_distance >= constants.DISTANCIA_INICIAL_CALCULO_NM
    
    return current_distance > previous_distance


def get_wake_category_priority(wake: str) -> int:
    """
    Devuelve un valor numérico de prioridad para la categoría de estela.
    Útil para ordenar o comparar categorías.
    
    Args:
        wake: Categoría de estela (SUPER/HEAVY/MEDIUM/LIGHT)
    
    Returns:
        Valor numérico (mayor = más pesado)
    """
    priorities = {
        'SUPER': 4,
        'HEAVY': 3,
        'MEDIUM': 2,
        'LIGHT': 1
    }
    return priorities.get(wake.upper().strip(), 0)
