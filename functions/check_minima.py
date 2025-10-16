import pandas as pd
import constants
from functions.geo_utils import calculate_distance_to_threshold

def _compute_thr_distance_from_latlon(
    df: pd.DataFrame,
    lat_cols=("lat","LAT","Lat","Latitude"),
    lon_cols=("lon","LON","Lon","Longitude")
) -> pd.Series:
    lat_name = next((c for c in lat_cols if c in df.columns), None)
    lon_name = next((c for c in lon_cols if c in df.columns), None)
    if lat_name is None or lon_name is None:
        # No se puede calcular de forma automática
        return pd.Series([float("nan")] * len(df), index=df.index)
    lat_vals = pd.to_numeric(df[lat_name], errors="coerce")
    lon_vals = pd.to_numeric(df[lon_name], errors="coerce")

    def _row(la, lo):
        if pd.isna(la) or pd.isna(lo):
            return float("nan")
        d24 = calculate_distance_to_threshold(la, lo, constants.THR_24L_LAT, constants.THR_24L_LON)
        d06 = calculate_distance_to_threshold(la, lo, constants.THR_06R_LAT, constants.THR_06R_LON)
        return min(d24, d06)

    return pd.Series((_row(la, lo) for la, lo in zip(lat_vals, lon_vals)), index=df.index)

def check_minima(
    distances_df: pd.DataFrame,
    distance_col: str = "distance_nm",
    tick_time_col: str = "tick_time_s",
    pair_keys = ("callsign_preceding", "callsign_following"),
    tower_threshold_nm: float = 0.5,
) -> pd.DataFrame:
    """
    Paso h) - Verifica incumplimientos con una única mínima (constants.MINIMA).
    Usa thr_distance_nm y/o ATCZone si existen (calculados en add_xy). Si no, intenta
    derivar thr_distance_nm desde lat/lon y clasifica ATCZone con umbral 0.5 NM.
    Consolida TMA conservando solo la primera infracción por par.
    """
    if distance_col not in distances_df.columns:
        raise KeyError(f"Falta columna de distancia: {distance_col}")
    if tick_time_col not in distances_df.columns:
        raise KeyError(f"Falta columna de tiempo de tick: {tick_time_col}")

    df = distances_df.copy()

    # Garantizar thr_distance_nm si no vino desde add_xy
    if "thr_distance_nm" not in df.columns:
        df["thr_distance_nm"] = _compute_thr_distance_from_latlon(df)

    # Garantizar ATCZone si no vino desde add_xy
    if "ATCZone" not in df.columns:
        df["ATCZone"] = "TMA"
        df.loc[pd.to_numeric(df["thr_distance_nm"], errors="coerce") < tower_threshold_nm, "ATCZone"] = "TWR"

    # Mínima única
    min_required = float(constants.MINIMA)
    vals = pd.to_numeric(df[distance_col], errors="coerce")
    df["min_required_nm"] = min_required
    df["is_below_minima"] = vals < min_required
    df["margin_nm"] = vals - min_required

    # Consolidación TMA: solo la primera infracción por par
    if pair_keys and all(k in df.columns for k in pair_keys):
        tma_mask = (df["ATCZone"] == "TMA") & (df["is_below_minima"])
        tma_viol = df.loc[tma_mask].copy().sort_values(by=[*pair_keys, tick_time_col], kind="mergesort")
        first_mask = ~tma_viol.duplicated(subset=[*pair_keys], keep="first")
        keep_ids = set(tma_viol.loc[first_mask].index)
        drop_ids = set(tma_viol.index) - keep_ids
        if drop_ids:
            df.loc[list(drop_ids), "is_below_minima"] = False

    return df
