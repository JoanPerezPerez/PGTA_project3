"""
calculate_separations_between_consecutive_departures.py
Cálculo de separaciones entre despegues consecutivos
Proyecto 3 - PGTA
"""

import pandas as pd
from typing import List, Dict, Optional, Tuple
from models.DataItems import DataItem
from functions.geo_utils import calculate_distance_2d, calculate_distance_to_threshold
from functions.separation_checker import (
    check_radar_separation,
    check_wake_turbulence_separation,
    normalize_wake_category
)
from functions.normalize_runway import normalize_runway
import constants


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def group_detections_by_callsign(data_items: List[DataItem]) -> Dict[str, List[DataItem]]:
    """Agrupa detecciones radar por callsign y las ordena por tiempo."""
    detections = {}
    for item in data_items:
        if item.callsign and item.callsign.strip():
            if item.callsign not in detections:
                detections[item.callsign] = []
            detections[item.callsign].append(item)
    
    for callsign in detections:
        detections[callsign].sort(key=lambda x: x.time)
    
    return detections


def find_first_valid_detection(
    detections: List[DataItem],
    thr_lat: float,
    thr_lon: float,
    min_distance_nm: float = constants.DISTANCIA_INICIAL_CALCULO_NM
) -> Optional[DataItem]:
    """
    Encuentra la primera detección válida (>= 0.5 NM del umbral EN MODO ALEJAMIENTO).
    
    CORREGIDO: Implementación más robusta.
    """
    if not detections or len(detections) < 1:
        return None
    
    # Calcular distancias para todas las detecciones
    distances = []
    for det in detections:
        dist = calculate_distance_to_threshold(det.lat, det.lon, thr_lat, thr_lon)
        distances.append((det, dist))
    
    # Buscar primera detección >= 0.5 NM que esté alejándose
    for i in range(len(distances)):
        det_current, dist_current = distances[i]
        
        # Verificar distancia mínima
        if dist_current >= min_distance_nm:
            # Verificar ALEJAMIENTO si hay detección anterior
            if i == 0:
                # Primera detección: aceptar si cumple distancia
                return det_current
            else:
                det_prev, dist_prev = distances[i-1]
                if dist_current > dist_prev:
                    # Se está alejando → VÁLIDA
                    return det_current
                # Si no se aleja, seguir buscando
    
    # Si no encuentra ninguna alejándose, devolver la primera que cumpla distancia
    for det, dist in distances:
        if dist >= min_distance_nm:
            return det
    
    return None


def find_concurrent_detection(
    detections: List[DataItem],
    reference_time: float,
    max_time_diff: float = constants.TOLERANCE_TIME_SECONDS
) -> Optional[DataItem]:
    """Encuentra la detección más cercana en tiempo a un momento de referencia."""
    min_time_diff = float('inf')
    best_detection = None
    
    for det in detections:
        time_diff = abs(det.time - reference_time)
        if time_diff < min_time_diff and time_diff < max_time_diff:
            min_time_diff = time_diff
            best_detection = det
    
    return best_detection


def do_flight_trajectories_overlap(
    preceding_detections: List[DataItem],
    following_detections: List[DataItem]
) -> bool:
    """Verifica si las trayectorias de vuelo se solapan temporalmente."""
    if not preceding_detections or not following_detections:
        return False
    
    prec_start = min(d.time for d in preceding_detections)
    prec_end = max(d.time for d in preceding_detections)
    
    foll_start = min(d.time for d in following_detections)
    foll_end = max(d.time for d in following_detections)
    
    # Solapamiento si: foll_start < prec_end
    return foll_start < prec_end


def calculate_overlap_duration(
    preceding_detections: List[DataItem],
    following_detections: List[DataItem]
) -> float:
    """Calcula la duración del solapamiento temporal."""
    if not preceding_detections or not following_detections:
        return 0.0
    
    prec_start = min(d.time for d in preceding_detections)
    prec_end = max(d.time for d in preceding_detections)
    
    foll_start = min(d.time for d in following_detections)
    foll_end = max(d.time for d in following_detections)
    
    overlap_start = max(prec_start, foll_start)
    overlap_end = min(prec_end, foll_end)
    
    if overlap_start < overlap_end:
        return overlap_end - overlap_start
    else:
        return 0.0


