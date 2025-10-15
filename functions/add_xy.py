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
    lat_col: str = "lat",          # prioriza los nombres reales de tu CSV
    lon_col: str = "lon",
    decimal: Optional[str] = None, # None -> no forzar decimal; usa el del archivo
    sep: str = ",",                # tu CSV muestra coma como separador
) -> pd.DataFrame:
    """
    Calcula (X,Y) estereográficos desde lat/lon y añade ambas columnas al CSV filtrado.
    """
    # Leer sin forzar decimal si viene con punto
    read_kwargs = {"sep": sep}
    if decimal is not None:
        read_kwargs["decimal"] = decimal
    df = pd.read_csv(ruta_csv_filtrado, **read_kwargs)

    # Alias de columnas: prioriza 'lat','lon' según tu CSV, luego variantes
    lat_candidates = [lat_col, "lat", "LAT", "Lat", "Latitude", "Latitud", "WGS84_Lat"]
    lon_candidates = [lon_col, "lon", "LON", "Lon", "Longitude", "Longitud", "WGS84_Lon"]

    lat_name = _pick_existing_column(df, lat_candidates, "latitud")
    lon_name = _pick_existing_column(df, lon_candidates, "longitud")

    lat = pd.to_numeric(df[lat_name], errors="coerce")
    lon = pd.to_numeric(df[lon_name], errors="coerce")

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

    df["X"] = xs
    df["Y"] = ys

    if salida_csv is None:
        ruta = Path(ruta_csv_filtrado)
        salida_csv = ruta.with_name(ruta.stem + "_with_xy.csv")

    df.to_csv(salida_csv, index=False)
    return df
