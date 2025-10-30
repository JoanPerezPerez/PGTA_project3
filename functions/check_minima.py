from typing import Dict, Optional, Tuple
import pandas as pd
import constants
from functions.geo_utils import calculate_distance_to_threshold

def _compute_thr_distance_from_latlon(
    df: pd.DataFrame,
    lat_cols=("lat","LAT","Lat","Latitude"),
    lon_cols=("lon","LON","Lon","Longitude")
) -> pd.Series:
    lat_name = next((c for c in lat_cols if c in df.columns), None)
    lon_name = next((c for c in lon_cols if c in df.columns), None)
    if lat_name is None or lon_name is None:
        # No se puede calcular de forma automática
        return pd.Series([float("nan")] * len(df), index=df.index)
    lat_vals = pd.to_numeric(df[lat_name], errors="coerce")
    lon_vals = pd.to_numeric(df[lon_name], errors="coerce")

    def _row(la, lo):
        if pd.isna(la) or pd.isna(lo):
            return float("nan")
        d24 = calculate_distance_to_threshold(la, lo, constants.THR_24L_LAT, constants.THR_24L_LON)
        d06 = calculate_distance_to_threshold(la, lo, constants.THR_06R_LAT, constants.THR_06R_LON)
        return min(d24, d06)

    return pd.Series((_row(la, lo) for la, lo in zip(lat_vals, lon_vals)), index=df.index)

def check_minima(
    distances_df: pd.DataFrame,
    distance_col: str = "distance_nm",
    tick_time_col: str = "tick_time_s",
    thr_col: str = "thr_distance_nm",
    pair_keys=("callsign_preceding", "callsign_following"),
    tower_threshold_nm: float = 0.5,
) -> pd.DataFrame:
    """
    Verifica, para cada pareja única:
      - Si existe detección radar en zona TWR (thr_distance_nm > 0.5 NM)
      - Si existe infracción de mínima radar (distance_nm < constants.MINIMA) en TMA
        — también por encima de 0.5 NM.

    Devuelve un DataFrame con una fila por pareja y las columnas:
      callsign_preceding, callsign_following, detected_TWR, incumple_TMA
    """

    if distance_col not in distances_df.columns:
        raise KeyError(f"Falta columna de distancia: {distance_col}")
    if tick_time_col not in distances_df.columns:
        raise KeyError(f"Falta columna de tiempo: {tick_time_col}")
    if thr_col not in distances_df.columns:
        raise KeyError(f"Falta columna de distancia al threshold: {thr_col}")

    df = distances_df.copy()

    # Convertir columnas a numéricas por seguridad
    df[distance_col] = pd.to_numeric(df[distance_col], errors="coerce")
    df[thr_col] = pd.to_numeric(df[thr_col], errors="coerce")

    # Definir condiciones
    df["in_TWR_zone"] = df[thr_col] > tower_threshold_nm
    df["in_TMA_zone"] = df[thr_col] > tower_threshold_nm  # Mismo rango pero con otra lógica

    # Infracción de mínima radar
    minima_nm = float(constants.MINIMA)
    df["is_below_minima"] = df[distance_col] < minima_nm

    # Evaluar por pareja
    results = []
    for (preceding, following), group in df.groupby(list(pair_keys)):
        # Zona TWR: detección si hay algún punto por encima de 0.5 NM
        detected_twr = group["in_TWR_zone"].any()

        # Zona TMA: infracción si hay alguna distancia < 3 NM en esa zona
        incumple_tma = group.loc[group["in_TMA_zone"], "is_below_minima"].any()

        results.append({
            "callsign_preceding": preceding,
            "callsign_following": following,
            "detected_TWR": detected_twr,
            "incumple_TMA": incumple_tma
        })

    return pd.DataFrame(results)

