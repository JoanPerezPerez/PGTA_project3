# functions/add_xy.py
import pandas as pd
from typing import Union, List, Optional
from pathlib import Path
from functions.geo_utils import geodetic_to_stereographic

def _pick_existing_column(df: pd.DataFrame, candidates: List[str], kind: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"No se encontró columna de {kind}. Probadas: {candidates}")

def add_xy_to_filtered_csv(
    ruta_csv_filtrado: Union[str, Path],
    salida_csv: Union[str, Path] = None,
    lat_col: str = "lat",          # nombre por defecto típico en tu pipeline
    lon_col: str = "lon",
    decimal: Optional[str] = None, # None => no forzar; usa el del archivo (punto por defecto)
    sep: str = ",",                # tu CSV de ejemplo usa coma como separador
    drop_latlon: bool = False,     # opcional: borrar lat/lon tras añadir X,Y
) -> pd.DataFrame:
    """
    Lee el CSV filtrado, calcula (X,Y) estereográficos con geodetic_to_stereographic
    y añade dos columnas nuevas 'X' y 'Y' (en NM). No modifica lat/lon salvo que
    drop_latlon=True.

    Args:
        ruta_csv_filtrado: Ruta del CSV filtrado (entrada).
        salida_csv: Ruta del CSV de salida. Si None, añade sufijo '_with_xy'.
        lat_col, lon_col: Nombres preferidos de columnas de lat/lon si existen.
        decimal: Carácter decimal del archivo. None -> no forzar (punto por defecto).
        sep: Separador de columnas (',' o ';').
        drop_latlon: Si True, elimina columnas de latitud/longitud del resultado.

    Returns:
        DataFrame con columnas X e Y añadidas y guardado en salida_csv.
    """
    # Lectura del CSV con configuración flexible de decimal
    read_kwargs = {"sep": sep}
    if decimal is not None:
        read_kwargs["decimal"] = decimal
    df = pd.read_csv(ruta_csv_filtrado, **read_kwargs)

    # Resolver nombres reales de lat/lon presentes en el CSV
    lat_candidates = [lat_col, "lat", "LAT", "Lat", "Latitude", "Latitud", "WGS84_Lat"]
    lon_candidates = [lon_col, "lon", "LON", "Lon", "Longitude", "Longitud", "WGS84_Lon"]

    lat_name = _pick_existing_column(df, lat_candidates, "latitud")
    lon_name = _pick_existing_column(df, lon_candidates, "longitud")

    # Conversión robusta a numérico
    lat = pd.to_numeric(df[lat_name], errors="coerce")
    lon = pd.to_numeric(df[lon_name], errors="coerce")

    # Proyección estereográfica por fila
    xs, ys = [], []
    for la, lo in zip(lat, lon):
        if pd.notna(la) and pd.notna(lo):
            try:
                x, y = geodetic_to_stereographic(float(la), float(lo))
            except Exception:
                x, y = float("nan"), float("nan")
        else:
            x, y = float("nan"), float("nan")
        xs.append(x)
        ys.append(y)

    # Añadir columnas X, Y (en NM)
    df["X"] = xs
    df["Y"] = ys

    # Opción para eliminar columnas geodésicas originales
    if drop_latlon:
        df = df.drop(columns=[lat_name, lon_name], errors="ignore")

    # Resolver ruta de salida por defecto
    if salida_csv is None:
        ruta = Path(ruta_csv_filtrado)
        salida_csv = ruta.with_name(ruta.stem + "_with_xy.csv")

    # Guardar
    df.to_csv(salida_csv, index=False)
    return df
