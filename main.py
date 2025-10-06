"""
main.py - Programa principal para el análisis de separaciones radar en despegues LEBL
Proyecto 3 - PGTA
"""

import pandas as pd
import os
import math

from typing import List, Dict, Tuple, Optional
from models.DataItems import DataItem
from functions.data_loader import *
from functions.geo_utils import *
from functions.separation_checker import *
from functions.calculate_separations_between_consecutive_departures import *
import constants

def main():
    """
    Función principal del programa.
    """
    print("\n" + "="*80)
    print("PROYECTO 3 - ANÁLISIS DE SEPARACIONES RADAR EN DESPEGUES LEBL")
    print("="*80 + "\n")
    
    # 1. Cargar datos CSV decodificados desde inputs/data.csv
    csv_file = os.path.join("Inputs", "P3_04h_08h.csv")
    
    if not os.path.exists(csv_file):
        print(f"❌ ERROR: No se encontró el archivo {csv_file}")
        print(f"   Asegúrate de que el archivo existe en la carpeta 'inputs'")
        return
    
    data_items = parse_csv_to_dataitem_list(csv_file)
    
    # 2. Aplicar filtros
    filtered_data = filter_data_items(data_items)
    
    # 3. Cargar planes de vuelo desde Excel
    flight_plans_file = os.path.join("Inputs", "P3_DEP_LEBL.xlsx")
    
    if not os.path.exists(flight_plans_file):
        print(f"\n❌ ERROR: No se encontró {flight_plans_file}")
        print("   Asegúrate de que el archivo existe en la carpeta 'inputs'")
        return
    
    print(f"\nCargando planes de vuelo desde {flight_plans_file}...")
    flight_plans = pd.read_excel(flight_plans_file, sheet_name='Hoja1')
    print(f"✓ Cargados {len(flight_plans)} planes de vuelo.")
    print(f"   Columnas: {list(flight_plans.columns)}")
    
    # 4. Calcular separaciones para RWY 24L
    results_24l = calculate_separations_between_consecutive_departures(
        filtered_data, flight_plans, '24L'
    )
    
    # 5. Calcular separaciones para RWY 06R
    results_06r = calculate_separations_between_consecutive_departures(
        filtered_data, flight_plans, '06R'
    )
    
    # 6. Combinar resultados
    all_results = pd.concat([results_24l, results_06r], ignore_index=True)
    
    # 7. Guardar resultados
    output_file = "separations_results.csv"
    all_results.to_csv(output_file, index=False)
    print(f"\n✓ Resultados guardados en {output_file}")
    
    # 8. Estadísticas
    print("\n" + "="*80)
    print("ESTADÍSTICAS DE INCUMPLIMIENTOS")
    print("="*80)
    
    if len(all_results) > 0:
        total_pairs = len(all_results)
        inc_radar_twr = all_results['Inc_Radar_TWR'].sum()
        inc_radar_tma = all_results['Inc_Radar_TMA'].sum()
        inc_wake_twr = all_results[all_results['Inc_Wake_TWR'] != 'NA']['Inc_Wake_TWR'].sum()
        inc_wake_tma = all_results[all_results['Inc_Wake_TMA'] != 'NA']['Inc_Wake_TMA'].sum()
        
        print(f"\nTotal de parejas analizadas: {total_pairs}")
        print(f"\nZONA TWR:")
        print(f"  - Incumplimientos mínima radar (3 NM): {inc_radar_twr} ({inc_radar_twr/total_pairs*100:.2f}%)")
        print(f"  - Incumplimientos estela turbulenta: {inc_wake_twr}")
        print(f"\nZONA TMA:")
        print(f"  - Incumplimientos mínima radar (3 NM): {inc_radar_tma} ({inc_radar_tma/total_pairs*100:.2f}%)")
        print(f"  - Incumplimientos estela turbulenta: {inc_wake_tma}")
    else:
        print("\n⚠️  No se encontraron parejas para analizar.")
    
    print("\n" + "="*80)
    print("PROCESO COMPLETADO")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
