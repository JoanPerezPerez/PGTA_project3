import pandas as pd
from typing import Union, List, Optional
from pathlib import Path
from functions.geo_utils import geodetic_to_stereographic, calculate_distance_to_threshold
import constants

def _pick_existing_column(df: pd.DataFrame, candidates: List[str], kind: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"No se encontró columna de {kind}. Probadas: {candidates}")

def _compute_thr_min_nm(lat: float, lon: float) -> float:
    # Distancia mínima al umbral entre 24L y 06R en NM
    d24 = calculate_distance_to_threshold(lat, lon, constants.THR_24L_LAT, constants.THR_24L_LON)
    d06 = calculate_distance_to_threshold(lat, lon, constants.THR_06R_LAT, constants.THR_06R_LON)
    return min(d24, d06)

def _parse_time_to_seconds(t: str) -> Optional[float]:
    if not isinstance(t, str):
        return None
    parts = t.split(":")
    if len(parts) != 4:
        return None
    hh, mm, ss, ms = parts
    try:
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
    except Exception:
        return None

def add_xy_to_filtered_csv(
    ruta_csv_filtrado: Union[str, Path],
    salida_csv: Union[str, Path] = None,
    lat_col: str = "lat",          # nombres reales en tu pipeline
    lon_col: str = "lon",
    time_col: str = "Time",        # hh:mm:ss:ms
    callsign_col: str = "callsign",
    decimal: Optional[str] = None, # None => autodetect
    sep: str = ",",                # separador del CSV de ejemplo
    tower_threshold_nm: float = 0.5,
    drop_latlon: bool = False,
) -> pd.DataFrame:
    """
    Calcula (X,Y) estereográficos y añade:
      - X, Y (NM)
      - thr_distance_nm (mínima a THR 24L/06R)
      - ATCZone con transición persistente: TWR hasta cruzar 0.5 NM; la PRIMERA ≥0.5 sigue TWR
        por tolerancia del radar (4 s), y a partir de la siguiente muestra del mismo callsign: TMA.
    """
    read_kwargs = {"sep": sep}
    if decimal is not None:
        read_kwargs["decimal"] = decimal
    df = pd.read_csv(ruta_csv_filtrado, **read_kwargs)

    # Resolver columnas
    lat_name = _pick_existing_column(df, [lat_col, "lat", "LAT", "Lat", "Latitude"], "latitud")
    lon_name = _pick_existing_column(df, [lon_col, "lon", "LON", "Lon", "Longitude"], "longitud")
    time_name = _pick_existing_column(df, [time_col, "Time", "time"], "tiempo")
    calls_name = _pick_existing_column(df, [callsign_col, "callsign", "TI"], "callsign")

    # Convertir a tipos
    lat = pd.to_numeric(df[lat_name], errors="coerce")
    lon = pd.to_numeric(df[lon_name], errors="coerce")
    tsec = df[time_name].astype(str).map(_parse_time_to_seconds)
    df["_tsec"] = tsec
    df[calls_name] = df[calls_name].astype(str).str.strip().str.upper()

    # Proyección estereográfica y distancia a umbral
    xs, ys, dthr = [], [], []
    for la, lo in zip(lat, lon):
        if pd.notna(la) and pd.notna(lo):
            try:
                x, y = geodetic_to_stereographic(float(la), float(lo))
                dmin = _compute_thr_min_nm(float(la), float(lo))
            except Exception:
                x, y, dmin = float("nan"), float("nan"), float("nan")
        else:
            x, y, dmin = float("nan"), float("nan"), float("nan")
        xs.append(x)
        ys.append(y)
        dthr.append(dmin)

    df["X"] = xs
    df["Y"] = ys
    df["thr_distance_nm"] = dthr

    # Etiquetado persistente TWR -> TMA por callsign con tolerancia de 1 tick
    # Regla:
    #  - Inicialmente TWR.
    #  - Si aparece la PRIMERA muestra con thr >= 0.5 NM para ese callsign:
    #      esa muestra sigue TWR (tolerancia radar),
    #      y la SIGUIENTE muestra de ese callsign pasa a TMA definitivamente.
    df = df.sort_values([calls_name, "_tsec"], kind="mergesort")

    zones = []
    crossed_once = {}   # callsign -> bool (ya consolidado TMA)
    pending_flip = {}   # callsign -> bool (próxima muestra será TMA)

    for cs, thr in zip(df[calls_name], df["thr_distance_nm"]):
        cs_state = crossed_once.get(cs, False)
        cs_pending = pending_flip.get(cs, False)

        if cs_state:
            zones.append("TMA")
            crossed_once[cs] = True
            pending_flip[cs] = False
            continue

        if cs_pending:
            zones.append("TMA")
            crossed_once[cs] = True
            pending_flip[cs] = False
            continue

        # Aún en fase TWR; evaluar cruce
        if pd.notna(thr) and float(thr) >= tower_threshold_nm:
            zones.append("TWR")          # tolerancia: este tick cuenta TWR
            pending_flip[cs] = True      # la próxima será TMA
            crossed_once[cs] = False
        else:
            zones.append("TWR")
            crossed_once[cs] = False
            pending_flip[cs] = False

    df["ATCZone"] = zones

    # (Opcional) recuperar orden original
    df = df.sort_index()

    if drop_latlon:
        df = df.drop(columns=[lat_name, lon_name], errors="ignore")

    if salida_csv is None:
        ruta = Path(ruta_csv_filtrado)
        salida_csv = ruta.with_name(ruta.stem + "_with_xy.csv")

    df.to_csv(salida_csv, index=False)
    return df
