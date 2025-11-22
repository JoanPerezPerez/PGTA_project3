import numpy as np
import pandas as pd
from typing import Tuple

RUNWAY_24L_TRACK = 240.0  # degrees
ROLL_THRESHOLD_DEG = 3.0
MIN_TURN_ALT_FT = 500.0
TURN_TRACK_DIFF_THRESHOLD = 5.0  # diferencia de TTA respecto a 240º para considerar que empieza el giro

# DVOR BCN coordinates (AIP reference)
DVOR_BCN_LAT = 41 + 16/60 + 5.4/3600  # 41°16'05.4"N
DVOR_BCN_LON = 2 + 2/60 + 0.0/3600    # 002°02'00.0"E

# R-234 radial from DVOR BCN (equivalente a la recta costera del AIP)
RADIAL_LIMIT_DEG = 234.0

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the bearing from point 1 to point 2 in degrees (0-360).
    """
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlon_rad = np.radians(lon2 - lon1)

    y = np.sin(dlon_rad) * np.cos(lat2_rad)
    x = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(dlon_rad)

    bearing_rad = np.arctan2(y, x)
    bearing_deg = (np.degrees(bearing_rad) + 360) % 360

    return bearing_deg

def angle_diff(a: float, b: float) -> float:
    """
    Absolute angular difference (0-180) between two angles in degrees.
    """
    diff = (a - b + 180) % 360 - 180
    return abs(diff)

def check_radial_compliance(lat: float, lon: float, alt_ft: float) -> Tuple[bool, float]:
    """
    Check if aircraft position complies with AIP AD-2 LEBL requirement for RWY 24L SIDs:
    - Below 500 ft: must NOT overshoot the R-234 straight line from DVOR BCN.
    - Above 500 ft: no restriction.
    """
    radial_from_dvor = calculate_bearing(DVOR_BCN_LAT, DVOR_BCN_LON, lat, lon)

    if alt_ft < MIN_TURN_ALT_FT:
        # Para RWY 24L, estar “más allá” de la R-234 significa tener un radial menor que 234°
        violates = radial_from_dvor < RADIAL_LIMIT_DEG
        return violates, radial_from_dvor
    else:
        return False, radial_from_dvor

def detect_turn_start_for_flight(group: pd.DataFrame) -> pd.Series:
    """
    Detecta el inicio de viraje de un vuelo:
    - Usa roll (ROLL) como indicio de viraje.
    - Añade detección aproximada por variación de True Track Angle (track_rate/TTA)
      respecto al rumbo pista 24L (~240º).
    - Aplica la restricción AIP de no sobrepasar R-234 por debajo de 500 ft.
    """
    g = group.sort_values("time_seconds").copy()

    # Identificadores básicos
    flight_id = g["id"].iloc[0] if "id" in g.columns else None
    callsign = (
        g["callsign_norm"].iloc[0]
        if "callsign_norm" in g.columns
        else g["callsign"].iloc[0] if "callsign" in g.columns
        else None
    )
    # Extraer Time_despegue (primer timestamp del vuelo)
    time_despegue = g["Time"].iloc[0] if "Time" in g.columns else None

    # Filtrar solo vuelos RWY 24L si existe la columna dep_rwy o PistaDesp
    if "dep_rwy" in g.columns:
        if not (g["dep_rwy"] == "24L").any():
            return _empty_turn_series(flight_id, callsign)
    elif "PistaDesp" in g.columns:
        if not (g["PistaDesp"] == "LEBL-24L").any():
            return _empty_turn_series(flight_id, callsign)

    # Comprobar columnas necesarias
    required_cols = ["ROLL", "Hft", "lat", "lon", "track_rate"]
    if not all(c in g.columns for c in required_cols):
        return _empty_turn_series(flight_id, callsign, compliant=False)

    # Condición roll significativo
    cond_roll = g["ROLL"].abs() >= ROLL_THRESHOLD_DEG
    
    # Condición variación suficiente en track angle respecto a pista 24L
    track_diff = g["track_rate"].apply(lambda x: angle_diff(x, RUNWAY_24L_TRACK))
    cond_track_change = track_diff >= TURN_TRACK_DIFF_THRESHOLD

    # Radial desde DVOR para cada punto
    radiales = calculate_bearing(DVOR_BCN_LAT, DVOR_BCN_LON, g["lat"].to_numpy(), g["lon"].to_numpy())
    g["radial_from_dvor"] = radiales

    # Condición lado permitido bajo 500 ft
    lado_ok_bajo_500 = g["radial_from_dvor"] >= RADIAL_LIMIT_DEG
    cond_alt_ok = (g["Hft"] >= MIN_TURN_ALT_FT) | ((g["Hft"] < MIN_TURN_ALT_FT) & lado_ok_bajo_500)

    # Candidatos a inicio de viraje: roll o track significativo y altitud/posición correcta
    idx_candidates = g.index[(cond_roll | cond_track_change) & cond_alt_ok]

    if len(idx_candidates) == 0:
        return _empty_turn_series(flight_id, callsign, compliant=True, time_despegue=time_despegue)

    idx_turn = idx_candidates[0]
    row = g.loc[idx_turn]

    # Verificar si antes del giro hubo violación (cruce de radial 234 bajo 500 ft)
    prev = g.loc[g["time_seconds"] <= row["time_seconds"]]
    violacion_prev = ((prev["Hft"] < MIN_TURN_ALT_FT) & (prev["radial_from_dvor"] < RADIAL_LIMIT_DEG)).any()
    turn_compliant = not violacion_prev

    return pd.Series(
        {
            "id": flight_id,
            "callsign": callsign,
            "Time_despegue": time_despegue,
            "lat_turn": row["lat"],
            "lon_turn": row["lon"],
            "time_turn": row["Time"] if "Time" in row.index else None,
            "roll_turn_deg": row["ROLL"],
            "track_turn_deg": row["track_rate"],
            "alt_ft_turn": row["Hft"],
            "turn_found": True,
            "turn_compliant": turn_compliant,
            "radial_from_dvor_turn": row["radial_from_dvor"],
            "x_turn": row.get("X", np.nan),
            "y_turn": row.get("Y", np.nan),
        }
    )

def _empty_turn_series(flight_id, callsign, compliant=True, time_despegue=None):
    """ Helper for empty turn detection results """
    return pd.Series(
        {
            "id": flight_id,
            "callsign": callsign,
            "Time_despegue": time_despegue,
            "turn_found": False,
            "turn_compliant": compliant,
            "time_turn": None,
            "time_turn_seconds": np.nan,
            "lat_turn": np.nan,
            "lon_turn": np.nan,
            "x_turn": np.nan,
            "y_turn": np.nan,
            "alt_ft_turn": np.nan,
            "roll_turn_deg": np.nan,
            "track_turn_deg": np.nan,
            "radial_from_dvor_turn": np.nan,
        }
    )

def add_extra_info_to_turns(df_turns: pd.DataFrame, df_joined: pd.DataFrame) -> pd.DataFrame:
    """
    Añade SID, Tipo aeronave, Estela y la columna Atraviesa radial 234 (True/False) al DataFrame de turns.
    """
    # Agrupar info relevante por vuelo (id)
    df_info = df_joined.groupby("id").agg({
        "ProcDesp": "first",    # SID
        "CAT": "first",         # Tipo aeronave
        "SAC": "first"          # Estela (ajusta si tienes un campo mejor)
    }).rename(columns={
        "ProcDesp": "SID",
        "CAT": "TipoAeronave",
        "SAC": "Estela"
    }).reset_index()

    # Calcular si atraviesa radial 234 bajo 500 ft
    def cruza_radial_234(group):
        return ((group["Hft"] < MIN_TURN_ALT_FT) &
                (calculate_bearing(DVOR_BCN_LAT, DVOR_BCN_LON, group["lat"], group["lon"]) < RADIAL_LIMIT_DEG)).any()

    radial_cross = (
        df_joined.groupby("id")
        .apply(cruza_radial_234)
        .rename("Atraviesa_radial_234")
        .reset_index()
    )

    # Merge con df_turns
    df_enriched = df_turns.merge(df_info, on="id", how="left")
    df_enriched = df_enriched.merge(radial_cross, on="id", how="left")

    return df_enriched

def detect_turns_all_flights(df_joined: pd.DataFrame) -> pd.DataFrame:
    """
    Ejecuta detect_turn_start_for_flight para todos los vuelos del dataframe.
    """
    results = df_joined.groupby("id", group_keys=False).apply(detect_turn_start_for_flight)
    df_res = pd.DataFrame(results).reset_index(drop=True)

    # Orden de columnas esperado
    cols_order = [
        "id",
        "callsign",
        "Time_despegue",
        "lat_turn",
        "lon_turn",
        "time_turn",
        "roll_turn_deg",  # RA
        "track_turn_deg", # TTA
        "alt_ft_turn",
        "SID",
        "TipoAeronave",
        "Estela",
        "Atraviesa_radial_234"
    ]
    # Añadir columnas extra antes de ordenar si no existen
    df_res = add_extra_info_to_turns(df_res, df_joined)

    cols_final = [c for c in cols_order if c in df_res.columns]
    df_res = df_res[cols_final]

    if "turn_found" not in df_res.columns:
        df_res["turn_found"] = False
    if "turn_compliant" not in df_res.columns:
        df_res["turn_compliant"] = False

    return df_res
