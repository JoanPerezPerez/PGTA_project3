import pandas as pd
from typing import Dict, Tuple, Optional
from functions.table_loader import load_aircraft_classification
import constants

def _build_wake_matrix_from_constants() -> Dict[Tuple[str, str], float]:
    """
    Devuelve una matriz de separación por estela en NM.
    Preferencia:
      1) constants.WAKE_MATRIX, dict con claves ('PRE_CAT','FOL_CAT') -> NM
      2) Fallbacks simples si no existe la matriz (ejemplos).
    """
    if hasattr(constants, "WAKE_MATRIX") and isinstance(constants.WAKE_MATRIX, dict):
        return constants.WAKE_MATRIX
    # Fallback genérico (ajusta a tu normativa o a lo definido en el PowerPoint):
    # Ejemplo (no normativo): claves por categorías 'SUPER','HEAVY','MEDIUM','LIGHT'
    base = {
        ("SUPER", "HEAVY"): 6.0,
        ("SUPER", "MEDIUM"): 7.0,
        ("SUPER", "LIGHT"): 8.0,
        ("HEAVY", "HEAVY"): 4.0,
        ("HEAVY", "MEDIUM"): 5.0,
        ("HEAVY", "LIGHT"): 6.0,
        ("MEDIUM", "LIGHT"): 5.0,
    }
    return base

def _map_type_to_wake(ac_type: Optional[str], classifications: Dict[str, any]) -> Optional[str]:
    if ac_type is None or (isinstance(ac_type, float) and pd.isna(ac_type)):
        return None
    key = str(ac_type).strip().upper()
    if key in classifications and getattr(classifications[key], "wake_category", None):
        return str(classifications[key].wake_category).strip().upper()
    return None

def check_wake_compliance(
    df_distances_checked: pd.DataFrame,
    type_pre_col: str = "Aircraft_Type_Preceding",
    type_fol_col: str = "Aircraft_Type_Following",
    distance_col: str = "distance_nm",
    zone_col: str = "ATCZone",
    out_required_col: str = "wake_required_nm",
    out_breach_col: str = "wake_is_below",
    out_margin_col: str = "wake_margin_nm",
    classification_path: str = "Inputs/Tabla_Clasificacion_aeronaves.xlsx",
) -> pd.DataFrame:
    """
    Calcula incumplimiento por estela:
      - Mapea tipos OACI a categorías de estela usando la tabla de clasificación.
      - Aplica matriz de separación por estela para obtener la mínima requerida (NM).
      - Marca incumplimiento si distance_nm < wake_required_nm.
    Segmenta por zona ATC si 'zone_col' está presente.
    """
    for c in [type_pre_col, type_fol_col, distance_col]:
        if c not in df_distances_checked.columns:
            raise KeyError(f"Falta columna requerida: {c}")

    df = df_distances_checked.copy()
    classifications = load_aircraft_classification(classification_path)
    wake_matrix = _build_wake_matrix_from_constants()

    # Mapear tipos a categorías
    df["Wake_Pre"] = df[type_pre_col].apply(lambda x: _map_type_to_wake(x, classifications))
    df["Wake_Fol"] = df[type_fol_col].apply(lambda x: _map_type_to_wake(x, classifications))

    # Calcular requerida por estela
    def _required_nm(row) -> float:
        pre = row["Wake_Pre"]
        fol = row["Wake_Fol"]
        if pre is None or fol is None:
            return float("nan")
        return wake_matrix.get((pre, fol), float("nan"))

    df[out_required_col] = df.apply(_required_nm, axis=1)

    # Comparar distancias
    vals = pd.to_numeric(df[distance_col], errors="coerce")
    reqs = pd.to_numeric(df[out_required_col], errors="coerce")
    df[out_breach_col] = vals < reqs
    df[out_margin_col] = vals - reqs

    # Si quieres guardar separados por zona:
    if zone_col in df.columns:
        for z, chunk in df.groupby(zone_col, dropna=False):
            safe_zone = "UNK" if pd.isna(z) else str(z)
            chunk.to_csv(f"Outputs/wake_{safe_zone}.csv", index=False)
    else:
        df.to_csv("Outputs/wake_ALL.csv", index=False)

    return df
