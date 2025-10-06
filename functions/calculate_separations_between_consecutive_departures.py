from typing import List
import pandas as pd
#from functions.geo_utils import calculate_distance_2d, calculate_distance_to_threshold
from functions.normalize_runway import normalize_runway
from functions.separation_checker import check_radar_separation, check_wake_turbulence_separation
import main
import constants
from models.DataItems import DataItem

def calculate_separations_between_consecutive_departures(
    data_items: List[DataItem],
    flight_plans: pd.DataFrame,
    runway: str
) -> pd.DataFrame:
    
    from functions.geo_utils import calculate_distance_2d, calculate_distance_to_threshold
    """
    Calcula las separaciones entre despegues consecutivos.
    
    Args:
        data_items: Lista de objetos DataItem filtrados
        flight_plans: DataFrame con los planes de vuelo
        runway: Pista de despegue ('24L' o '06R')
    
    Returns:
        DataFrame con los resultados de separaciones
    """
    print(f"\n{'='*80}")
    print(f"Calculando separaciones para RWY {runway}...")
    print('='*80)
    
    # Determinar umbral según pista
    if runway == '24L':
        thr_lat, thr_lon = constants.THR_24L_LAT, constants.THR_24L_LON
    else:
        thr_lat, thr_lon = constants.THR_06R_LAT, constants.THR_06R_LON
    
    # Agrupar detecciones por callsign
    detections_by_callsign = {}
    for item in data_items:
        if item.callsign and item.callsign.strip():
            if item.callsign not in detections_by_callsign:
                detections_by_callsign[item.callsign] = []
            detections_by_callsign[item.callsign].append(item)
    
    # Ordenar cada grupo por tiempo
    for callsign in detections_by_callsign:
        detections_by_callsign[callsign].sort(key=lambda x: x.time)
    
    print(f"✓ Detectados {len(detections_by_callsign)} callsigns únicos")
    
    # Normalizar columna PistaDesp y filtrar por pista
    flight_plans['PistaDesp_Norm'] = flight_plans['PistaDesp'].apply(normalize_runway)
    dep_runway = flight_plans[flight_plans['PistaDesp_Norm'] == runway].copy()
    dep_runway = dep_runway.sort_values('HoraDespegue')
    
    print(f"✓ {len(dep_runway)} despegues programados en RWY {runway}")
    
    results = []
    
    # Comparar despegues consecutivos
    for i in range(len(dep_runway) - 1):
        preceding = dep_runway.iloc[i]
        following = dep_runway.iloc[i + 1]
        
        preceding_callsign = preceding['Indicativo']
        following_callsign = following['Indicativo']
        
        if preceding_callsign not in detections_by_callsign or following_callsign not in detections_by_callsign:
            continue
        
        preceding_detections = detections_by_callsign[preceding_callsign]
        following_detections = detections_by_callsign[following_callsign]
        
        # Buscar primera detección válida del siguiente (>= 0.5 NM del umbral)
        first_valid_following = None
        for det in following_detections:
            dist_to_thr = calculate_distance_to_threshold(det.lat, det.lon, thr_lat, thr_lon)
            if dist_to_thr >= constants.DISTANCIA_INICIAL_CALCULO_NM:
                first_valid_following = det
                break
        
        if first_valid_following is None:
            continue
        
        # Buscar detección del precedente en ese mismo tiempo
        preceding_at_time = None
        for det in preceding_detections:
            if abs(det.time - first_valid_following.time) < 2:  # Tolerancia de 2 segundos
                preceding_at_time = det
                break
        
        if preceding_at_time is None:
            continue
        
        # Calcular distancia en TWR (primera detección)
        distance_twr = calculate_distance_2d(
            preceding_at_time.x, preceding_at_time.y,
            first_valid_following.x, first_valid_following.y
        )
        
        # Verificar incumplimientos en TWR
        inc_radar_twr = check_radar_separation(distance_twr)
        
        # Obtener categorías de estela (manejar valores vacíos o '-')
        prec_estela = preceding.get('Estela', 'UNKNOWN')
        foll_estela = following.get('Estela', 'UNKNOWN')
        
        if prec_estela == '-' or not prec_estela or pd.isna(prec_estela):
            prec_estela = 'UNKNOWN'
        if foll_estela == '-' or not foll_estela or pd.isna(foll_estela):
            foll_estela = 'UNKNOWN'
        
        inc_wake_twr, wake_sep_required = check_wake_turbulence_separation(
            prec_estela,
            foll_estela,
            distance_twr
        )
        
        # Calcular mínima distancia en TMA (resto de detecciones)
        min_distance_tma = float('inf')
        min_time_tma = None
        
        for prec_det in preceding_detections:
            for foll_det in following_detections:
                if foll_det.time > first_valid_following.time:
                    dist = calculate_distance_2d(prec_det.x, prec_det.y, foll_det.x, foll_det.y)
                    if dist < min_distance_tma:
                        min_distance_tma = dist
                        min_time_tma = foll_det.time
        
        # Verificar incumplimientos en TMA
        inc_radar_tma = check_radar_separation(min_distance_tma) if min_distance_tma != float('inf') else False
        inc_wake_tma, _ = check_wake_turbulence_separation(
            prec_estela,
            foll_estela,
            min_distance_tma
        ) if min_distance_tma != float('inf') else (False, None)
        
        # Obtener ProcDesp (SID) manejando valores vacíos
        prec_sid = preceding.get('ProcDesp', '-')
        foll_sid = following.get('ProcDesp', '-')
        
        if prec_sid == '-' or not prec_sid or pd.isna(prec_sid):
            prec_sid = 'NO_SID'
        if foll_sid == '-' or not foll_sid or pd.isna(foll_sid):
            foll_sid = 'NO_SID'
        
        results.append({
            'Callsign_Preceding': preceding_callsign,
            'Callsign_Following': following_callsign,
            'ATOT_Preceding': preceding['HoraDespegue'],
            'ATOT_Following': following['HoraDespegue'],
            'ToD_TWR': first_valid_following.time,
            'Distance_TWR_NM': round(distance_twr, 2),
            'ToD_Min_TMA': min_time_tma if min_time_tma else '',
            'Min_Distance_TMA_NM': round(min_distance_tma, 2) if min_distance_tma != float('inf') else '',
            'Inc_Radar_TWR': inc_radar_twr,
            'Inc_Radar_TMA': inc_radar_tma,
            'Inc_Wake_TWR': inc_wake_twr if wake_sep_required else 'NA',
            'Inc_Wake_TMA': inc_wake_tma if wake_sep_required else 'NA',
            'Wake_Separation_Required_NM': wake_sep_required if wake_sep_required else 'NA',
            'Wake_Preceding': prec_estela,
            'Wake_Following': foll_estela,
            'SID_Preceding': prec_sid,
            'SID_Following': foll_sid,
            'Runway': runway,
            'Aircraft_Type_Preceding': preceding.get('TipoAeronave', 'UNKNOWN'),
            'Aircraft_Type_Following': following.get('TipoAeronave', 'UNKNOWN')
        })
    
    results_df = pd.DataFrame(results)
    print(f"✓ Analizadas {len(results_df)} parejas de despegues consecutivos.")
    
    return results_df
