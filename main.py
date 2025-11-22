# main.py - Programa principal actualizado

# Proyecto 3 - PGTA

from datetime import datetime, timezone
import json
import os
from typing import List
import webbrowser

import pandas as pd

from functions.P3_loader_and_filter import (
    filtrar_asterix_por_callsigns_y_dominios,
    leer_callsigns_validos_p3,
)
from functions.add_xy import add_xy_to_filtered_csv
from functions.check_loa_compilance import check_loa_compliance
from functions.check_wake_turbulence import (
    check_wake_turbulence_violations,
    get_wake_violations_detail,
)
from functions.compute_distance import compute_distance, get_twr_tma_distances
from functions.check_minima import check_minima_violations, get_violations_detail
from functions.compute_radial_bcn import add_radial_from_bcn
from functions.detect_turn_start import detect_turns_all_flights
from functions.load_and_join_radar import join_plan_radar
#from main_turns_pipeline import build_czml_for_flight, write_cesium_html
from  main_turns_pipeline import main_turns_pipeline
from main_IAS import main_IAS


def main():
    print("\n=== INICIO DEL PROCESAMIENTO ===")

    # 1) Leer callsigns válidos desde Excel P3
    print("→ Leyendo callsigns válidos...")
    callsigns_validos = leer_callsigns_validos_p3(
        "Inputs/P3_DEP_LEBL.xlsx",
        hoja="Hoja1",
    )

    # 2) Filtrar CAT048 según callsigns y dominios
    print("→ Filtrando CAT048...")
    rutas_csv: List[str] = ["Inputs/P3_04h_08h.csv"]
    _ = filtrar_asterix_por_callsigns_y_dominios(
        rutas_csv_asterix=rutas_csv,
        callsigns_validos=callsigns_validos,
        salida_csv="Outputs/cat048_filtered_LEBL_DEP.csv",
    )

    # 3) Añadir coordenadas X,Y + distancia a threshold + ATCZone
    print("→ Añadiendo coordenadas y distancia al threshold...")
    _ = add_xy_to_filtered_csv(
        ruta_csv_filtrado="Outputs/cat048_filtered_LEBL_DEP.csv",
        salida_csv="Outputs/cat048_filtered_LEBL_DEP_with_xy.csv",
        lat_col="lat",
        lon_col="lon",
        time_col="Time",
        callsign_col="callsign",
        decimal=None,
        sep=",",
        tower_threshold_nm=0.5,
    )

    # 4) Calcular distancias entre vuelos consecutivos con segregación TWR/TMA
    print("→ Calculando distancias por tick con segregación TWR/TMA...")
    df_xy = pd.read_csv("Outputs/cat048_filtered_LEBL_DEP_with_xy.csv")
    df_all_distances = compute_distance(
        df_xy=df_xy,
        callsign_col="callsign",
        time_col="Time",
        x_col="X",
        y_col="Y",
        lat_col="lat",
        lon_col="lon",
        threshold_twr_nm=0.5,
        only_same_runway=False,
        only_same_sid=False,
    )
    df_all_distances.to_csv("Outputs/distances_all_ticks.csv", index=False)

    # 5) Extraer distancias TWR y TMA por pareja
    print("\n→ Extrayendo distancias TWR y TMA...")
    df_twr_tma = get_twr_tma_distances(df_all_distances)
    df_twr_tma.to_csv("Outputs/distances_twr_tma.csv", index=False)

    # 6) Verificar incumplimientos de separación mínima (3 NM)
    print("\n→ Verificando incumplimientos de separación mínima...")
    df_with_violations, stats = check_minima_violations(
        df_twr_tma=df_twr_tma,
        minima_nm=3.0,
    )
    df_with_violations.to_csv(
        "Outputs/separations_with_violations.csv",
        index=False,
    )

    # 7) Extraer solo incumplimientos para análisis detallado
    df_violations = get_violations_detail(df_with_violations, zone="both")
    df_violations.to_csv("Outputs/violations_only.csv", index=False)

    # 8) Verificar incumplimientos de separación por wake turbulence
    print("\n→ Verificando incumplimientos de wake turbulence...")
    df_with_wake_violations, wake_stats = check_wake_turbulence_violations(
        df_twr_tma=df_twr_tma,
        callsign_col_preceding="callsign_preceding",
        callsign_col_following="callsign_following",
        wake_prec_col="wake_cat_preceding",
        wake_foll_col="wake_cat_following",
    )

    # 10) Mostrar estadísticas de Wake Turbulence (aunque sean 0)
    print("\n=== ESTADÍSTICAS DE WAKE TURBULENCE ===")
    print(f"Total de parejas evaluadas: {wake_stats.get('total_pairs', 0)}")
    print(
        f"Parejas con restricción wake: "
        f"{wake_stats.get('pairs_with_wake_restriction', 0)}"
    )
    print(f"Incumplimientos wake en TWR: {wake_stats.get('wake_violations_twr', 0)}")
    print(f"Incumplimientos wake en TMA: {wake_stats.get('wake_violations_tma', 0)}")
    print(f"Incumplimientos wake en ambos: {wake_stats.get('wake_violations_both', 0)}")
    print(f"Incumplimientos wake (TWR o TMA): {wake_stats.get('wake_violations_any', 0)}")

    df_with_wake_violations.to_csv(
        "Outputs/wake_turbulence_check.csv",
        index=False,
    )

    # 9) Extraer solo incumplimientos de wake turbulence
    df_wake_violations = get_wake_violations_detail(
        df_with_wake_violations,
        zone="both",
    )
    df_wake_violations.to_csv("Outputs/wake_violations_only.csv", index=False)

    # 11) Verificar cumplimiento de LoA
    print("\n→ Verificando cumplimiento de LoA...")
    df_loa = check_loa_compliance(df_twr_tma)
    df_loa.to_csv("Outputs/loa_check_full.csv", index=False)
    df_loa_bad = df_loa[df_loa["loa_ok"] == False].copy()
    df_loa_bad.to_csv("Outputs/loa_violations_only.csv", index=False)

    total_pairs = len(df_loa)
    total_bad = len(df_loa_bad)
    print(f"Parejas evaluadas LoA: {total_pairs}")
    print(f"Incumplimientos LoA: {total_bad}")


    main_turns_pipeline()
    main_IAS()
    print("\n=== PROCESAMIENTO COMPLETADO (SEPARACIONES) ===")
    print("→ Archivos generados en carpeta 'Outputs/'")
if __name__ == "__main__":
    main()
