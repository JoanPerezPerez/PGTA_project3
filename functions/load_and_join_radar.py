# functions/load_and_join_radar_IAS.py

import numpy as np
import pandas as pd


# ---------------------------------------------------------
# Utilidades de tiempo
# ---------------------------------------------------------
def time_str_to_seconds(time_str: str) -> float:
    """
    Convierte una cadena de la forma HH:MM:SS[.ms] en segundos.
    No sirve para strings tipo '0 days 00:04:25'.
    """
    parts = str(time_str).split(":")
    if len(parts) == 4:
        h, m, s, ms = parts
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    elif len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    else:
        raise ValueError(f"Formato de tiempo no reconocido: {time_str}")


# ---------------------------------------------------------
# Carga de radar (ASTERIX o CSV procesado)
# ---------------------------------------------------------
def load_radar(path_csv: str) -> pd.DataFrame:
    """
    Igual que antes, pero sin asumir 24L: sirve para cualquier pista.
    """
    # Intentar formato ASTERIX: ';' + ',' y presencia de LAT/LON
    df = pd.read_csv(path_csv, sep=";", decimal=",")
    cols = set(df.columns)

    if "LAT" not in cols and "LON" not in cols:
        df = pd.read_csv(path_csv)
        cols = set(df.columns)

    rename_map = {}
    if "LAT" in cols:
        rename_map["LAT"] = "lat"
    if "LON" in cols:
        rename_map["LON"] = "lon"
    if "H(ft)" in cols:
        rename_map["H(ft)"] = "Hft"
    if "Mode3/A" in cols:
        rename_map["Mode3/A"] = "mode3a"
    if "TI" in cols:
        rename_map["TI"] = "callsign"
    if "TTA" in cols:
        rename_map["TTA"] = "track_true"
    if "TAR" in cols:
        rename_map["TAR"] = "track_rate"
    if "RA" in cols:
        rename_map["RA"] = "ROLL"

    if rename_map:
        df = df.rename(columns=rename_map)
        cols = set(df.columns)

    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"load_radar esperaba un DataFrame, obtuvo {type(df)}")

    for col in ["track_true", "track_rate", "ROLL", "Hft", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # callsign_norm
    cols = set(df.columns)
    if "callsign" in cols:
        base = df["callsign"]
    elif "callsign_norm" in cols:
        base = df["callsign_norm"]
    elif "mode3a" in cols:
        base = df["mode3a"]
    else:
        base = pd.Series([""] * len(df))

    df["callsign_norm"] = base.astype(str).str.strip().str.upper()

    # time_seconds
    cols = set(df.columns)
    if "time_seconds" not in cols:
        if "Time" in cols:
            df["time_seconds"] = df["Time"].apply(time_str_to_seconds)
        else:
            raise KeyError(
                "No se encuentra ni 'time_seconds' ni 'Time' en el CSV radar. "
                f"Columnas disponibles: {sorted(df.columns)}"
            )

    return df


# ---------------------------------------------------------
# Carga plan de vuelos SIN filtrar pista
# ---------------------------------------------------------
def load_departures_all(path_excel: str) -> pd.DataFrame:
    """
    Carga P3_DEP_LEBL.xlsx sin filtrar por PistaDesp.
    Debe existir 'Indicativo_norm', 'PistaDesp' y 'ATOT'.
    """
    df_plan = pd.read_excel(path_excel)

    if "Indicativo" not in df_plan.columns:
        raise KeyError("El plan no tiene columna 'Indicativo'")
    if "PistaDesp" not in df_plan.columns:
        raise KeyError("El plan no tiene columna 'PistaDesp'")
    if "ATOT" not in df_plan.columns:
        raise KeyError("El plan no tiene columna 'ATOT'")

    # ATOT_seconds
    if pd.api.types.is_datetime64_any_dtype(df_plan["ATOT"]):
        df_plan["ATOT_seconds"] = (
            df_plan["ATOT"].dt.hour * 3600
            + df_plan["ATOT"].dt.minute * 60
            + df_plan["ATOT"].dt.second
        )
    elif pd.api.types.is_timedelta64_dtype(df_plan["ATOT"]):
        df_plan["ATOT_seconds"] = df_plan["ATOT"].dt.total_seconds()
    else:
        df_plan["ATOT_seconds"] = (
            df_plan["ATOT"].astype(str).apply(time_str_to_seconds)
        )

    return df_plan


# ---------------------------------------------------------
# Aproximación de las cabeceras 24L y 06R
# (tomadas de info pública de LEBL) [web:21][web:24]
# ---------------------------------------------------------
RWY24L_LAT = 41.2925  # aprox umbral 24L
RWY24L_LON = 2.1033
RWY06R_LAT = 41.2823  # aprox umbral 06R
RWY06R_LON = 2.0744


def _haversine(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos puntos (lat/lon en grados)."""
    R = 6371000.0
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)
    dlat = lat2 - lat1
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------
# Join plan (todas pistas) + radar con filtro por pista
# ---------------------------------------------------------
def join_plan_radar(path_excel: str,
                    path_csv: str,
                    runway: str) -> pd.DataFrame:
    """
    Une P3_DEP_LEBL (todas las pistas) con radar, filtrando por runway:

    - runway debe ser algo como 'LEBL-24L' o 'LEBL-06R' (como en PistaDesp).
    - Join por Indicativo_norm ↔ callsign_norm.
    - Filtro temporal: solo trazas dentro de ±5 min del ATOT.
    - Filtro geométrico: primer punto de cada id debe estar cerca de la cabecera
      de la pista elegida.
    """

    # 1) Plan SOLO de la pista indicada
    df_plan_all = load_departures_all(path_excel)
    df_plan = df_plan_all[df_plan_all["PistaDesp"] == runway].copy()
    if df_plan.empty:
        raise ValueError(f"No hay salidas para la pista {runway} en el plan")

    # 2) Radar
    df_radar = load_radar(path_csv)

    # 3) Merge por callsign_norm
    df = df_radar.merge(
        df_plan,
        left_on="callsign_norm",
        right_on="Indicativo",
        how="inner",
        suffixes=("", "_plan"),
    )

    # 4) Filtro temporal ±5 minutos alrededor del ATOT
    WINDOW_SECONDS = 5 * 60
    df = df[
        (df["time_seconds"] >= df["ATOT_seconds"] - WINDOW_SECONDS)
        & (df["time_seconds"] <= df["ATOT_seconds"] + WINDOW_SECONDS)
    ].copy()

    if df.empty:
        return df

    # 5) Ordenar por id/time
    if "id" not in df.columns:
        # si no tienes 'id' en P3_DEP, crea uno por (Indicativo_norm, ATOT)
        df["id"] = (
            df["Indicativo"].astype(str)
            + "_"
            + df["ATOT_seconds"].astype(int).astype(str)
        )

    df = df.sort_values(["id", "time_seconds"]).reset_index(drop=True)

    # 6) Filtro geométrico según runway
    if runway.endswith("24L"):
        rwy_lat, rwy_lon = RWY24L_LAT, RWY24L_LON
    elif runway.endswith("06R"):
        rwy_lat, rwy_lon = RWY06R_LAT, RWY06R_LON
    else:
        raise ValueError(f"Pista {runway} no soportada para filtro geométrico")

    first_points = df.groupby("id").first().reset_index()
    first_points["dist_rwy_m"] = _haversine(
        first_points["lat"], first_points["lon"], rwy_lat, rwy_lon
    )

    MAX_DIST = 2000.0  # 2 km alrededor del umbral
    ids_ok = set(first_points[first_points["dist_rwy_m"] <= MAX_DIST]["id"])

    df = df[df["id"].isin(ids_ok)].copy()
    df = df.sort_values(["id", "time_seconds"]).reset_index(drop=True)

    return df
