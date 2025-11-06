# functions/compute_distance.py
"""
Cálculo de distancias entre vuelos consecutivos con segregación TWR/TMA
Proyecto 3 - PGTA
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from functions.geo_utils import calculate_distance_2d, calculate_distance_to_threshold
import constants


def time_str_to_seconds(time_str: str) -> float:
    """
    Convierte un string de tiempo en formato 'HH:MM:SS:mmm' a segundos desde medianoche.
    
    Args:
        time_str: String de tiempo (ej: '04:01:24:789')
        
    Returns:
        Tiempo en segundos como float
    """
    if isinstance(time_str, (int, float)):
        return float(time_str)
    
    try:
        parts = str(time_str).split(':')
        if len(parts) == 4:
            hours, minutes, seconds, milliseconds = parts
            total_seconds = (int(hours) * 3600 + 
                           int(minutes) * 60 + 
                           int(seconds) + 
                           int(milliseconds) / 1000)
            return total_seconds
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return total_seconds
        else:
            raise ValueError(f"Formato de tiempo no reconocido: {time_str}")
    except Exception as e:
        raise ValueError(f"Error convirtiendo tiempo '{time_str}': {e}")


def compute_distance(
    df_xy: pd.DataFrame,
    callsign_col: str = "callsign",
    time_col: str = "Time",
    x_col: str = "X",
    y_col: str = "Y",
    lat_col: str = "lat",
    lon_col: str = "lon",
    excel_path: str = "Inputs/P3_DEP_LEBL.xlsx",
    threshold_twr_nm: float = 0.5,
    only_same_runway: bool = False,
    only_same_sid: bool = False,
) -> pd.DataFrame:
    """
    Calcula las distancias radar entre parejas de vuelos consecutivos,
    segregando entre TWR y TMA según la distancia al threshold.

    Devuelve todas las detecciones por tick donde ambos vuelos están presentes,
    incluyendo metadatos y las categorías de estela de precedente y siguiente.
    """

    # 0) Asegurar columna temporal numérica
    print("  → Verificando formato de tiempo...")
    if df_xy[time_col].dtype == 'object':
        print("  → Convirtiendo tiempo de string a segundos...")
        df_xy = df_xy.copy()
        df_xy['time_seconds'] = df_xy[time_col].apply(time_str_to_seconds)
        time_col_numeric = 'time_seconds'
    else:
        time_col_numeric = time_col

    # 1) Leer Excel de programa de salidas
    print(f"  → Leyendo orden de despegues desde {excel_path}...")
    df_order = pd.read_excel(excel_path, sheet_name="Hoja1")

    # Normalización y diccionarios de mapeo
    def norm(s):
        return s.astype(str).str.strip().str.upper()

    df_order['Indicativo_norm'] = norm(df_order['Indicativo'])

    callsign_to_id = dict(zip(df_order['Indicativo_norm'], df_order['id']))
    callsign_to_runway = dict(zip(df_order['Indicativo_norm'], df_order['PistaDesp']))
    callsign_to_sid = dict(zip(df_order['Indicativo_norm'], df_order['ProcDesp']))
    callsign_to_wake = dict(zip(
        df_order['Indicativo_norm'],
        df_order['Estela'].astype(str).str.strip().str.capitalize()
    ))

    # 2) Filtrar radar a callsigns válidos
    df_xy = df_xy.copy()
    df_xy[callsign_col] = norm(df_xy[callsign_col])
    valid_callsigns = set(df_order['Indicativo_norm'])
    df_filtered = df_xy[df_xy[callsign_col].isin(valid_callsigns)].copy()

    print(f"  → Vuelos válidos encontrados en radar: {len(df_filtered[callsign_col].unique())}")

    # Añadir metadatos por vuelo
    df_filtered['id'] = df_filtered[callsign_col].map(callsign_to_id)
    df_filtered['runway'] = df_filtered[callsign_col].map(callsign_to_runway)
    df_filtered['sid'] = df_filtered[callsign_col].map(callsign_to_sid)
    df_filtered['wake_cat'] = df_filtered[callsign_col].map(callsign_to_wake).fillna('Desconocida')

    # 3) Definir parejas consecutivas según id
    sorted_ids = sorted(df_filtered['id'].dropna().unique())
    pairs = [(sorted_ids[i], sorted_ids[i+1]) for i in range(len(sorted_ids)-1)]

    print(f"  → Parejas consecutivas a analizar: {len(pairs)}")

    # Inverso id->callsign
    id_to_callsign = {v: k for k, v in callsign_to_id.items()}

    results = []
    pairs_processed = 0
    pairs_skipped_no_overlap = 0
    pairs_skipped_filter = 0

    for id_prec, id_foll in pairs:
        callsign_prec = id_to_callsign.get(id_prec)
        callsign_foll = id_to_callsign.get(id_foll)

        df_prec = df_filtered[df_filtered['id'] == id_prec].copy()
        df_foll = df_filtered[df_filtered['id'] == id_foll].copy()

        if df_prec.empty or df_foll.empty:
            pairs_skipped_no_overlap += 1
            continue

        runway_prec = df_prec['runway'].iloc[0]
        runway_foll = df_foll['runway'].iloc[0]
        sid_prec = df_prec['sid'].iloc[0]
        sid_foll = df_foll['sid'].iloc[0]
        wake_prec = df_prec['wake_cat'].iloc[0]
        wake_foll = df_foll['wake_cat'].iloc[0]

        if only_same_runway and runway_prec != runway_foll:
            pairs_skipped_filter += 1
            continue
        if only_same_sid:
            if sid_prec != sid_foll or sid_prec == '-' or pd.isna(sid_prec):
                pairs_skipped_filter += 1
                continue

        # Coordinates threshold según pista del precedente
        if runway_prec == 'LEBL-24L':
            thr_lat, thr_lon = constants.THR_24L_LAT, constants.THR_24L_LON
        elif runway_prec == 'LEBL-06R':
            thr_lat, thr_lon = constants.THR_06R_LAT, constants.THR_06R_LON
        else:
            print(f"  ⚠ Pista desconocida para {callsign_prec}: {runway_prec}")
            pairs_skipped_filter += 1
            continue

        # Ventana temporal de solapamiento
        overlap_start = max(df_prec[time_col_numeric].min(), df_foll[time_col_numeric].min())
        overlap_end   = min(df_prec[time_col_numeric].max(), df_foll[time_col_numeric].max())
        if overlap_start > overlap_end:
            pairs_skipped_no_overlap += 1
            continue

        df_prec_o = df_prec[(df_prec[time_col_numeric] >= overlap_start) & (df_prec[time_col_numeric] <= overlap_end)].copy()
        df_foll_o = df_foll[(df_foll[time_col_numeric] >= overlap_start) & (df_foll[time_col_numeric] <= overlap_end)].copy()

        merged = pd.merge(
            df_prec_o[[time_col, time_col_numeric, callsign_col, x_col, y_col, lat_col, lon_col, 'id']],
            df_foll_o[[time_col, time_col_numeric, callsign_col, x_col, y_col, lat_col, lon_col, 'id']],
            on=time_col_numeric,
            how='inner',
            suffixes=('_preceding', '_following')
        )

        if merged.empty:
            rows = []
            for _, rprec in df_prec_o.iterrows():
                t = rprec[time_col_numeric]
                df_foll_o['time_diff'] = (df_foll_o[time_col_numeric] - t).abs()
                idx = df_foll_o['time_diff'].idxmin()
                rfoll = df_foll_o.loc[idx]
                if df_foll_o.loc[idx, 'time_diff'] > 10:
                    continue
                rows.append({
                    time_col: rprec[time_col],
                    time_col_numeric: t,
                    f'{callsign_col}_preceding': rprec[callsign_col],
                    f'{callsign_col}_following': rfoll[callsign_col],
                    f'{x_col}_preceding': rprec[x_col],
                    f'{y_col}_preceding': rprec[y_col],
                    f'{lat_col}_preceding': rprec[lat_col],
                    f'{lon_col}_preceding': rprec[lon_col],
                    f'{x_col}_following': rfoll[x_col],
                    f'{y_col}_following': rfoll[y_col],
                    f'{lat_col}_following': rfoll[lat_col],
                    f'{lon_col}_following': rfoll[lon_col],
                    'id_preceding': rprec['id'],
                    'id_following': rfoll['id']
                })
            if not rows:
                pairs_skipped_no_overlap += 1
                continue
            merged = pd.DataFrame(rows)

        # Distancias
        d_pair, d_thr_p, d_thr_f = [], [], []
        for _, row in merged.iterrows():
            dist = calculate_distance_2d(row[f'{x_col}_preceding'], row[f'{y_col}_preceding'],
                                         row[f'{x_col}_following'], row[f'{y_col}_following'])
            d_pair.append(dist)
            d_thr_p.append(calculate_distance_to_threshold(row[f'{lat_col}_preceding'], row[f'{lon_col}_preceding'], thr_lat, thr_lon))
            d_thr_f.append(calculate_distance_to_threshold(row[f'{lat_col}_following'], row[f'{lon_col}_following'], thr_lat, thr_lon))

        merged['distance_nm'] = d_pair
        merged['distance_to_threshold_preceding'] = d_thr_p
        merged['distance_to_threshold_following'] = d_thr_f
        merged['both_beyond_threshold'] = (
            (merged['distance_to_threshold_preceding'] > threshold_twr_nm) &
            (merged['distance_to_threshold_following'] > threshold_twr_nm)
        )

        # Metadatos y categorías
        merged['runway_preceding'] = runway_prec
        merged['runway_following'] = runway_foll
        merged['sid_preceding'] = sid_prec
        merged['sid_following'] = sid_foll
        merged['callsign_preceding'] = callsign_prec
        merged['callsign_following'] = callsign_foll
        merged['wake_cat_preceding'] = wake_prec
        merged['wake_cat_following'] = wake_foll

        # Renombrado de coordenadas
        merged = merged.rename(columns={
            f'{x_col}_preceding': 'X_preceding',
            f'{y_col}_preceding': 'Y_preceding',
            f'{x_col}_following': 'X_following',
            f'{y_col}_following': 'Y_following',
        })

        results.append(merged)
        pairs_processed += 1

    if not results:
        print("  ⚠ No se encontraron parejas válidas con datos simultáneos")
        return pd.DataFrame()

    df_distances = pd.concat(results, ignore_index=True)
    df_distances = df_distances.sort_values(by=[time_col_numeric]).reset_index(drop=True)

    print(f"  ✓ Parejas procesadas: {pairs_processed}")
    print(f"  ⚠ Parejas sin solapamiento temporal: {pairs_skipped_no_overlap}")
    print(f"  ⚠ Parejas filtradas (runway/SID): {pairs_skipped_filter}")
    print(f"  ✓ Total de registros de distancia: {len(df_distances)}")

    return df_distances

def get_twr_tma_distances(df_distances: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae las distancias segregadas por TWR y TMA para cada pareja.
    
    Lógica:
    - TWR: Primera detección con ambos aviones > 0.5 NM del threshold
    - TMA: Distancia mínima del resto de detecciones (excluyendo la primera válida)
    
    Args:
        df_distances: DataFrame resultado de compute_distance()
        
    Returns:
        DataFrame con una fila por pareja conteniendo:
        - Datos TWR: distance_twr_nm, time_twr
        - Datos TMA: distance_tma_nm, time_tma (mínima)
        - Metadatos de la pareja
    """
    
    if len(df_distances) == 0:
        return pd.DataFrame()
    
    # Determinar columna de tiempo a usar
    time_col = 'time_seconds' if 'time_seconds' in df_distances.columns else 'Time'
    
    grouped = df_distances.groupby(['id_preceding', 'id_following'])
    
    results = []
    pairs_without_valid_detections = 0
    
    for (id_prec, id_foll), group in grouped:
        # Filtrar detecciones válidas (ambos más allá del threshold)
        valid_detections = group[group['both_beyond_threshold'] == True].copy()
        
        if len(valid_detections) == 0:
            # No hay detecciones válidas, intentar usar todas las detecciones
            print(f"  ⚠ Pareja {id_prec}→{id_foll}: Sin detecciones con ambos > 0.5 NM, usando todas")
            valid_detections = group.copy()
            pairs_without_valid_detections += 1
        
        # Ordenar por tiempo
        valid_detections = valid_detections.sort_values(time_col)
        
        # TWR: Primera detección (válida o no)
        twr_row = valid_detections.iloc[0]
        distance_twr = twr_row['distance_nm']
        time_twr = twr_row['Time'] if 'Time' in twr_row else twr_row[time_col]
        
        # TMA: Mínima del resto (si hay más de una detección)
        if len(valid_detections) > 1:
            tma_detections = valid_detections.iloc[1:]
            min_idx = tma_detections['distance_nm'].idxmin()
            tma_row = df_distances.loc[min_idx]
            distance_tma = tma_row['distance_nm']
            time_tma = tma_row['Time'] if 'Time' in tma_row else tma_row[time_col]
        else:
            # Solo hay una detección, no hay TMA
            distance_tma = None
            time_tma = None
        
        results.append({
            'id_preceding': id_prec,
            'id_following': id_foll,
            'callsign_preceding': twr_row['callsign_preceding'],
            'callsign_following': twr_row['callsign_following'],
            'wake_cat_preceding': twr_row['wake_cat_preceding'],
            'wake_cat_following': twr_row['wake_cat_following'],
            'runway_preceding': twr_row['runway_preceding'],
            'runway_following': twr_row['runway_following'],
            'sid_preceding': twr_row['sid_preceding'],
            'sid_following': twr_row['sid_following'],
            'distance_twr_nm': distance_twr,
            'time_twr': time_twr,
            'distance_tma_nm': distance_tma,
            'time_tma': time_tma
        })
    
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values('id_preceding').reset_index(drop=True)
    
    print(f"\n  → Distancias TWR/TMA calculadas para {len(df_result)} parejas")
    if pairs_without_valid_detections > 0:
        print(f"  ⚠ {pairs_without_valid_detections} parejas sin detecciones válidas > 0.5 NM")
    
    return df_result
