import numpy as np
import pandas as pd


# --- Utilidad tiempo ---
def time_str_to_seconds(time_str: str) -> float:
    parts = str(time_str).split(":")
    if len(parts) == 4:
        h, m, s, ms = parts
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    elif len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    else:
        raise ValueError(f"Formato de tiempo no reconocido: {time_str}")


# --- Carga radar sin filtrar pista ---
def load_radar(path_csv: str) -> pd.DataFrame:
    df = pd.read_csv(path_csv, sep=";")  # asumimos CSV ASTERIX con ';'
    cols = set(df.columns)

    rename_map = {}
    if "LAT" in cols:
        rename_map["LAT"] = "lat"
    if "LON" in cols:
        rename_map["LON"] = "lon"
    if "H(ft)" in cols:
        rename_map["H(ft)"] = "Hft"
    if "TI" in cols:
        rename_map["TI"] = "callsign"
    if "mode3a" in cols:
        rename_map["mode3a"] = "mode3a"  # por si se usa
    if "Time" in cols:
        rename_map["Time"] = "Time"

    if rename_map:
        df = df.rename(columns=rename_map)

    # Asegurar numéricos
    for col in ["Hft", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # limpiar callsign_norm
    if "callsign" in df.columns:
        df["callsign_norm"] = df["callsign"].astype(str).str.strip().str.upper()
    else:
        df["callsign_norm"] = ""

    # tiempo en segundos
    if "time_seconds" not in df.columns:
        if "Time" in df.columns:
            df["time_seconds"] = df["Time"].apply(time_str_to_seconds)
    return df


# --- Carga plan vuelos sin filtro pista ---
def load_plan(path_excel: str) -> pd.DataFrame:
    df_plan = pd.read_excel(path_excel)

    # Añadir ATOT_seconds
    if "ATOT" in df_plan.columns:
        if pd.api.types.is_datetime64_any_dtype(df_plan["ATOT"]):
            df_plan["ATOT_seconds"] = (
                df_plan["ATOT"].dt.hour * 3600 +
                df_plan["ATOT"].dt.minute * 60 +
                df_plan["ATOT"].dt.second
            )
        else:
            df_plan["ATOT_seconds"] = df_plan["ATOT"].astype(str).apply(time_str_to_seconds)
    else:
        raise KeyError("El plan de vuelos no contiene columna 'ATOT'")
    return df_plan


# --- Haversine ---
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    lat1, lat2 = np.radians(lat1), np.radians(lat2)
    dlat = lat2 - lat1
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


# --- Unión plan + radar con filtros temporal y geométrico para cualquier pista ---
def join_plan_radar(path_excel: str, path_csv: str, runway:str) -> pd.DataFrame:
    df_plan = load_plan(path_excel)
    df_radar = load_radar(path_csv)

    df = df_radar.merge(df_plan, left_on="callsign_norm", right_on="Indicativo_norm", how="inner")

    WINDOW = 5 * 60
    df = df[
        (df["time_seconds"] >= df["ATOT_seconds"] - WINDOW) &
        (df["time_seconds"] <= df["ATOT_seconds"] + WINDOW)
    ].copy()

    # Coordenadas umbral pista - ajustar según pista
    if runway == "LEBL-24L":
        RWY_LAT, RWY_LON = 41.2904, 2.0747
    elif runway == "LEBL-06R":
        RWY_LAT, RWY_LON = 41.3018, 2.0784  # ejemplo aproximado de 06R
    else:
        raise ValueError("Pista no soportada")

    first_points = df.groupby("id").first().reset_index()
    first_points["dist_rwy"] = _haversine(first_points["lat"], first_points["lon"], RWY_LAT, RWY_LON)
    ids_ok = set(first_points[first_points["dist_rwy"] <= 2000]["id"])
    df = df[df["id"].isin(ids_ok)].copy().sort_values(["id", "time_seconds"])

    return df


# --- Función que extrae IAS en altitudes dadas ---
def extract_IAS_by_altitude(df_joined: pd.DataFrame, altitudes_ft=[850,1500,3500]) -> pd.DataFrame:
    records = []

    for flight_id, group in df_joined.groupby("id"):
        callsign = group["callsign"].iloc[0]
        SID = group["ProcDesp"].iloc[0] if "ProcDesp" in group.columns else "Unknown"
        airline = group["BP"].iloc[0] if "BP" in group.columns else "Unknown"
        ac_type = group["TipoAeronave"].iloc[0] if "TipoAeronave" in group.columns else "Unknown"
        runway = group["PistaDesp"].iloc[0] if "PistaDesp" in group.columns else "Unknown"
        time_takeoff = group["ATOT"].iloc[0] if "ATOT" in group.columns else "Unknown"
        estela = group["Estela"].iloc[0] if "Estela" in group.columns else "Unknown"

        for alt_ft in altitudes_ft:
            # Encontrar la fila con Hft más cercana a alt_ft
            group["dist_alt"] = abs(group["Hft"] - alt_ft)
            row_closest = group.loc[group["dist_alt"].idxmin()]

            records.append({
                "callsign": callsign,
                "time_despegue": time_takeoff,
                "SID": SID,
                "Estela": estela,
                "Airline": airline,
                "AircraftType": ac_type,
                "Runway": runway,
                f"IAS_{alt_ft}ft": row_closest.get("IAS", np.nan),
                f"IAS_{alt_ft}ft_time": row_closest.get("Time", ""),
                f"IAS_{alt_ft}ft_altitude": row_closest.get("Hft", np.nan)
            })

    return pd.DataFrame(records)


# --- Guardar resultados ---
def save_results_csv(df_results: pd.DataFrame, output_path: str):
    df_results.to_csv(output_path, index=False)