def check_minima_violations(
    df_distances: pd.DataFrame,
    minima_twr: float = 3.0,  # NM - ajustar según constants.Minima_RADAR
    minima_tma: float = 3.0,  # NM - ajustar según constants.Minima_RADAR
    twr_threshold_distance: float = 0.5,  # NM desde el threshold
    runway_thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
    x_col: str = "X",
    y_col: str = "Y",
    callsign_col: str = "callsign"
) -> pd.DataFrame:
    """
    Verifica incumplimientos de distancias mínimas en zonas TWR y TMA.
    
    TWR: primera detección más allá de 0.5 NM del threshold
    TMA: resto de detecciones más allá de 0.5 NM
    
    Args:
        df_distances: DataFrame con distancias entre vuelos consecutivos
        minima_twr: Distancia mínima permitida en zona TWR
        minima_tma: Distancia mínima permitida en zona TMA
        twr_threshold_distance: Distancia desde threshold para considerar TWR (0.5 NM)
        runway_thresholds: Diccionario con coordenadas de thresholds por pista
        x_col, y_col: Columnas con coordenadas
        callsign_col: Columna con identificador de vuelo
    
    Returns:
        DataFrame con violaciones detectadas
    """
    
    # Si no se proporcionan thresholds, usar un valor por defecto o calcular
    if runway_thresholds is None:
        # En un caso real, aquí se cargarían las coordenadas de los thresholds
        runway_thresholds = {
            # "RWY_NAME": (x_threshold, y_threshold)
            "25L": (0, 0),
            "25R": (0, 0),
            # ... añadir todas las pistas
        }
    
    violations = []
    
    for _, row in df_distances.iterrows():
        # Determinar si es violación en TWR o TMA
        is_twr_violation = False
        is_tma_violation = False
        
        # Calcular distancia desde threshold para ambos vuelos
        # Asumiendo que tenemos información de la pista en el DataFrame
        runway = row.get('runway', None)
        
        if runway and runway in runway_thresholds:
            threshold_x, threshold_y = runway_thresholds[runway]
            
            # Distancia del vuelo precedente al threshold
            dist_pre = _euclidean_nm(
                threshold_x, threshold_y, 
                row['X_pre'], row['Y_pre']
            )
            
            # Distancia del vuelo siguiente al threshold  
            dist_fol = _euclidean_nm(
                threshold_x, threshold_y,
                row['X_fol'], row['Y_fol']
            )
            
            # Verificar condiciones TWR vs TMA
            if (dist_pre <= twr_threshold_distance and 
                dist_fol <= twr_threshold_distance):
                # Ambos dentro de 0.5 NM - no aplicar mínimos radar
                continue
                
            elif (dist_pre <= twr_threshold_distance or 
                  dist_fol <= twr_threshold_distance):
                # Al menos uno dentro de 0.5 NM - considerar TWR
                if row['distance_nm'] < minima_twr:
                    is_twr_violation = True
                    
            else:
                # Ambos más allá de 0.5 NM - considerar TMA
                if row['distance_nm'] < minima_tma:
                    is_tma_violation = True
        
        # Si hay violación, registrar
        if is_twr_violation or is_tma_violation:
            violation_rec = {
                'time_preceding': row['time_preceding'],
                'time_following': row['time_following'],
                'callsign_preceding': row['callsign_preceding'],
                'callsign_following': row['callsign_following'],
                'distance_nm': row['distance_nm'],
                'violation_type': 'TWR' if is_twr_violation else 'TMA',
                'minimum_required': minima_twr if is_twr_violation else minima_tma,
                'X_pre': row['X_pre'],
                'Y_pre': row['Y_pre'],
                'X_fol': row['X_fol'],
                'Y_fol': row['Y_fol']
            }
            
            # Añadir metadatos si existen
            for col in ['runway', 'zone', 'sid']:
                if col in row:
                    violation_rec[col] = row[col]
            
            violations.append(violation_rec)
    
    return pd.DataFrame.from_records(violations)


# Función auxiliar para calcular distancias (debe estar definida)
def _euclidean_nm(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calcula distancia euclídea en NM entre dos puntos."""
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5