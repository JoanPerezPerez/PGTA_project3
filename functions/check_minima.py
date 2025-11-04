# functions/check_minima.py
"""
Verificación de incumplimientos de separación mínima (3 NM)
Proyecto 3 - PGTA
"""

import pandas as pd
from typing import Tuple


def check_minima_violations(
    df_twr_tma: pd.DataFrame,
    minima_nm: float = 3.0
) -> Tuple[pd.DataFrame, dict]:
    """
    Verifica incumplimientos de separación mínima en TWR y TMA.
    
    Se considera incumplimiento cuando la distancia < 3 NM.
    
    Args:
        df_twr_tma: DataFrame resultado de get_twr_tma_distances()
        minima_nm: Separación mínima requerida en NM (default 3.0)
        
    Returns:
        Tuple con:
        - DataFrame con columnas adicionales de incumplimiento
        - Diccionario con estadísticas de incumplimientos
    """
    
    if len(df_twr_tma) == 0:
        return pd.DataFrame(), {}
    
    df = df_twr_tma.copy()
    
    # Verificar incumplimientos en TWR
    df['violation_twr'] = df['distance_twr_nm'] < minima_nm
    
    # Verificar incumplimientos en TMA (solo si existe dato)
    df['violation_tma'] = df['distance_tma_nm'].notna() & (df['distance_tma_nm'] < minima_nm)
    
    # Calcular estadísticas
    total_pairs = len(df)
    
    # Incumplimientos TWR
    violations_twr = df['violation_twr'].sum()
    violations_twr_pct = (violations_twr / total_pairs * 100) if total_pairs > 0 else 0
    
    # Incumplimientos TMA (solo considerar parejas con dato TMA)
    pairs_with_tma = df['distance_tma_nm'].notna().sum()
    violations_tma = df['violation_tma'].sum()
    violations_tma_pct = (violations_tma / pairs_with_tma * 100) if pairs_with_tma > 0 else 0
    
    # Parejas con incumplimiento en ambas zonas
    violations_both = (df['violation_twr'] & df['violation_tma']).sum()
    
    # CORRECCIÓN: Parejas cumplidoras son las que NO incumplen en NINGUNA zona
    # Es decir, NO incumplen en TWR Y NO incumplen en TMA
    compliant_pairs = len(df[~df['violation_twr'] & ~df['violation_tma']])
    
    # Parejas con al menos un incumplimiento
    any_violation = (df['violation_twr'] | df['violation_tma']).sum()
    
    # Crear diccionario de estadísticas
    stats = {
        'total_pairs': total_pairs,
        'pairs_with_tma_data': int(pairs_with_tma),
        'minima_nm': minima_nm,
        'violations_twr': int(violations_twr),
        'violations_twr_pct': round(violations_twr_pct, 1),
        'violations_tma': int(violations_tma),
        'violations_tma_pct': round(violations_tma_pct, 1),
        'violations_both': int(violations_both),
        'violations_any': int(any_violation),
        'compliant_pairs': int(compliant_pairs)
    }
    
    # Imprimir resumen
    print("\n" + "="*70)
    print("ANÁLISIS DE INCUMPLIMIENTOS DE SEPARACIÓN MÍNIMA")
    print("="*70)
    print(f"Separación mínima requerida: {minima_nm} NM")
    print(f"Total de parejas analizadas: {total_pairs}")
    print(f"\n--- TORRE (TWR) ---")
    print(f"Incumplimientos: {violations_twr} de {total_pairs} ({violations_twr_pct:.1f}%)")
    print(f"\n--- TMA ---")
    print(f"Parejas con datos TMA: {pairs_with_tma}")
    print(f"Incumplimientos: {violations_tma} de {pairs_with_tma} ({violations_tma_pct:.1f}%)")
    print(f"\n--- GLOBAL ---")
    print(f"Parejas cumplidoras (ambas zonas): {compliant_pairs}")
    print(f"Incumplimientos en ambas zonas: {violations_both}")
    print(f"Parejas con al menos un incumplimiento: {any_violation}")
    print("="*70)
    
    return df, stats


def get_violations_detail(
    df_with_violations: pd.DataFrame,
    zone: str = 'both'
) -> pd.DataFrame:
    """
    Extrae el detalle de parejas con incumplimientos.
    
    Args:
        df_with_violations: DataFrame resultado de check_minima_violations()
        zone: 'twr', 'tma', o 'both' para filtrar por zona
        
    Returns:
        DataFrame filtrado con solo las parejas que incumplen
    """
    
    if zone == 'twr':
        violations = df_with_violations[df_with_violations['violation_twr'] == True]
    elif zone == 'tma':
        violations = df_with_violations[df_with_violations['violation_tma'] == True]
    elif zone == 'both':
        violations = df_with_violations[
            (df_with_violations['violation_twr'] == True) |
            (df_with_violations['violation_tma'] == True)
        ]
    else:
        raise ValueError("zone debe ser 'twr', 'tma' o 'both'")
    
    return violations.sort_values('id_preceding').reset_index(drop=True)


def print_violations_summary(df_with_violations: pd.DataFrame):
    """
    Imprime un resumen detallado de los incumplimientos.
    
    Args:
        df_with_violations: DataFrame resultado de check_minima_violations()
    """
    
    print("\n" + "="*70)
    print("DETALLE DE INCUMPLIMIENTOS")
    print("="*70)
    
    # Incumplimientos en TWR
    twr_viols = df_with_violations[df_with_violations['violation_twr']]
    if len(twr_viols) > 0:
        print("\n--- INCUMPLIMIENTOS EN TWR ---")
        for _, row in twr_viols.iterrows():
            print(f"{row['callsign_preceding']} → {row['callsign_following']}: "
                  f"{row['distance_twr_nm']:.2f} NM @ {row['time_twr']}")
    
    # Incumplimientos en TMA
    tma_viols = df_with_violations[df_with_violations['violation_tma']]
    if len(tma_viols) > 0:
        print("\n--- INCUMPLIMIENTOS EN TMA ---")
        for _, row in tma_viols.iterrows():
            print(f"{row['callsign_preceding']} → {row['callsign_following']}: "
                  f"{row['distance_tma_nm']:.2f} NM @ {row['time_tma']}")
    
    # Incumplimientos en ambas zonas
    both_viols = df_with_violations[
        df_with_violations['violation_twr'] & df_with_violations['violation_tma']
    ]
    if len(both_viols) > 0:
        print("\n--- INCUMPLIMIENTOS EN AMBAS ZONAS ---")
        for _, row in both_viols.iterrows():
            print(f"{row['callsign_preceding']} → {row['callsign_following']}: "
                  f"TWR={row['distance_twr_nm']:.2f} NM, TMA={row['distance_tma_nm']:.2f} NM")
    
    print("="*70)
