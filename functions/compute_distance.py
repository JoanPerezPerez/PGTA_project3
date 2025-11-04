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
    segregando entre TWR (Torre) y TMA según la distancia al threshold.
    
    IMPORTANTE: Calcula distancias en todos los ticks donde ambos vuelos estén
    presentes simultáneamente, no requiere timestamps exactamente iguales.
    
    Lógica de segregación:
    - TWR: Primera detección con ambos aviones a > 0.5 NM del threshold
    - TMA: Distancia mínima del resto de detecciones (excluyendo la primera)
    
    Args:
        df_xy: DataFrame con datos radar (debe incluir X, Y, lat, lon, callsign, Time)
        callsign_col: Nombre de la columna de callsign
        time_col: Nombre de la columna de tiempo
        x_col: Nombre de la columna X (coordenada proyectada en NM)
        y_col: Nombre de la columna Y (coordenada proyectada en NM)
        lat_col: Nombre de la columna de latitud
        lon_col: Nombre de la columna de longitud
        excel_path: Ruta al archivo Excel con el orden de despegues
        threshold_twr_nm: Distancia mínima al threshold para considerar fuera de TWR (default 0.5 NM)
        only_same_runway: Si True, solo calcula distancias entre vuelos de la misma pista
        only_same_sid: Si True, solo calcula distancias entre vuelos con la misma SID
        
    Returns:
        DataFrame con todas las detecciones y columnas adicionales:
        - distance_to_threshold_preceding: distancia del precedente al threshold (NM)
        - distance_to_threshold_following: distancia del siguiente al threshold (NM)
        - both_beyond_threshold: True si ambos están > threshold_twr_nm
    """
    
    # 0. Convertir columna de tiempo a segundos si es necesario
    print(f"  → Verificando formato de tiempo...")
    if df_xy[time_col].dtype == 'object':
        print(f"  → Convirtiendo tiempo de string a segundos...")
        df_xy = df_xy.copy()
        df_xy['time_seconds'] = df_xy[time_col].apply(time_str_to_seconds)
        time_col_numeric = 'time_seconds'
    else:
        time_col_numeric = time_col
    
    # 1. Leer el Excel para obtener el orden de despegues
    print(f"  → Leyendo orden de despegues desde {excel_path}...")
    df_order = pd.read_excel(excel_path, sheet_name="Hoja1")
    
    # Crear diccionarios de mapeo
    callsign_to_id = dict(zip(df_order['Indicativo'], df_order['id']))
    callsign_to_runway = dict(zip(df_order['Indicativo'], df_order['PistaDesp']))
    callsign_to_sid = dict(zip(df_order['Indicativo'], df_order['ProcDesp']))
    
    # 2. Filtrar df_xy para incluir solo callsigns válidos del Excel
    valid_callsigns = set(callsign_to_id.keys())
    df_filtered = df_xy[df_xy[callsign_col].isin(valid_callsigns)].copy()
    
    print(f"  → Vuelos válidos encontrados en radar: {len(df_filtered[callsign_col].unique())}")
    
    # Añadir metadatos de cada vuelo
    df_filtered['id'] = df_filtered[callsign_col].map(callsign_to_id)
    df_filtered['runway'] = df_filtered[callsign_col].map(callsign_to_runway)
    df_filtered['sid'] = df_filtered[callsign_col].map(callsign_to_sid)
    
    # 3. Determinar parejas consecutivas según el orden en Excel
    sorted_ids = sorted(df_filtered['id'].unique())
    pairs = [(sorted_ids[i], sorted_ids[i+1]) for i in range(len(sorted_ids)-1)]
    
    print(f"  → Parejas consecutivas a analizar: {len(pairs)}")
    
    # Mapeo inverso: id -> callsign
    id_to_callsign = {v: k for k, v in callsign_to_id.items()}
    
    # 4. Calcular distancias para cada pareja en cada tick temporal
    results = []
    pairs_processed = 0
    pairs_skipped_no_overlap = 0
    pairs_skipped_filter = 0
    
    for id_prec, id_foll in pairs:
        callsign_prec = id_to_callsign[id_prec]
        callsign_foll = id_to_callsign[id_foll]
        
        # Obtener datos de ambos vuelos
        df_prec = df_filtered[df_filtered[callsign_col] == callsign_prec].copy()
        df_foll = df_filtered[df_filtered[callsign_col] == callsign_foll].copy()
        
        if len(df_prec) == 0 or len(df_foll) == 0:
            pairs_skipped_no_overlap += 1
            continue
        
        # Extraer metadatos
        runway_prec = df_prec['runway'].iloc[0]
        runway_foll = df_foll['runway'].iloc[0]
        sid_prec = df_prec['sid'].iloc[0]
        sid_foll = df_foll['sid'].iloc[0]
        
        # Aplicar filtros opcionales
        if only_same_runway and runway_prec != runway_foll:
            pairs_skipped_filter += 1
            continue
        
        if only_same_sid:
            if sid_prec != sid_foll or sid_prec == '-' or pd.isna(sid_prec):
                pairs_skipped_filter += 1
                continue
        
        # Determinar threshold según pista del precedente
        if runway_prec == 'LEBL-24L':
            thr_lat = constants.THR_24L_LAT
            thr_lon = constants.THR_24L_LON
        elif runway_prec == 'LEBL-06R':
            thr_lat = constants.THR_06R_LAT
            thr_lon = constants.THR_06R_LON
        else:
            print(f"  ⚠ Pista desconocida para {callsign_prec}: {runway_prec}")
            pairs_skipped_filter += 1
            continue
        
        # *** CLAVE: Encontrar período de solapamiento temporal usando columna numérica ***
        time_prec_min = df_prec[time_col_numeric].min()
        time_prec_max = df_prec[time_col_numeric].max()
        time_foll_min = df_foll[time_col_numeric].min()
        time_foll_max = df_foll[time_col_numeric].max()
        
        # Rango de solapamiento
        overlap_start = max(time_prec_min, time_foll_min)
        overlap_end = min(time_prec_max, time_foll_max)
        
        if overlap_start > overlap_end:
            # No hay solapamiento temporal (vuelos no coinciden en el tiempo)
            pairs_skipped_no_overlap += 1
            continue
        
        # Filtrar ambos vuelos al período de solapamiento
        df_prec_overlap = df_prec[
            (df_prec[time_col_numeric] >= overlap_start) & 
            (df_prec[time_col_numeric] <= overlap_end)
        ].copy()
        df_foll_overlap = df_foll[
            (df_foll[time_col_numeric] >= overlap_start) & 
            (df_foll[time_col_numeric] <= overlap_end)
        ].copy()
        
        # Merge usando columna numérica
        merged = pd.merge(
            df_prec_overlap[[time_col, time_col_numeric, callsign_col, x_col, y_col, lat_col, lon_col, 'id']],
            df_foll_overlap[[time_col, time_col_numeric, callsign_col, x_col, y_col, lat_col, lon_col, 'id']],
            on=time_col_numeric,
            how='inner',
            suffixes=('_preceding', '_following')
        )
        
        # Si no hay coincidencias exactas, hacer nearest neighbor
        if len(merged) == 0:
            merged_list = []
            
            for _, row_prec in df_prec_overlap.iterrows():
                time_prec = row_prec[time_col_numeric]
                
                # Calcular diferencia temporal usando valores numéricos
                df_foll_overlap['time_diff'] = abs(df_foll_overlap[time_col_numeric] - time_prec)
                idx_closest = df_foll_overlap['time_diff'].idxmin()
                row_foll = df_foll_overlap.loc[idx_closest]
                
                # Solo considerar si la diferencia es menor a 10 segundos
                if row_foll['time_diff'] > 10:
                    continue
                
                merged_row = {
                    time_col: row_prec[time_col],  # Mantener formato original
                    time_col_numeric: time_prec,
                    f'{callsign_col}_preceding': row_prec[callsign_col],
                    f'{callsign_col}_following': row_foll[callsign_col],
                    f'{x_col}_preceding': row_prec[x_col],
                    f'{y_col}_preceding': row_prec[y_col],
                    f'{lat_col}_preceding': row_prec[lat_col],
                    f'{lon_col}_preceding': row_prec[lon_col],
                    f'{x_col}_following': row_foll[x_col],
                    f'{y_col}_following': row_foll[y_col],
                    f'{lat_col}_following': row_foll[lat_col],
                    f'{lon_col}_following': row_foll[lon_col],
                    'id_preceding': row_prec['id'],
                    'id_following': row_foll['id']
                }
                merged_list.append(merged_row)
            
            if len(merged_list) == 0:
                pairs_skipped_no_overlap += 1
                continue
            
            merged = pd.DataFrame(merged_list)
        
        # Calcular distancias entre aviones y al threshold
        distances = []
        dist_to_thr_prec = []
        dist_to_thr_foll = []
        
        for _, row in merged.iterrows():
            # Distancia entre aviones
            x1 = row[f'{x_col}_preceding']
            y1 = row[f'{y_col}_preceding']
            x2 = row[f'{x_col}_following']
            y2 = row[f'{y_col}_following']
            dist = calculate_distance_2d(x1, y1, x2, y2)
            distances.append(dist)
            
            # Distancia al threshold para cada avión
            lat_prec = row[f'{lat_col}_preceding']
            lon_prec = row[f'{lon_col}_preceding']
            lat_foll = row[f'{lat_col}_following']
            lon_foll = row[f'{lon_col}_following']
            
            d_thr_prec = calculate_distance_to_threshold(lat_prec, lon_prec, thr_lat, thr_lon)
            d_thr_foll = calculate_distance_to_threshold(lat_foll, lon_foll, thr_lat, thr_lon)
            
            dist_to_thr_prec.append(d_thr_prec)
            dist_to_thr_foll.append(d_thr_foll)
        
        merged['distance_nm'] = distances
        merged['distance_to_threshold_preceding'] = dist_to_thr_prec
        merged['distance_to_threshold_following'] = dist_to_thr_foll
        
        # Determinar si ambos están más allá del threshold
        merged['both_beyond_threshold'] = (
            (merged['distance_to_threshold_preceding'] > threshold_twr_nm) &
            (merged['distance_to_threshold_following'] > threshold_twr_nm)
        )
        
        # Añadir metadatos
        merged['runway_preceding'] = runway_prec
        merged['runway_following'] = runway_foll
        merged['sid_preceding'] = sid_prec
        merged['sid_following'] = sid_foll
        
        # Renombrar columnas para claridad
        merged = merged.rename(columns={
            f'{x_col}_preceding': 'X_preceding',
            f'{y_col}_preceding': 'Y_preceding',
            f'{x_col}_following': 'X_following',
            f'{y_col}_following': 'Y_following',
        })
        
        results.append(merged)
        pairs_processed += 1
    
    # 5. Concatenar resultados
    if len(results) == 0:
        print("  ⚠ No se encontraron parejas válidas con datos simultáneos")
        return pd.DataFrame()
    
    df_distances = pd.concat(results, ignore_index=True)
    
    # Usar la columna de tiempo original para ordenar
    if time_col in df_distances.columns:
        df_distances = df_distances.sort_values(by=[time_col_numeric]).reset_index(drop=True)
    else:
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
