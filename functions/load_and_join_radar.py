import pandas as pd

from functions.load_dept_24L import load_departures_24L


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


def load_radar(path_csv: str) -> pd.DataFrame:
    """
    Carga radar desde:

    - CSV ASTERIX bruto (P3_04h_08h.csv): separador ';', decimal ',', columnas LAT/LON/H(ft)/TI/Mode3-A/Time.
    - CSV procesado que ya tenga 'time_seconds' y 'callsign'/'callsign_norm'.

    Si el CSV ya tiene 'time_seconds', NO intenta recrearlo desde 'Time'.
    """
    # Intentar formato ASTERIX: ';' + ',' y presencia de LAT/LON
    df = pd.read_csv(path_csv, sep=";", decimal=",")
    cols = set(df.columns)

    # Si no parece ASTERIX (no hay 'LAT' ni 'LON'), leer como CSV normal
    if "LAT" not in cols and "LON" not in cols:
        df = pd.read_csv(path_csv)
        cols = set(df.columns)

    # Renombrar columnas si vienen con nombres ASTERIX
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

    # Algunos CSV procesados ya tienen 'Time'; si viene con otro nombre, ya no lo tocamos aquí
    if "Time" in cols:
        rename_map["Time"] = "Time"

    if rename_map:
        df = df.rename(columns=rename_map)
        cols = set(df.columns)
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"load_radar esperaba un DataFrame, obtuvo {type(df)}")
    # Asegurar numéricos clave si existen
    for col in ["track_true", "track_rate", "ROLL", "Hft", "lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Construir callsign_norm:
    # 1) si existe 'callsign'
    # 2) si existe 'callsign_norm'
    # 3) si existe 'mode3a'
    if "callsign" in cols:
        base = df["callsign"]
    elif "callsign_norm" in cols:
        base = df["callsign_norm"]
    elif "mode3a" in cols:
        base = df["mode3a"]
    else:
        base = pd.Series([""] * len(df))

    df["callsign_norm"] = base.astype(str).str.strip().str.upper()

    # Asegurar time_seconds:
    # - Si ya existe, lo usamos tal cual.
    # - Si no existe, intentamos generarlo desde 'Time'.
    cols = set(df.columns)  # actualizar por si hemos añadido columnas
    if "time_seconds" not in cols:
        if "Time" in cols:
            df["time_seconds"] = df["Time"].apply(time_str_to_seconds)
        else:
            # Para depuración: ver columnas reales y fallar de forma clara
            raise KeyError(
                f"No se encuentra ni 'time_seconds' ni 'Time' en el CSV radar. "
                f"Columnas disponibles: {sorted(df.columns)}"
            )

    return df


def join_plan_radar(path_excel: str, path_csv: str) -> pd.DataFrame:
    """
    Une plan de vuelos (P3_DEP_LEBL.xlsx) con radar usando el indicativo normalizado.

    - Plan: columna 'Indicativo_norm'.
    - Radar: columna 'callsign_norm' (derivada de TI, callsign o mode3a).
    """
    df_plan = load_departures_24L(path_excel)
    df_radar = load_radar(path_csv)

    df = df_radar.merge(
        df_plan,
        left_on="callsign_norm",
        right_on="Indicativo_norm",
        how="inner",
        suffixes=("", "_plan"),
    )

    df = df.sort_values(["id", "time_seconds"]).reset_index(drop=True)
    return df
