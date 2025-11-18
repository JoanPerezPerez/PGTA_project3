import pandas as pd

from pathlib import Path
from typing import Iterable, Set, Optional, Union


def _pick_existing_column(df: pd.DataFrame, candidates, logical_name: str) -> str:
    """
    Devuelve la primera columna existente dentro de 'candidates' o lanza un error
    explicando qué nombre lógico se esperaba.
    """
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(
        f"No se encontró ninguna columna para '{logical_name}'. "
        f"Probadas: {candidates}. Columnas disponibles: {list(df.columns)}"
    )


def leer_callsigns_validos_p3(
    ruta_excel: Union[str, Path],
    hoja: str = "Hoja1",
    pistas_validas: Optional[Iterable[str]] = None,
) -> Set[str]:
    """
    Lee P3_DEP_LEBL.xlsx y devuelve el conjunto de callsigns (Indicativo)
    cuyo Origen=LEBL y PistaDesp en {LEBL-24L, LEBL-06R} por defecto.
    Se admite flexibilidad en los nombres reales de columnas del Excel.
    """
    if pistas_validas is None:
        pistas_validas = ["LEBL-24L", "LEBL-06R"]

    df = pd.read_excel(ruta_excel, sheet_name=hoja)

    col_origen = _pick_existing_column(
        df,
        ["Origen", "ORIGEN", "AirportOrig", "AeropuertoOrigen"],
        "Origen",
    )
    col_runway = _pick_existing_column(
        df,
        ["PistaDesp", "Pista_Desp", "RWY", "Runway"],
        "PistaDesp",
    )
    col_callsign = _pick_existing_column(
        df,
        ["Indicativo", "CALLSIGN", "Callsign"],
        "Indicativo",
    )

    # Filtro por aeropuerto de origen y pista
    origen_norm = df[col_origen].astype(str).str.strip().str.upper()
    pista_norm = df[col_runway].astype(str).str.strip().str.upper()

    df = df[origen_norm == "LEBL"]
    df = df[pista_norm.isin([p.upper() for p in pistas_validas])]

    calls = (
        df[col_callsign]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return set(calls)


def filtrar_asterix_por_callsigns_y_dominios(
    rutas_csv_asterix: Iterable[Union[str, Path]],
    callsigns_validos: Set[str],
    salida_csv: Union[str, Path] = "cat048_filtered_LEBL_DEP.csv",
    decimal: str = ",",
    sep: str = ";",
    lat_min: float = 40.9,
    lat_max: float = 41.7,
    lon_min: float = 1.5,
    lon_max: float = 2.6,
    alt_max_ft: float = 6000.0,
) -> pd.DataFrame:
    """
    Aplica:
    - cruce por callsign con el conjunto válido,
    - filtro geográfico (lat/lon),
    - filtro vertical ALT_CORR <= 6000 ft,
    - filtro de presencia de FL.

    Acepta múltiples CSV y concatena el resultado.
    """
    frames = []

    for ruta in rutas_csv_asterix:
        df = pd.read_csv(ruta, sep=sep, decimal=decimal)

        # Normalizaciones/renombres seguros
        # Mapea columnas del ejemplo a nombres de trabajo
        col_map = {
            "TI": "callsign",
            "LAT": "lat",
            "LON": "lon",
            "FL": "FL",
            "BAR": "ALT_CORR",  # asumimos BAR es altitud corregida en ft
        }

        for src, dst in col_map.items():
            if src in df.columns:
                df[dst] = df[src]
            elif dst not in df.columns:
                df[dst] = pd.NA

        # Tipificar numéricos y limpiar callsign
        df["callsign"] = (
            df["callsign"].fillna("").astype(str).str.strip().str.upper()
        )
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        df["FL"] = pd.to_numeric(df["FL"], errors="coerce")
        df["ALT_CORR"] = pd.to_numeric(df["ALT_CORR"], errors="coerce")

        # Máscara por llamadas válidas
        mask_calls = df["callsign"].isin(callsigns_validos)

        # Filtros PDF
        mask_geo = df["lat"].between(lat_min, lat_max) & df["lon"].between(
            lon_min, lon_max
        )
        mask_alt = df["ALT_CORR"].le(alt_max_ft)
        mask_fl = df["FL"].notna()

        filtered = df[mask_calls & mask_geo & mask_alt & mask_fl].copy()
        frames.append(filtered)

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = pd.DataFrame()

    # Guardar resultado combinado
    Path(salida_csv).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(salida_csv, index=False)

    return result
