import pandas as pd
from typing import List, Optional, Tuple
import math
import constants

def _parse_time_to_seconds(t: str) -> Optional[float]:
    """
    Convierte 'HH:MM:SS:ms' a segundos desde medianoche.
    Ej.: '04:00:11:523' -> 14411.523
    """
    if not isinstance(t, str):
        return None
    parts = t.split(":")
    if len(parts) != 4:
        return None
    hh, mm, ss, ms = parts
    try:
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
    except Exception:
        return None

def _resample_to_radar_ticks(df: pd.DataFrame, time_col: str, tick: float) -> pd.DataFrame:
    """
    Redondea tiempos a múltiplos de 'tick' (p.ej., 4 s) para sincronizar detecciones.
    """
    df = df.copy()
    tsec = df[time_col].astype(str).map(_parse_time_to_seconds)
    df["_tsec"] = tsec
    df = df[pd.notna(df["_tsec"])]
    df["_tick"] = (df["_tsec"] // tick) * tick
    return df

def _euclidean_nm(x1: float, y1: float, x2: float, y2: float) -> float:
    if any(pd.isna([x1, y1, x2, y2])):
        return math.nan
    return math.hypot(x2 - x1, y2 - y1)
def compute_distance(
    df_xy: pd.DataFrame,
    callsign_col: str = "callsign",
    time_col: str = "Time",
    x_col: str = "X",
    y_col: str = "Y",
    runway_col: Optional[str] = None,
    zone_col: Optional[str] = None,
    sid_col: Optional[str] = None,
    only_same_runway: bool = True,
    only_same_sid: bool = False,
) -> pd.DataFrame:
    """
    Calcula distancias entre despegues consecutivos basándose en el orden temporal.
      - Ordena todos los datos por tiempo
      - Aplica criterios de agrupación (pista, SID, zona)
      - Empareja consecutivos dentro de cada grupo y mide distancia 2D entre sus X,Y
      - Solo forma parejas entre callsigns diferentes
    """
    # Asegurar columnas necesarias
    for c in [callsign_col, time_col, x_col, y_col]:
        if c not in df_xy.columns:
            raise KeyError(f"Falta columna requerida: {c}")

    # Trabajar con copia para no modificar original
    work = df_xy.copy()
    
    # Ordenar todo el dataset por tiempo
    work = work.sort_values(by=time_col, kind="mergesort")

    # Definir claves de agrupación según criterios
    group_keys: List[str] = []
    if zone_col and zone_col in work.columns:
        group_keys.append(zone_col)
    if only_same_runway and runway_col and runway_col in work.columns:
        group_keys.append(runway_col)
    if only_same_sid and sid_col and sid_col in work.columns:
        group_keys.append(sid_col)

    # Si no hay criterios de agrupación, tratar todo como un grupo
    if not group_keys:
        group_keys = [None]

    records = []
    
    # Para cada grupo definido por los criterios
    for _, group_data in work.groupby(group_keys, dropna=False) if group_keys != [None] else [(None, work)]:
        
        # Ordenar por tiempo dentro del grupo
        group_sorted = group_data.sort_values(by=time_col, kind="mergesort")
        
        # Generar pares consecutivos
        prev_row = None
        for _, row in group_sorted.iterrows():
            if prev_row is not None and prev_row[callsign_col] != row[callsign_col]:
                d_nm = _euclidean_nm(
                    prev_row[x_col], prev_row[y_col], 
                    row[x_col], row[y_col]
                )
                
                rec = {
                    "time_preceding": prev_row[time_col],
                    "time_following": row[time_col],
                    "callsign_preceding": prev_row[callsign_col],
                    "callsign_following": row[callsign_col],
                    "X_pre": prev_row[x_col],
                    "Y_pre": prev_row[y_col],
                    "X_fol": row[x_col],
                    "Y_fol": row[y_col],
                    "distance_nm": d_nm,
                }
                
                # Rellenar metadatos de criterios si existen
                if zone_col and zone_col in group_sorted.columns:
                    rec[zone_col] = row[zone_col]
                if runway_col and runway_col in group_sorted.columns:
                    rec[runway_col] = row[runway_col]
                if sid_col and sid_col in group_sorted.columns:
                    rec[sid_col] = row[sid_col]
                    
                records.append(rec)
            
            prev_row = row

    out = pd.DataFrame.from_records(records)
    return out