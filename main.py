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
    
    # 6. Estadísticas detalladas
    print("\n" + "="*80)
    print("ESTADÍSTICAS DE SEPARACIONES")
    print("="*80)
    
    if len(all_results) > 0:
        total = len(all_results)
        
        # Contar incumplimientos radar (son booleanos)
        inc_radar_twr = int(all_results['Inc_Radar_TWR'].sum())
        inc_radar_tma = int(all_results['Inc_Radar_TMA'].sum())
        
        # Contar incumplimientos estela (filtrar 'NA' y contar True)
        # Inc_Wake_TWR y Inc_Wake_TMA son True/False/'NA'
        wake_twr_applicable = all_results[all_results['Inc_Wake_TWR'] != 'NA']
        wake_tma_applicable = all_results[all_results['Inc_Wake_TMA'] != 'NA']
        
        # Contar cuántas parejas tienen separación por estela aplicable
        wake_twr_cases = len(wake_twr_applicable)
        wake_tma_cases = len(wake_tma_applicable)
        
        # Contar incumplimientos (True = incumplimiento)
        inc_wake_twr = int(wake_twr_applicable['Inc_Wake_TWR'].sum()) if wake_twr_cases > 0 else 0
        inc_wake_tma = int(wake_tma_applicable['Inc_Wake_TMA'].sum()) if wake_tma_cases > 0 else 0
        
        # Resumen general
        print(f"\n📊 RESUMEN GENERAL:")
        print(f"   Total parejas analizadas: {total}")
        
        # Estadísticas TWR
        print(f"\n🛫 ZONA TWR (primera detección ≥ 0.5 NM):")
        print(f"   Mínima radar: {constants.MINIMA_RADAR_TWR_NM} NM")
        print(f"   • Incumplimientos radar: {inc_radar_twr}/{total} ({inc_radar_twr/total*100:.1f}%)")
        
        if wake_twr_cases > 0:
            print(f"   • Parejas con separación estela aplicable: {wake_twr_cases}/{total} ({wake_twr_cases/total*100:.1f}%)")
            print(f"   • Incumplimientos estela: {inc_wake_twr}/{wake_twr_cases} ({inc_wake_twr/wake_twr_cases*100:.1f}%)")
        else:
            print(f"   • Incumplimientos estela: N/A (no aplica a ninguna pareja)")
        
        # Estadísticas TMA
        print(f"\n✈️  ZONA TMA (resto de detecciones):")
        print(f"   Mínima radar: {constants.MINIMA_RADAR_TMA_NM} NM")
        print(f"   • Incumplimientos radar: {inc_radar_tma}/{total} ({inc_radar_tma/total*100:.1f}%)")
        
        if wake_tma_cases > 0:
            print(f"   • Parejas con separación estela aplicable: {wake_tma_cases}/{total} ({wake_tma_cases/total*100:.1f}%)")
            print(f"   • Incumplimientos estela: {inc_wake_tma}/{wake_tma_cases} ({inc_wake_tma/wake_tma_cases*100:.1f}%)")
        else:
            print(f"   • Incumplimientos estela: N/A (no aplica a ninguna pareja)")
        
        # Estadísticas por pista
        print(f"\n🛬 ESTADÍSTICAS POR PISTA:")
        for rwy in ['24L', '06R']:
            rwy_data = all_results[all_results['Runway'] == rwy]
            if len(rwy_data) > 0:
                rwy_total = len(rwy_data)
                rwy_inc_radar_twr = int(rwy_data['Inc_Radar_TWR'].sum())
                rwy_inc_radar_tma = int(rwy_data['Inc_Radar_TMA'].sum())
                
                print(f"\n   Pista {rwy}: {rwy_total} parejas")
                print(f"   • Inc. radar TWR: {rwy_inc_radar_twr} ({rwy_inc_radar_twr/rwy_total*100:.1f}%)")
                print(f"   • Inc. radar TMA: {rwy_inc_radar_tma} ({rwy_inc_radar_tma/rwy_total*100:.1f}%)")
        
        # Distribución de categorías de estela
        print(f"\n📋 DISTRIBUCIÓN DE CATEGORÍAS DE ESTELA:")
        wake_combinations = all_results.groupby(['Wake_Preceding', 'Wake_Following']).size().sort_values(ascending=False)
        
        print(f"   Top 5 combinaciones:")
        for idx, (combo, count) in enumerate(wake_combinations.head(5).items(), 1):
            prec, foll = combo
            print(f"   {idx}. {prec} → {foll}: {count} parejas ({count/total*100:.1f}%)")
        
        # Detalle de incumplimientos si los hay
        total_inc = inc_radar_twr + inc_radar_tma + inc_wake_twr + inc_wake_tma
        
        if total_inc > 0:
            print(f"\n⚠️  TOTAL INCUMPLIMIENTOS DETECTADOS: {total_inc}")
            
            # Guardar solo incumplimientos
            incumplimientos = all_results[
                (all_results['Inc_Radar_TWR'] == True) | 
                (all_results['Inc_Radar_TMA'] == True) |
                (all_results['Inc_Wake_TWR'] == True) |
                (all_results['Inc_Wake_TMA'] == True)
            ]
            
            if len(incumplimientos) > 0:
                inc_file = "incumplimientos_separaciones.csv"
                incumplimientos.to_csv(inc_file, index=False, sep=';', encoding='utf-8')
                print(f"   → Detalles guardados en: {inc_file}")
        else:
            print(f"\n✅ NO SE DETECTARON INCUMPLIMIENTOS")
            print(f"   • Todas las separaciones cumplen con las mínimas requeridas")
            print(f"   • Nota: La mayoría de parejas son MEDIUM→MEDIUM (no aplica estela)")
        
    else:
        print("\n⚠️  No se analizaron parejas")
        print("   Verifica que los callsigns del radar coinciden con los planes de vuelo")
    
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

