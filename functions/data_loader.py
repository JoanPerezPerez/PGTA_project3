# extract data from the .csv file

"""
data_loader.py - Funciones para cargar y procesar datos CSV
Proyecto 3 - PGTA
"""

from datetime import datetime
from typing import List

import pandas as pd
from functions.geo_utils import geodetic_to_stereographic
import main
from models.DataItems import DataItem


def parse_csv_to_dataitem_list(csv_file: str) -> List[DataItem]:
    """
    Lee el archivo CSV decodificado y crea una lista de objetos DataItem.
    
    Args:
        csv_file: Ruta al archivo CSV con datos decodificados CAT048
    
    Returns:
        Lista de objetos DataItem
    """
    print(f"Cargando datos desde {csv_file}...")
    df = pd.read_csv(csv_file, sep=';')
    
    print(f"Columnas disponibles en el CSV: {list(df.columns)}")
    
    data_items = []
    
    for idx, row in df.iterrows():
        rho = str(row.get('RHO', 0))
        rho = float(rho.replace(',', '.'))
        
        theta = str(row.get('THETA', 0))
        theta = float(theta.replace(',', '.'))
        
        lat = str(row.get('LAT', 0))
        lat = float(lat.replace(',', '.'))
        
        lon = str(row.get('LON', 0))
        lon = float(lon.replace(',', '.'))
        
        h = str(row.get('H(m)', 0))
        h = float(h.replace(',', '.'))
        
        fl = str(row.get('FL', 0))
        fl = float(fl.replace(',', '.'))
                
        bp = str(row.get('BP', 0))
        bp = float(parse_value(bp.replace(',', '.')))
        
        ra = str(row.get('RA', 0))
        ra = float(ra.replace(',', '.'))
        
        tta = str(row.get('TTA', 0))
        tta = float(parse_value(tta.replace(',', '.')))
        
        gs = str(row.get('GS', 0))
        gs = float(parse_value(gs.replace(',', '.')))
        
        tar = str(row.get('TAR', 0))
        tar = float(parse_value(tar.replace(',', '.')))
        
        tas = str(row.get('TAS', 0))
        tas = float(tas.replace(',', '.'))
        
        hdg = str(row.get('HDG', 0))
        hdg = float(hdg.replace(',', '.'))
        
        ias = str(row.get('IAS', 0))
        ias = float(ias.replace(',', '.'))
        
        bar = str(row.get('BAR', 0))
        bar = float(bar.replace(',', '.'))
        
        ivv = str(row.get('IVV', 0))
        ivv = float(parse_value(ivv.replace(',', '.')))
        
        time_str = row.get('Time', '0')
        t = datetime.strptime(time_str, "%H:%M:%S:%f")
        time = t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6
        # Crear objeto DataItem con los datos del CSV
        item = DataItem(
            time=float(time),
            track_number=int(row.get('TN', 0)) if pd.notna(row.get('TI')) else 0,
            callsign=str(row.get('TI', '')).strip() if pd.notna(row.get('TI')) else None,
            target_address=str(row.get('TA', '')).strip() if pd.notna(row.get('TA')) else None,
            mode_3a=str(row.get('Mode3A', '')).strip() if pd.notna(row.get('Mode3A')) else None,
            
            rho=float(rho) if pd.notna(row.get('RHO')) else 0,
            theta=float(theta) if pd.notna(row.get('THETA')) else 0,
            lat=float(lat),
            lon=float(lon),
            h=float(h),
            fl=float(fl) if pd.notna(fl) else None,
            flight_status=str(row.get('STAT', '')).strip() if pd.notna(row.get('STAT')) else None,
            bds40_bp=float(bp) if pd.notna(bp) else None,
            bds50_roll_angle=float(ra) if pd.notna(ra) else None,
            bds50_true_track_angle=float(tta) if pd.notna(tta) else None,
            bds50_ground_speed=float(gs) if pd.notna(gs) else None,
            bds50_track_angle_rate=float(tar) if pd.notna(tar) else None,
            bds50_true_airspeed=float(tas) if pd.notna(tas) else None,
            bds60_magnetic_heading=float(hdg) if pd.notna(hdg) else None,
            bds60_indicated_airspeed=float(ias) if pd.notna(ias) else None,
            bds60_barometric_altitude_rate=float(bar) if pd.notna(bar) else None,
            bds60_inertial_vertical_velocity=float(ivv) if pd.notna(ivv) else None,
        )
        
        # Calcular coordenadas proyectadas
        x, y = geodetic_to_stereographic(item.lat, item.lon)
        item.x = x
        item.y = y
        
        # Calcular altitud corregida por QNH (simplificado)
        if item.fl is not None:
            item.barometric_altitude = item.fl * 100
        else:
            item.barometric_altitude = item.h
        
        data_items.append(item)
    
    print(f"✓ Cargados {len(data_items)} registros radar.")
    return data_items


def filter_data_items(data_items: List[DataItem]) -> List[DataItem]:
    """
    Aplica los filtros geográficos y de altitud según las diapositivas 33-34.
    
    Args:
        data_items: Lista de objetos DataItem
    
    Returns:
        Lista filtrada de DataItem
    """
    filtered = []
    
    for item in data_items:
        # Filtro geográfico
        if not item.is_in_geographic_filter():
            continue
        
        # Filtro de altitud (≤ 6000 ft)
        if item.barometric_altitude and item.barometric_altitude > 6000:
            continue
        
        # Filtro de FL válido
        if item.fl is None:
            continue
        
        filtered.append(item)
    
    print(f"✓ Después de aplicar filtros: {len(filtered)} registros.")
    return filtered


def parse_value(value):
    if isinstance(value, str) and value.strip().upper() == 'NV':
        return 100000000000  # Valor muy alto para 'NV'
    try:
        return float(value)
    except ValueError:
        return None