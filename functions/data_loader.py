"""
data_loader.py - Funciones para cargar y procesar datos CSV
Proyecto 3 - PGTA
"""

from datetime import datetime
from typing import List
import pandas as pd
import math
from functions.geo_utils import geodetic_to_stereographic
from models.DataItems import DataItem


def parse_value(value):
    """
    Parsea valores que pueden ser 'NV', NaN, o numéricos con comas decimales.
    Maneja formato CSV español (comas como decimales).
    """
    if value is None:
        return None
    
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    
    if isinstance(value, (int, float)) and not math.isnan(value):
        return float(value)
    
    if isinstance(value, str):
        value_clean = value.strip().upper()
        
        if value_clean in ['NV', '', 'NA', 'NULL', 'NONE', '-']:
            return None
        
        try:
            result = float(value.strip().replace(',', '.'))
            return result if not (math.isnan(result) or math.isinf(result)) else None
        except (ValueError, AttributeError):
            return None
    
    return None


def parse_time_string(time_str: str) -> float:
    """
    Parsea string de tiempo a segundos desde medianoche.
    Soporta formatos: HH:MM:SS y HH:MM:SS:ffffff
    """
    try:
        t = datetime.strptime(time_str, "%H:%M:%S:%f")
        return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6
    except ValueError:
        try:
            t = datetime.strptime(time_str, "%H:%M:%S")
            return t.hour * 3600 + t.minute * 60 + t.second
        except ValueError:
            print(f"⚠️  Formato de tiempo no reconocido: {time_str}")
            return 0.0


