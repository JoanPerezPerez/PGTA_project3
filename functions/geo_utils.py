"""
geo_utils.py - Funciones de proyección estereográfica y cálculo de distancias
Proyecto 3 - PGTA
"""

import math
from typing import Tuple
import constants


def geodetic_to_stereographic(lat: float, lon: float,
                              lat0: float = constants.TMA_CENTER_LAT,
                              lon0: float = constants.TMA_CENTER_LON,
                              R: float = constants.RADIO_ESFERA_CONFORME_NM) -> Tuple[float, float]:
    """
    Convierte coordenadas geodésicas (lat, lon) a coordenadas estereográficas (x, y).
    Según diapositiva 42 del proyecto.
    
    Args:
        lat: Latitud en grados decimales
        lon: Longitud en grados decimales
        lat0: Latitud del centro de proyección (TMA)
        lon0: Longitud del centro de proyección (TMA)
        R: Radio de la esfera conforme en NM
    
    Returns:
        Tuple (x, y) en millas náuticas
    """
    # Validar que las coordenadas están en rangos válidos
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitud fuera de rango: {lat}. Debe estar entre -90 y 90")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitud fuera de rango: {lon}. Debe estar entre -180 y 180")
    
    # Convertir a radianes
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lat0_rad = math.radians(lat0)
    lon0_rad = math.radians(lon0)
    
    # Cálculo de la proyección estereográfica
    # Fórmula según Eurocontrol Translib / geoutils
    dlon = lon_rad - lon0_rad
    
    # Factor de escala k
    denominator = 1 + math.sin(lat0_rad) * math.sin(lat_rad) + \
                  math.cos(lat0_rad) * math.cos(lat_rad) * math.cos(dlon)
    
    if abs(denominator) < 1e-10:
        raise ValueError(f"Denominador muy pequeño en proyección: {denominator}")
    
    k = (2 * R) / denominator
    
    # Coordenadas proyectadas
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
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance


def calculate_distance_to_threshold(lat: float, lon: float,
                                    thr_lat: float, thr_lon: float) -> float:
    """
    Calcula la distancia de un punto al umbral de pista.
    
    Args:
        lat, lon: Coordenadas del punto en grados decimales
        thr_lat, thr_lon: Coordenadas del umbral en grados decimales
    
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


def test_projection():
    """
    Función de prueba para verificar que la proyección funciona correctamente.
    Prueba con los umbrales de pista conocidos.
    """
    print("\n" + "="*80)
    print("TEST DE PROYECCIÓN ESTEREOGRÁFICA")
    print("="*80)
    
    # Centro TMA (debería proyectarse cerca del origen)
    lat_tma = constants.TMA_CENTER_LAT
    lon_tma = constants.TMA_CENTER_LON
    x_tma, y_tma = geodetic_to_stereographic(lat_tma, lon_tma)
    print(f"\nCentro TMA ({lat_tma:.6f}°N, {lon_tma:.6f}°E):")
    print(f"  → x={x_tma:.3f} NM, y={y_tma:.3f} NM")
    print(f"  → Distancia al origen: {math.sqrt(x_tma**2 + y_tma**2):.3f} NM (debe ser ~0)")
    
    # Umbral 24L
    lat_24l = constants.THR_24L_LAT
    lon_24l = constants.THR_24L_LON
    x_24l, y_24l = geodetic_to_stereographic(lat_24l, lon_24l)
    print(f"\nUmbral 24L ({lat_24l:.6f}°N, {lon_24l:.6f}°E):")
    print(f"  → x={x_24l:.3f} NM, y={y_24l:.3f} NM")
    
    # Umbral 06R
    lat_06r = constants.THR_06R_LAT
    lon_06r = constants.THR_06R_LON
    x_06r, y_06r = geodetic_to_stereographic(lat_06r, lon_06r)
    print(f"\nUmbral 06R ({lat_06r:.6f}°N, {lon_06r:.6f}°E):")
    print(f"  → x={x_06r:.3f} NM, y={y_06r:.3f} NM")
    
    # Distancia entre umbrales
    dist_umbr = calculate_distance_2d(x_24l, y_24l, x_06r, y_06r)
    print(f"\nDistancia entre umbrales 24L y 06R: {dist_umbr:.3f} NM")
    print(f"  (debe ser aprox. 1.6-2.0 NM para pistas paralelas de LEBL)")
    
    print("\n" + "="*80)


# Si ejecutas este archivo directamente, hace las pruebas
if __name__ == "__main__":
    test_projection()
