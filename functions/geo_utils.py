"""
geo_utils.py - Funciones de proyección estereográfica y cálculo de distancias
Proyecto 3 - PGTA
"""

import math
from typing import Tuple
import main
import constants

def geodetic_to_stereographic(lat: float, lon: float, 
                              lat0: float = constants.TMA_CENTER_LAT, 
                              lon0: float = constants.TMA_CENTER_LON,
                              R: float = constants.RADIO_ESFERA_CONFORME_NM) -> Tuple[float, float]:
    """
    Convierte coordenadas geodésicas (lat, lon) a coordenadas estereográficas (x, y).
    
    Args:
        lat: Latitud en grados decimales
        lon: Longitud en grados decimales
        lat0: Latitud del centro de proyección
        lon0: Longitud del centro de proyección
        R: Radio de la esfera conforme en NM
    
    Returns:
        Tuple (x, y) en millas náuticas
    """
    # Convertir a radianes
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lat0_rad = math.radians(lat0)
    lon0_rad = math.radians(lon0)
    
    # Cálculo de la proyección estereográfica
    dlon = lon_rad - lon0_rad
    
    k = (2 * R) / (1 + math.sin(lat0_rad) * math.sin(lat_rad) + 
                    math.cos(lat0_rad) * math.cos(lat_rad) * math.cos(dlon))
    
    x = k * math.cos(lat_rad) * math.sin(dlon)
    y = k * (math.cos(lat0_rad) * math.sin(lat_rad) - 
             math.sin(lat0_rad) * math.cos(lat_rad) * math.cos(dlon))
    
    return x, y


def calculate_distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calcula la distancia 2D entre dos puntos en el plano proyectado.
    
    Args:
        x1, y1: Coordenadas del primer punto en NM
        x2, y2: Coordenadas del segundo punto en NM
    
    Returns:
        Distancia en millas náuticas
    """
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def calculate_distance_to_threshold(lat: float, lon: float, 
                                    thr_lat: float, thr_lon: float) -> float:
    """
    Calcula la distancia de un punto al umbral de pista.
    
    Args:
        lat, lon: Coordenadas del punto
        thr_lat, thr_lon: Coordenadas del umbral
    
    Returns:
        Distancia en millas náuticas
    """
    x1, y1 = geodetic_to_stereographic(lat, lon)
    x2, y2 = geodetic_to_stereographic(thr_lat, thr_lon)
    return calculate_distance_2d(x1, y1, x2, y2)


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula el rumbo (bearing) entre dos puntos geodésicos.
    
    Args:
        lat1, lon1: Coordenadas del primer punto en grados
        lat2, lon2: Coordenadas del segundo punto en grados
    
    Returns:
        Rumbo en grados (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))
    
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360