def parse_csv_to_dataitem_list(csv_file: str) -> List[DataItem]:
    """
    Lee el archivo CSV decodificado y crea lista de objetos DataItem.
    
    Args:
        csv_file: Ruta al archivo CSV con datos CAT048 decodificados
    
    Returns:
        Lista de objetos DataItem con callsign válido
    """
    print(f"Cargando datos desde {csv_file}...")
    df = pd.read_csv(csv_file, sep=';')
    
    print(f"Columnas disponibles: {list(df.columns)}")
    print(f"Total filas en CSV: {len(df)}")
    
    data_items = []
    stats = {
        'no_callsign': 0,
        'no_coords': 0,
        'on_ground': 0,
        'errors': 0,
        'valid': 0
    }
    
    for idx, row in df.iterrows():
        try:
            # CRÍTICO: Verificar callsign PRIMERO
            callsign_value = str(row.get('TI', '')).strip()
            
            if not callsign_value or callsign_value.lower() in ['nan', '', 'none']:
                stats['no_callsign'] += 1
                continue
            
            # Parsear valores numéricos
            lat = parse_value(row.get('LAT', 0))
            lon = parse_value(row.get('LON', 0))
            h = parse_value(row.get('H(m)', 0))
            
            # Validar coordenadas esenciales
            if lat is None or lon is None or lat == 0 or lon == 0:
                stats['no_coords'] += 1
                continue
            
            # IMPORTANTE: Filtrar aeronaves on-ground
            flight_status = str(row.get('STAT', '')).strip()
            if 'ground' in flight_status.lower():
                stats['on_ground'] += 1
                continue  # ← CORREGIDO: Saltar SIEMPRE si on-ground
            
            # Parsear tiempo
            time_str = str(row.get('Time', '0'))
            time = parse_time_string(time_str)
            
            # Parsear otros campos
            rho = parse_value(row.get('RHO', 0))
            theta = parse_value(row.get('THETA', 0))
            fl = parse_value(row.get('FL', None))
            
            # Parsear QNH si está disponible (del BDS 4.0 BP)
            bp = parse_value(row.get('BP', None))
            
            # *** CORREGIDO: Validar rango de QNH ***
            qnh = 1013.25  # Default QNE
            if bp is not None and 900 < bp < 1100:  # Rango válido de presión
                qnh = bp
            
            ra = parse_value(row.get('RA', None))
            tta = parse_value(row.get('TTA', None))
            gs = parse_value(row.get('GS', None))
            tar = parse_value(row.get('TAR', None))
            tas = parse_value(row.get('TAS', None))
            hdg = parse_value(row.get('HDG', None))
            ias = parse_value(row.get('IAS', None))
            bar = parse_value(row.get('BAR', None))
            ivv = parse_value(row.get('IVV', None))
            
            # Crear DataItem
            item = DataItem(
                time=float(time),
                track_number=int(row.get('TN', 0)) if pd.notna(row.get('TN')) else 0,
                callsign=callsign_value,
                target_address=str(row.get('TA', '')).strip() if pd.notna(row.get('TA')) else None,
                mode_3a=str(row.get('Mode3/A', '')).strip() if pd.notna(row.get('Mode3/A')) else None,
                rho=float(rho) if rho is not None else 0,
                theta=float(theta) if theta is not None else 0,
                lat=float(lat),
                lon=float(lon),
                h=float(h) if h is not None else 0,
                fl=float(fl) if fl is not None else None,
                flight_status=flight_status,
                bds40_bp=float(bp) if bp is not None else None,
                bds50_roll_angle=float(ra) if ra is not None else None,
                bds50_true_track_angle=float(tta) if tta is not None else None,
                bds50_ground_speed=float(gs) if gs is not None else None,
                bds50_track_angle_rate=float(tar) if tar is not None else None,
                bds50_true_airspeed=float(tas) if tas is not None else None,
                bds60_magnetic_heading=float(hdg) if hdg is not None else None,
                bds60_indicated_airspeed=float(ias) if ias is not None else None,
                bds60_barometric_altitude_rate=float(bar) if bar is not None else None,
                bds60_inertial_vertical_velocity=float(ivv) if ivv is not None else None,
            )

            # Calcular coordenadas proyectadas
            x, y = geodetic_to_stereographic(item.lat, item.lon)
            item.x = x
            item.y = y

            # CORRECCIÓN QNH CORRECTA
            if item.fl is not None:
                # Convertir FL a pies
                fl_feet = item.fl * 100
                
                # Por DEBAJO de 6000 ft: Aplicar corrección QNH
                if fl_feet <= 6000:
                    # Corrección: 1 hPa ≈ 27 pies
                    qnh_correction = (qnh - 1013.25) * 27
                    item.barometric_altitude = fl_feet + qnh_correction
                else:
                    # Por ENCIMA de 6000 ft: Usar FL directamente (ya está en QNE)
                    item.barometric_altitude = fl_feet
            else:
                # Si no hay FL, usar H(m) convertido a pies
                item.barometric_altitude = item.h
            
            # *** CRÍTICO: AÑADIR ITEM A LA LISTA ***
            data_items.append(item)
            stats['valid'] += 1
            
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] <= 5:
                print(f"⚠️  Error fila {idx}: {str(e)}")
    
    # Resumen
    print(f"\n✓ Procesamiento completado:")
    print(f"  - Registros válidos: {stats['valid']}")
    print(f"  - Sin callsign: {stats['no_callsign']}")
    print(f"  - Sin coordenadas: {stats['no_coords']}")
    print(f"  - On-ground (filtrados): {stats['on_ground']}")
    print(f"  - Errores: {stats['errors']}")
    
    # Debug: Callsigns únicos
    unique_callsigns = set([item.callsign for item in data_items])
    print(f"✓ Callsigns únicos: {len(unique_callsigns)}")
    if len(unique_callsigns) > 0:
        sample = sorted(list(unique_callsigns))[:10]
        print(f"  Ejemplos: {', '.join(sample)}")
    
    return data_items


def filter_data_items(data_items: List[DataItem]) -> List[DataItem]:
    """
    Aplica filtros geográficos y de altitud (diapositivas 33-34).
    """
    filtered = []
    stats = {
        'total': len(data_items),
        'geo': 0,
        'alt': 0,
        'fl': 0,
        'passed': 0
    }
    
    for item in data_items:
        # Filtro geográfico
        if not item.is_in_geographic_filter():
            stats['geo'] += 1
            continue
        
        # Filtro altitud
        if item.barometric_altitude and item.barometric_altitude > 6000:
            stats['alt'] += 1
            continue
        
        # Filtro FL válido
        if item.fl is None:
            stats['fl'] += 1
            continue
        
        filtered.append(item)
        stats['passed'] += 1
    
    print(f"\n✓ Filtros aplicados:")
    print(f"  - Total entrada: {stats['total']}")
    print(f"  - Filtrados geografía: {stats['geo']}")
    print(f"  - Filtrados altitud: {stats['alt']}")
    print(f"  - Filtrados FL: {stats['fl']}")
    print(f"  - RESULTADO: {stats['passed']} registros")
    
    return filtered
