# main.py - Programa principal
# Proyecto 3 - PGTA

from typing import List
import pandas as pd
from functions.P3_loader_and_filter import (
    filtrar_asterix_por_callsigns_y_dominios,
    leer_callsigns_validos_p3,
)
from functions.add_xy import add_xy_to_filtered_csv
from functions.check_loa_compilance import check_loa_compliance
from functions.compute_distance import compute_distance
from functions.check_minima import check_minima
from functions.check_wake import check_wake_compliance
import constants


def main():
    # 1) Callsigns válidos desde P3
    callsigns_validos = leer_callsigns_validos_p3("Inputs/P3_DEP_LEBL.xlsx", hoja="Hoja1")

    # 2) Filtro CAT048
    rutas_csv: List[str] = ["Inputs/P3_04h_08h.csv"]
    _ = filtrar_asterix_por_callsigns_y_dominios(
        rutas_csv_asterix=rutas_csv,
        callsigns_validos=callsigns_validos,
        salida_csv="Outputs/cat048_filtered_LEBL_DEP.csv",
    )

    # 3) X,Y + thr_distance_nm + ATCZone (persistente TWR->TMA)
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

    # 4) Paso g: distancias por tick
    df_xy = pd.read_csv("Outputs/cat048_filtered_LEBL_DEP_with_xy.csv")

    dist_df = compute_distance(
        df_xy=df_xy,
        callsign_col="callsign",
        time_col="Time",
        x_col="X",
        y_col="Y",
        only_same_runway=False,
        only_same_sid=False,
    )

    # Propagar ATCZone y thr_distance_nm desde df_xy a dist_df
    def _parse_time_to_seconds(t: str):
        parts = str(t).split(":")
        if len(parts) != 4:
            return None
        hh, mm, ss, ms = parts
        try:
            return int(hh)*3600 + int(mm)*60 + int(ss) + int(ms)/1000.0
        except Exception:
            return None

    df_xy = df_xy.copy()
    df_xy["_tsec"] = df_xy["Time"].astype(str).map(_parse_time_to_seconds)
    tick = float(constants.RADAR_UPDATE_TIME)
    df_xy["_tick"] = (pd.to_numeric(df_xy["_tsec"], errors="coerce") // tick) * tick

    xy_keys = ["_tick", "callsign", "ATCZone", "thr_distance_nm"]
    xy_present = [c for c in xy_keys if c in df_xy.columns]
    xy_min = df_xy[xy_present].dropna(subset=["_tick"]).copy()

    if "tick_time_s" in dist_df.columns:
        pre_map = xy_min.rename(columns={
            "callsign": "callsign_preceding",
            "ATCZone": "ATCZone_pre",
            "thr_distance_nm": "thr_distance_nm_pre"
        })
        fol_map = xy_min.rename(columns={
            "callsign": "callsign_following",
            "ATCZone": "ATCZone_fol",
            "thr_distance_nm": "thr_distance_nm_fol"
        })

        dist_df = dist_df.merge(
            pre_map[["_tick", "callsign_preceding", "ATCZone_pre", "thr_distance_nm_pre"]],
            left_on=["tick_time_s", "callsign_preceding"],
            right_on=["_tick", "callsign_preceding"],
            how="left"
        )
        dist_df = dist_df.merge(
            fol_map[["_tick", "callsign_following", "ATCZone_fol", "thr_distance_nm_fol"]],
            left_on=["tick_time_s", "callsign_following"],
            right_on=["_tick", "callsign_following"],
            how="left"
        )

        for aux in ["_tick_x", "_tick_y", "_tick"]:
            if aux in dist_df.columns:
                dist_df = dist_df.drop(columns=[aux])

        dist_df["ATCZone"] = dist_df["ATCZone_fol"].combine_first(dist_df["ATCZone_pre"])
        dist_df["thr_distance_nm"] = dist_df["thr_distance_nm_fol"].combine_first(dist_df["thr_distance_nm_pre"])

    dist_df.to_csv("Outputs/distances_per_tick.csv", index=False)

        # 5) Paso h: detección e incumplimiento TWR/TMA
    pair_summary = check_minima(
        distances_df=dist_df,
        distance_col="distance_nm",
        tick_time_col="tick_time_s",
        thr_col="thr_distance_nm",
        pair_keys=("callsign_preceding", "callsign_following"),
        tower_threshold_nm=0.5,
    )

    pair_summary.to_csv("Outputs/distances_minima_checked.csv", index=False)

    # ---- Estadísticas ----
    total_pairs = len(pair_summary)
    detected_twr = pair_summary["detected_TWR"].sum()
    incumple_twr = pair_summary["incumple_TWR"].sum()
    incumple_tma = pair_summary["incumple_TMA"].sum()

    print("\n" + "="*80)
    print("ESTADÍSTICAS DE DETECCIÓN E INCUMPLIMIENTO (TWR/TMA)")
    print("="*80)
    print(f"Total parejas: {total_pairs}")
    print(f"Detección TWR (>0.5 NM): {detected_twr}")
    print(f"Incumplimiento TWR (<3 NM, primera detección): {incumple_twr}")
    print(f"Incumplimiento TMA (<3 NM, resto): {incumple_tma}")
    print(f"% detección TWR: {detected_twr / total_pairs * 100:.2f}%")
    print(f"% incumplimiento TWR: {incumple_twr / total_pairs * 100:.2f}%")
    print(f"% incumplimiento TMA: {incumple_tma / total_pairs * 100:.2f}%")



if __name__ == "__main__":
    main()