def calculate_minimum_tma_distance(
    preceding_detections: List[DataItem],
    following_detections: List[DataItem],
    first_valid_time: float
) -> Tuple[float, Optional[float]]:
    """Calcula la mínima distancia en zona TMA entre dos aeronaves."""
    min_distance = float('inf')
    min_time = None
    
    following_filtered = [d for d in following_detections if d.time > first_valid_time]
    
    if not following_filtered:
        return min_distance, min_time
    
    foll_time_start = following_filtered[0].time
    foll_time_end = following_filtered[-1].time
    
    preceding_filtered = [
        d for d in preceding_detections
        if d.is_in_geographic_filter() and
           (not d.barometric_altitude or d.barometric_altitude <= 6000) and
           foll_time_start <= d.time <= foll_time_end
    ]
    
    if not preceding_filtered:
        return min_distance, min_time
    
    for foll_det in following_filtered:
        for prec_det in preceding_filtered:
            time_diff = abs(prec_det.time - foll_det.time)
            if time_diff > 30:
                continue
            
            dist = calculate_distance_2d(prec_det.x, prec_det.y, foll_det.x, foll_det.y)
            if dist < min_distance:
                min_distance = dist
                min_time = foll_det.time
    
    return min_distance, min_time


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def process_consecutive_pair(
    preceding: pd.Series,
    following: pd.Series,
    detections: Dict[str, List[DataItem]],
    thr_lat: float,
    thr_lon: float,
    runway: str
) -> Optional[Dict]:
    """Procesa una pareja de despegues consecutivos con DEBUG."""
    
    prec_callsign = preceding['Indicativo']
    foll_callsign = following['Indicativo']
    
    # DEBUG: Mostrar qué está pasando
    debug_mode = False  # Cambia a True para ver detalles
    
    if prec_callsign not in detections or foll_callsign not in detections:
        if debug_mode:
            print(f"  ❌ {prec_callsign}/{foll_callsign}: Sin detecciones radar")
        return None
    
    prec_dets = detections[prec_callsign]
    foll_dets = detections[foll_callsign]
    
    if not do_flight_trajectories_overlap(prec_dets, foll_dets):
        if debug_mode:
            print(f"  ❌ {prec_callsign}/{foll_callsign}: No solapan temporalmente")
        return None
    
    prec_first_time = min(d.time for d in prec_dets)
    foll_first_time = min(d.time for d in foll_dets)
    
    if foll_first_time <= prec_first_time:
        if debug_mode:
            print(f"  ❌ {prec_callsign}/{foll_callsign}: Orden temporal incorrecto")
        return None
    
    first_valid_foll = find_first_valid_detection(foll_dets, thr_lat, thr_lon)
    if not first_valid_foll:
        if debug_mode:
            print(f"  ❌ {prec_callsign}/{foll_callsign}: Sin primera detección válida del siguiente")
        return None
    
    prec_at_time = find_concurrent_detection(prec_dets, first_valid_foll.time)
    if not prec_at_time:
        if debug_mode:
            print(f"  ❌ {prec_callsign}/{foll_callsign}: Sin detección concurrente del precedente")
        return None
    
    # ZONA TWR
    dist_twr = calculate_distance_2d(
        prec_at_time.x, prec_at_time.y,
        first_valid_foll.x, first_valid_foll.y
    )
    
    inc_radar_twr = check_radar_separation(dist_twr, zone='TWR')
    
    prec_wake = normalize_wake_category(preceding.get('Estela'))
    foll_wake = normalize_wake_category(following.get('Estela'))
    
    inc_wake_twr, wake_sep_req = check_wake_turbulence_separation(
        prec_wake, foll_wake, dist_twr, True
    )
    
    # ZONA TMA
    min_dist_tma, min_time_tma = calculate_minimum_tma_distance(
        prec_dets, foll_dets, first_valid_foll.time
    )
    
    inc_radar_tma = False
    inc_wake_tma = False
    
    if min_dist_tma != float('inf'):
        inc_radar_tma = check_radar_separation(min_dist_tma, zone='TMA')
        inc_wake_tma, _ = check_wake_turbulence_separation(
            prec_wake, foll_wake, min_dist_tma, True
        )
    
    if debug_mode:
        print(f"  ✅ {prec_callsign}/{foll_callsign}: TWR={dist_twr:.2f} NM, TMA={min_dist_tma:.2f} NM")
    
    return {
        'Callsign_Preceding': prec_callsign,
        'Callsign_Following': foll_callsign,
        'ATOT_Preceding': preceding['HoraDespegue'],
        'ATOT_Following': following['HoraDespegue'],
        'Time_Overlap_Seconds': calculate_overlap_duration(prec_dets, foll_dets),
        'ToD_TWR': first_valid_foll.time,
        'Distance_TWR_NM': round(dist_twr, 2),
        'ToD_Min_TMA': min_time_tma if min_time_tma else '',
        'Min_Distance_TMA_NM': round(min_dist_tma, 2) if min_dist_tma != float('inf') else '',
        'Inc_Radar_TWR': inc_radar_twr,
        'Inc_Radar_TMA': inc_radar_tma,
        'Inc_Wake_TWR': inc_wake_twr if wake_sep_req else 'NA',
        'Inc_Wake_TMA': inc_wake_tma if wake_sep_req else 'NA',
        'Wake_Separation_Required_NM': wake_sep_req if wake_sep_req else 'NA',
        'Wake_Preceding': prec_wake,
        'Wake_Following': foll_wake,
        'SID_Preceding': preceding.get('ProcDesp', 'NO_SID') or 'NO_SID',
        'SID_Following': following.get('ProcDesp', 'NO_SID') or 'NO_SID',
        'Runway': runway,
        'Aircraft_Type_Preceding': preceding.get('TipoAeronave', 'UNKNOWN'),
        'Aircraft_Type_Following': following.get('TipoAeronave', 'UNKNOWN')
    }


