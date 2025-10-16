import pandas as pd
from typing import Dict, Tuple, Optional
import constants

def _default_loa_matrix() -> Dict[Tuple[str, str, str], float]:
    """
    Matriz de ejemplo para LoA en TWR.
    Clave: (wake_pre, wake_fol, same_sid_flag) -> separación NM
    Ajusta según tu LoA real del PowerPoint.
    """
    # same_sid_flag: "SAME" o "DIFF" // tocará hacer cambios en la base i pillarlo de la tabla que corresponda
    base = {
        ("SUPER","HEAVY","SAME"): 3.0,
        ("SUPER","HEAVY","DIFF"): 3.0,
        ("HEAVY","HEAVY","SAME"): 3.0,
        ("HEAVY","HEAVY","DIFF"): 3.0,
        ("HEAVY","MEDIUM","SAME"): 3.0,
        ("HEAVY","MEDIUM","DIFF"): 3.0,
        ("MEDIUM","MEDIUM","SAME"): 3.0,
        ("MEDIUM","MEDIUM","DIFF"): 3.0,
        ("MEDIUM","LIGHT","SAME"): 3.0,
        ("MEDIUM","LIGHT","DIFF"): 3.0,
        ("LIGHT","LIGHT","SAME"): 3.0,
        ("LIGHT","LIGHT","DIFF"): 3.0,
    }
    return base

def _normalize_cat(x: Optional[str]) -> Optional[str]:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return str(x).strip().upper()

def _same_sid_flag(sid_pre: Optional[str], sid_fol: Optional[str]) -> str:
    if sid_pre and sid_fol and str(sid_pre).strip().upper() == str(sid_fol).strip().upper():
        return "SAME"
    return "DIFF"

def check_loa_compliance(
    df_in: pd.DataFrame,
    zone_col: str = "ATCZone",
    distance_col: str = "distance_nm",
    wake_pre_col: str = "Wake_Pre",
    wake_fol_col: str = "Wake_Fol",
    sid_pre_col: str = "SID_Preceding",
    sid_fol_col: str = "SID_Following",
    out_required_col: str = "loa_required_nm",
    out_breach_col: str = "loa_is_below",
    out_margin_col: str = "loa_margin_nm",
) -> pd.DataFrame:
    """
    Calcula incumplimiento por LoA SOLO en TWR:
      - Se requiere que el DataFrame traiga Wake_Pre/Wake_Fol (o columnas a mapear previamente)
        y opcionalmente SID_Preceding/SID_Following para distinguir SAME/DIFF SID.
      - Usa constants.LOA_MATRIX si existe; si no, aplica un fallback.
    """
    if zone_col not in df_in.columns:
        raise KeyError(f"Falta columna de zona ATC: {zone_col}")
    if distance_col not in df_in.columns:
        raise KeyError(f"Falta columna de distancia: {distance_col}")

    loa_matrix: Dict[Tuple[str,str,str], float] = getattr(constants, "LOA_MATRIX", None)
    if not isinstance(loa_matrix, dict):
        loa_matrix = _default_loa_matrix()

    df = df_in.copy()

    # Filtrar TWR
    df_twr = df[df[zone_col] == "TWR"].copy()

    # Normalizar categorías y SAME/DIFF SID
    df_twr["Wake_Pre_N"] = df_twr[wake_pre_col].map(_normalize_cat) if wake_pre_col in df_twr.columns else None
    df_twr["Wake_Fol_N"] = df_twr[wake_fol_col].map(_normalize_cat) if wake_fol_col in df_twr.columns else None
    if sid_pre_col in df_twr.columns and sid_fol_col in df_twr.columns:
        df_twr["SID_Flag"] = [
            _same_sid_flag(sp, sf) for sp, sf in zip(df_twr[sid_pre_col], df_twr[sid_fol_col])
        ]
    else:
        df_twr["SID_Flag"] = "DIFF"

    def _req(row) -> float:
        pre = row["Wake_Pre_N"]
        fol = row["Wake_Fol_N"]
        sflag = row["SID_Flag"]
        if pre is None or fol is None:
            return float("nan")
        return loa_matrix.get((pre, fol, sflag), float("nan"))

    df_twr[out_required_col] = df_twr.apply(_req, axis=1)
    vals = pd.to_numeric(df_twr[distance_col], errors="coerce")
    reqs = pd.to_numeric(df_twr[out_required_col], errors="coerce")
    df_twr[out_breach_col] = vals < reqs
    df_twr[out_margin_col] = vals - reqs

    # Mezclar resultados con el DataFrame completo (no TWR quedan NaN en columnas LoA)
    df_out = df.copy()
    for col in [out_required_col, out_breach_col, out_margin_col]:
        df_out[col] = None
    df_out.loc[df_twr.index, out_required_col] = df_twr[out_required_col]
    df_out.loc[df_twr.index, out_breach_col] = df_twr[out_breach_col]
    df_out.loc[df_twr.index, out_margin_col] = df_twr[out_margin_col]

    return df_out
