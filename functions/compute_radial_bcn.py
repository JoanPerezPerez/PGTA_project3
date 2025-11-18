# functions/compute_radial_bcn.py
import math
import pandas as pd
import constants
from functions.geo_utils import calculate_bearing

def add_radial_from_bcn(df_turns: pd.DataFrame) -> pd.DataFrame:
    """
    Añade 'radial_from_bcn_deg' usando las columnas de posición que haya en df_turns.
    Intenta primero lat_turn/lon_turn y, si no existen, usa lat/lon.
    """
    df = df_turns.copy()

    # Detectar columnas de lat/lon disponibles
    if "lat_turn" in df.columns and "lon_turn" in df.columns:
        lat_col = "lat_turn"
        lon_col = "lon_turn"
    elif "lat" in df.columns and "lon" in df.columns:
        lat_col = "lat"
        lon_col = "lon"
    else:
        raise RuntimeError(f"No se han encontrado columnas de latitud/longitud en df_turns: {df.columns.tolist()}")

    lat_bcn = constants.DVOR_BCN_LAT
    lon_bcn = constants.DVOR_BCN_LON

    radiales = []
    for _, row in df.iterrows():
        lat = row[lat_col]
        lon = row[lon_col]

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            radiales.append(math.nan)
            continue

        r = calculate_bearing(lat_bcn, lon_bcn, lat_f, lon_f)
        radiales.append(r)

    df["radial_from_bcn_deg"] = radiales
    return df
