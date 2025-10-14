"""
table_loader.py
Funciones para cargar tablas de clasificación y análisis
Proyecto 3 - PGTA
"""

import pandas as pd
from typing import Dict, List
from models.AircraftClassification import AircraftClassification
from models.SameSIDPairs import SameSIDPair


def load_aircraft_classification(filepath: str = 'Inputs/Tabla_Clasificacion_aeronaves.xlsx') -> Dict[str, AircraftClassification]:
    """
    Carga la tabla de clasificación de aeronaves.
    
    Args:
        filepath: Ruta al archivo Excel de clasificación
        
    Returns:
        Diccionario {tipo_oaci: AircraftClassification}
    """
    print(f"\n{'='*80}")
    print(f"CARGANDO CLASIFICACIÓN DE AERONAVES")
    print('='*80)
    
    try:
        df = pd.read_excel(filepath)
        print(f"✓ Archivo cargado: {filepath}")
        print(f"✓ Registros encontrados: {len(df)}")
        
        # Mostrar columnas disponibles
        print(f"✓ Columnas: {list(df.columns)}")
        
        # Crear diccionario de clasificaciones
        classifications = {}
        
        for _, row in df.iterrows():
            # Adaptar según las columnas reales del Excel
            oaci_type = str(row.get('TipoOACI', row.get('Tipo OACI', row.get('OACI', '')))).strip().upper()
            wake_cat = str(row.get('Estela', row.get('Wake', row.get('Categoría', '')))).strip().upper()
            
            if oaci_type and wake_cat:
                classifications[oaci_type] = AircraftClassification(
                    oaci_type=oaci_type,
                    wake_category=wake_cat,
                    engine_type=str(row.get('Motor', '')).strip() if 'Motor' in row else None,
                    mtow_kg=float(row.get('MTOW_kg', 0)) if 'MTOW_kg' in row else None,
                    manufacturer=str(row.get('Fabricante', '')).strip() if 'Fabricante' in row else None,
                    model=str(row.get('Modelo', '')).strip() if 'Modelo' in row else None
                )
        
        print(f"✓ Clasificaciones cargadas: {len(classifications)} tipos de aeronave")
        print('='*80)
        
        return classifications
        
    except Exception as e:
        print(f"❌ ERROR cargando clasificación de aeronaves: {str(e)}")
        print('='*80)
        return {}


def load_same_sid_pairs(filepath_24L: str = 'Inputs/Tabla_misma_SID_24L.xlsx',
                       filepath_06R: str = 'Inputs/Tabla_misma_SID_06R.xlsx') -> Dict[str, List[SameSIDPair]]:
    """
    Carga las tablas de parejas con misma SID para ambas pistas.
    
    Args:
        filepath_24L: Ruta al archivo Excel de RWY 24L
        filepath_06R: Ruta al archivo Excel de RWY 06R
        
    Returns:
        Diccionario {'24L': [SameSIDPair, ...], '06R': [SameSIDPair, ...]}
    """
    print(f"\n{'='*80}")
    print(f"CARGANDO TABLAS DE MISMA SID")
    print('='*80)
    
    same_sid_data = {}
    
    for runway, filepath in [('24L', filepath_24L), ('06R', filepath_06R)]:
        try:
            df = pd.read_excel(filepath)
            print(f"\n✓ RWY {runway}: {filepath}")
            print(f"  - Registros: {len(df)}")
            print(f"  - Columnas: {list(df.columns)}")
            
            pairs = []
            for _, row in df.iterrows():
                # Adaptar según las columnas reales
                prec = str(row.get('Precedente', row.get('Callsign_Preceding', ''))).strip()
                foll = str(row.get('Siguiente', row.get('Callsign_Following', ''))).strip()
                sid_prec = str(row.get('SID_Prec', row.get('SID_Preceding', ''))).strip()
                sid_foll = str(row.get('SID_Foll', row.get('SID_Following', ''))).strip()
                
                if prec and foll:
                    pair = SameSIDPair(
                        runway=runway,
                        callsign_preceding=prec,
                        callsign_following=foll,
                        sid_preceding=sid_prec,
                        sid_following=sid_foll
                    )
                    pairs.append(pair)
            
            same_sid_data[runway] = pairs
            same_sid_count = sum(1 for p in pairs if p.same_sid)
            print(f"  - Parejas con misma SID: {same_sid_count}/{len(pairs)}")
            
        except Exception as e:
            print(f"❌ ERROR cargando RWY {runway}: {str(e)}")
            same_sid_data[runway] = []
    
    print('='*80)
    return same_sid_data


def enrich_results_with_classification(
    results_df: pd.DataFrame,
    classifications: Dict[str, AircraftClassification]
) -> pd.DataFrame:
    """
    Enriquece el DataFrame de resultados con información de clasificación.
    
    Args:
        results_df: DataFrame con resultados de separaciones
        classifications: Diccionario de clasificaciones por tipo OACI
        
    Returns:
        DataFrame enriquecido con columnas adicionales
    """
    print(f"\n{'='*80}")
    print(f"ENRIQUECIENDO RESULTADOS CON CLASIFICACIÓN")
    print('='*80)
    
    df = results_df.copy()
    
    # Función auxiliar para obtener clasificación
    def get_classification_info(aircraft_type, field):
        if pd.isna(aircraft_type) or aircraft_type == 'UNKNOWN':
            return None
        ac_type = str(aircraft_type).strip().upper()
        if ac_type in classifications:
            return getattr(classifications[ac_type], field, None)
        return None
    
    # Añadir información del precedente
    df['Wake_Preceding_Verified'] = df['Aircraft_Type_Preceding'].apply(
        lambda x: get_classification_info(x, 'wake_category')
    )
    df['Engine_Preceding'] = df['Aircraft_Type_Preceding'].apply(
        lambda x: get_classification_info(x, 'engine_type')
    )
    
    # Añadir información del siguiente
    df['Wake_Following_Verified'] = df['Aircraft_Type_Following'].apply(
        lambda x: get_classification_info(x, 'wake_category')
    )
    df['Engine_Following'] = df['Aircraft_Type_Following'].apply(
        lambda x: get_classification_info(x, 'engine_type')
    )
    
    verified_count = df['Wake_Preceding_Verified'].notna().sum()
    print(f"✓ Parejas con clasificación verificada: {verified_count}/{len(df)}")
    print('='*80)
    
    return df


def mark_same_sid_pairs(
    results_df: pd.DataFrame,
    same_sid_pairs: List[SameSIDPair]
) -> pd.DataFrame:
    """
    Marca en el DataFrame qué parejas tienen la misma SID.
    
    Args:
        results_df: DataFrame con resultados de separaciones
        same_sid_pairs: Lista de parejas con misma SID
        
    Returns:
        DataFrame con columna 'Same_SID' añadida
    """
    df = results_df.copy()
    df['Same_SID'] = False
    
    # Crear diccionario de parejas con misma SID para búsqueda rápida
    same_sid_dict = {
        (p.callsign_preceding, p.callsign_following): p.same_sid 
        for p in same_sid_pairs
    }
    
    # Marcar parejas con misma SID
    for idx, row in df.iterrows():
        key = (row['Callsign_Preceding'], row['Callsign_Following'])
        if key in same_sid_dict:
            df.at[idx, 'Same_SID'] = same_sid_dict[key]
    
    same_sid_count = df['Same_SID'].sum()
    print(f"  ✓ Parejas con misma SID: {same_sid_count}/{len(df)}")
    
    return df
