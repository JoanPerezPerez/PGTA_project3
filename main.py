# main.py - Programa principal actualizado
# Proyecto 3 - PGTA

from typing import List
import pandas as pd
from functions.P3_loader_and_filter import (
    filtrar_asterix_por_callsigns_y_dominios,
    leer_callsigns_validos_p3,
)
from functions.add_xy import add_xy_to_filtered_csv
from functions.compute_distance import compute_distance, get_twr_tma_distances
from functions.check_minima import check_minima_violations, get_violations_detail


def main():
    print("\n=== INICIO DEL PROCESAMIENTO ===")

    # 1) Leer callsigns válidos desde Excel P3
    print("→ Leyendo callsigns válidos...")
    callsigns_validos = leer_callsigns_validos_p3("Inputs/P3_DEP_LEBL.xlsx", hoja="Hoja1")

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
        minima_nm=3.0
    )
    df_with_violations.to_csv("Outputs/separations_with_violations.csv", index=False)

    # 7) Extraer solo incumplimientos para análisis detallado
    df_violations = get_violations_detail(df_with_violations, zone='both')
    df_violations.to_csv("Outputs/violations_only.csv", index=False)

    print("\n=== PROCESAMIENTO COMPLETADO ===")
    print(f"→ Archivos generados en carpeta 'Outputs/'")


if __name__ == "__main__":
    main()
