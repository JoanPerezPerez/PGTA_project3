"""
main.py - Programa principal
Proyecto 3 - PGTA
"""

import pandas as pd
import os
import sys
from typing import List
from models.DataItems import DataItem
from functions.data_loader import parse_csv_to_dataitem_list, filter_data_items
from functions.calculate_separations_between_consecutive_departures import calculate_separations_between_consecutive_departures
import constants


def main():
    """Función principal del programa."""
    
    print("\n" + "="*80)
    print("PROYECTO 3 - ANÁLISIS DE SEPARACIONES RADAR EN DESPEGUES LEBL")
    print("="*80 + "\n")
    
    # 1. Cargar datos radar
    csv_file = os.path.join("Inputs", "P3_04h_08h.csv")
    
    if not os.path.exists(csv_file):
        print(f"❌ ERROR: No se encontró {csv_file}")
        print(f"   Verifica que existe la carpeta 'Inputs' con el archivo CSV")
        sys.exit(1)
    
    data_items = parse_csv_to_dataitem_list(csv_file)
    
    if len(data_items) == 0:
        print("\n❌ ERROR CRÍTICO: No se cargaron datos radar")
        print("   Verifica que la columna 'TI' contiene callsigns válidos")
        sys.exit(1)
    
    # 2. Aplicar filtros
    filtered_data = filter_data_items(data_items)
    
    if len(filtered_data) == 0:
        print("\n⚠️  ADVERTENCIA: Todos los datos filtrados")
        print("   Revisa los criterios de filtrado")
        sys.exit(1)
    
    # 3. Cargar planes de vuelo
    fp_file = os.path.join("Inputs", "P3_DEP_LEBL.xlsx")
    
    if not os.path.exists(fp_file):
        print(f"\n❌ ERROR: No se encontró {fp_file}")
        sys.exit(1)
    
    print(f"\nCargando planes de vuelo...")
    flight_plans = pd.read_excel(fp_file, sheet_name='Hoja1')
    print(f"✓ Cargados {len(flight_plans)} planes de vuelo")
    
    # 4. Calcular separaciones
    results_24l = calculate_separations_between_consecutive_departures(
        filtered_data, flight_plans, '24L'
    )
    
    results_06r = calculate_separations_between_consecutive_departures(
        filtered_data, flight_plans, '06R'
    )
    
    # 5. Combinar y guardar
    all_results = pd.concat([results_24l, results_06r], ignore_index=True)
    
    output_file = "separations_results.csv"
    all_results.to_csv(output_file, index=False, sep=';', encoding='utf-8')
    print(f"\n✓ Resultados → {output_file}")
    
    # 6. Estadísticas
    print("\n" + "="*80)
    print("ESTADÍSTICAS")
    print("="*80)
    
    if len(all_results) > 0:
        total = len(all_results)
        inc_radar_twr = all_results['Inc_Radar_TWR'].sum()
        inc_radar_tma = all_results['Inc_Radar_TMA'].sum()
        
        wake_twr = all_results[all_results['Inc_Wake_TWR'] != 'NA']
        wake_tma = all_results[all_results['Inc_Wake_TMA'] != 'NA']
        
        inc_wake_twr = wake_twr['Inc_Wake_TWR'].sum() if len(wake_twr) > 0 else 0
        inc_wake_tma = wake_tma['Inc_Wake_TMA'].sum() if len(wake_tma) > 0 else 0
        
        print(f"\nTotal parejas: {total}")
        print(f"\nTWR (mínima {constants.MINIMA_RADAR_TWR_NM} NM):")
        print(f"  - Inc. radar: {inc_radar_twr} ({inc_radar_twr/total*100:.1f}%)")
        print(f"  - Inc. estela: {inc_wake_twr}")
        print(f"\nTMA (mínima {constants.MINIMA_RADAR_TMA_NM} NM):")
        print(f"  - Inc. radar: {inc_radar_tma} ({inc_radar_tma/total*100:.1f}%)")
        print(f"  - Inc. estela: {inc_wake_tma}")
        
        # Por pista
        for rwy in ['24L', '06R']:
            rwy_data = all_results[all_results['Runway'] == rwy]
            if len(rwy_data) > 0:
                print(f"\nPista {rwy}: {len(rwy_data)} parejas")
    else:
        print("\n⚠️  No se analizaron parejas")
    
    print("\n" + "="*80)
    print("COMPLETADO")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