def calculate_separations_between_consecutive_departures(
    data_items: List[DataItem],
    flight_plans: pd.DataFrame,
    runway: str
) -> pd.DataFrame:
    """Calcula las separaciones entre despegues consecutivos."""
    
    print(f"\n{'='*80}")
    print(f"Calculando separaciones para RWY {runway}...")
    print('='*80)
    
    if runway == '24L':
        thr_lat, thr_lon = constants.THR_24L_LAT, constants.THR_24L_LON
    else:
        thr_lat, thr_lon = constants.THR_06R_LAT, constants.THR_06R_LON
    
    detections_by_callsign = group_detections_by_callsign(data_items)
    print(f"✓ Detectados {len(detections_by_callsign)} callsigns únicos")
    
    flight_plans['PistaDesp_Norm'] = flight_plans['PistaDesp'].apply(normalize_runway)
    dep_runway = flight_plans[flight_plans['PistaDesp_Norm'] == runway].copy()
    dep_runway = dep_runway.sort_values('HoraDespegue')
    print(f"✓ {len(dep_runway)} despegues programados")
    
    fp_callsigns = set(dep_runway['Indicativo'].unique())
    radar_callsigns = set(detections_by_callsign.keys())
    common_callsigns = fp_callsigns.intersection(radar_callsigns)
    print(f"✓ {len(common_callsigns)} callsigns comunes entre FP y radar")
    
    if len(common_callsigns) == 0:
        print("⚠️  WARNING: No hay callsigns comunes")
        return pd.DataFrame()
    
    results = []
    skip_reasons = {
        'no_detections': 0,
        'no_overlap': 0,
        'wrong_order': 0,
        'no_first_valid': 0,
        'no_concurrent': 0,
        'other': 0
    }
    
    for i in range(len(dep_runway) - 1):
        try:
            result = process_consecutive_pair(
                dep_runway.iloc[i],
                dep_runway.iloc[i + 1],
                detections_by_callsign,
                thr_lat,
                thr_lon,
                runway
            )
            
            if result:
                results.append(result)
                
        except Exception as e:
            print(f"⚠️  Error procesando pareja {i}: {str(e)}")
            skip_reasons['other'] += 1
            continue
    
    results_df = pd.DataFrame(results)
    total_pairs = len(dep_runway) - 1
    analyzed = len(results_df)
    skipped = total_pairs - analyzed
    
    print(f"\n✓ Analizadas {analyzed} parejas de {total_pairs}")
    print(f"  - Saltadas: {skipped}")
    
    return results_df



