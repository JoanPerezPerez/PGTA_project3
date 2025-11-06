import pandas as pd
from typing import Tuple

# Tabla de separaciones mínimas por wake turbulence (en NM)
WAKE_TURBULENCE_SEPARATIONS = {
    ('Super Pesada', 'Pesada'): 6,
    ('Super Pesada', 'Media'): 7,
    ('Super Pesada', 'Ligera'): 8,
    ('Pesada', 'Pesada'): 4,
    ('Pesada', 'Media'): 5,
    ('Pesada', 'Ligera'): 6,
    ('Media', 'Ligera'): 5,
}

# Normalizador de etiquetas (por si llegan como 'super heavy', 'Medium', etc.)
LABEL_MAP = {
    'SUPER PESADA': 'Super Pesada', 'SUPER HEAVY': 'Super Pesada', 'JUMBO': 'Super Pesada',
    'PESADA': 'Pesada', 'HEAVY': 'Pesada',
    'MEDIA': 'Media', 'MEDIUM': 'Media',
    'LIGERA': 'Ligera', 'LIGHT': 'Ligera'
}

def _norm_cat(value: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'Desconocida'
    key = str(value).strip().upper()
    return LABEL_MAP.get(key, value if isinstance(value, str) else str(value))

def get_wake_separation_minima(cat_preceding: str, cat_following: str) -> float:
    """Devuelve la separación mínima NM; 0.0 si no aplica (incluye 'Desconocida')."""
    cp = _norm_cat(cat_preceding)
    cf = _norm_cat(cat_following)
    return WAKE_TURBULENCE_SEPARATIONS.get((cp, cf), 0.0)

def check_wake_turbulence_violations(
    df_twr_tma: pd.DataFrame,
    callsign_col_preceding: str = 'callsign_preceding',
    callsign_col_following: str = 'callsign_following',
    wake_prec_col: str = 'wake_cat_preceding',
    wake_foll_col: str = 'wake_cat_following'
) -> Tuple[pd.DataFrame, dict]:
    """
    Verifica violaciones de wake turbulence usando las categorías ya presentes
    en df_twr_tma (no requiere volver a unir con el Excel).
    """
    df = df_twr_tma.copy()

    # Garantizar columnas de categoría; si faltan, crearlas como 'Desconocida'
    if wake_prec_col not in df.columns:
        df[wake_prec_col] = 'Desconocida'
    if wake_foll_col not in df.columns:
        df[wake_foll_col] = 'Desconocida'

    # Normalizar etiquetas
    df[wake_prec_col] = df[wake_prec_col].apply(_norm_cat)
    df[wake_foll_col] = df[wake_foll_col].apply(_norm_cat)

    # Separación mínima requerida por pareja
    df['wake_minima_nm'] = df.apply(
        lambda r: get_wake_separation_minima(r[wake_prec_col], r[wake_foll_col]), axis=1
    )

    # Flags de violación
    df['wake_violation_twr'] = (
        (df['wake_minima_nm'] > 0) &
        df['distance_twr_nm'].notna() &
        (df['distance_twr_nm'] < df['wake_minima_nm'])
    )
    df['wake_violation_tma'] = (
        (df['wake_minima_nm'] > 0) &
        df['distance_tma_nm'].notna() &
        (df['distance_tma_nm'] < df['wake_minima_nm'])
    )

    # Márgenes de violación
    df['wake_violation_margin_twr'] = (df['wake_minima_nm'] - df['distance_twr_nm']).where(df['wake_violation_twr'], 0.0)
    df['wake_violation_margin_tma'] = (df['wake_minima_nm'] - df['distance_tma_nm']).where(df['wake_violation_tma'], 0.0)

    # Estadísticas
    stats = {
        'total_pairs': int(len(df)),
        'pairs_with_wake_restriction': int((df['wake_minima_nm'] > 0).sum()),
        'wake_violations_twr': int(df['wake_violation_twr'].sum()),
        'wake_violations_tma': int(df['wake_violation_tma'].sum()),
        'wake_violations_both': int((df['wake_violation_twr'] & df['wake_violation_tma']).sum()),
        'wake_violations_any': int((df['wake_violation_twr'] | df['wake_violation_tma']).sum()),
        'avg_violation_margin_twr': float(df.loc[df['wake_violation_twr'], 'wake_violation_margin_twr'].mean() or 0.0),
        'avg_violation_margin_tma': float(df.loc[df['wake_violation_tma'], 'wake_violation_margin_tma'].mean() or 0.0),
        'max_violation_margin_twr': float(df['wake_violation_margin_twr'].max() if len(df) else 0.0),
        'max_violation_margin_tma': float(df['wake_violation_margin_tma'].max() if len(df) else 0.0),
    }

    return df, stats

def get_wake_violations_detail(df_with_violations: pd.DataFrame, zone: str = 'both') -> pd.DataFrame:
    """
    Devuelve solo las filas con violación de wake turbulence, filtrando por zona.
    """
    if zone == 'twr':
        mask = df_with_violations['wake_violation_twr']
    elif zone == 'tma':
        mask = df_with_violations['wake_violation_tma']
    else:
        mask = df_with_violations['wake_violation_twr'] | df_with_violations['wake_violation_tma']
    return df_with_violations[mask].copy()
