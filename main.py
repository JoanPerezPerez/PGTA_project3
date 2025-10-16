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

def _print_minima_stats(df: pd.DataFrame, zone_col: str = "ATCZone"):
    print("\n" + "="*80)
    print("ESTADÍSTICAS DE INCUMPLIMIENTOS POR MÍNIMA RADAR (3 NM)")
    print("="*80)
    if zone_col not in df.columns:
        total = df["is_below_minima"].sum()
        print(f"Total incumplimientos (sin zona): {total}")
        return
    for zone in ["TWR", "TMA"]:
        chunk = df[df[zone_col] == zone]
        total = len(chunk)
        breaches = chunk["is_below_minima"].sum() if "is_below_minima" in chunk.columns else 0
        print(f"{zone}: muestras={total} | incumplen={breaches}")

def _print_wake_stats(df: pd.DataFrame, zone_col: str = "ATCZone", breach_col: str = "wake_is_below"):
    print("\n" + "="*80)
    print("ESTADÍSTICAS DE INCUMPLIMIENTOS POR ESTELA")
    print("="*80)
    if breach_col not in df.columns:
        print("No hay columna de incumplimiento por estela en el DataFrame.")
        return
    if zone_col not in df.columns:
        total = df[breach_col].sum()
        print(f"Total incumplimientos (sin zona): {total}")
        return
    for zone in ["TWR", "TMA"]:
        chunk = df[df[zone_col] == zone]
        total = len(chunk)
        breaches = chunk[breach_col].sum()
        print(f"{zone}: muestras={total} | incumplen_estela={breaches}")

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
    # 1) Recalcular tick en df_xy para poder hacer merge
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

    # 2) Selección mínima de columnas para join y renombre
    xy_keys = ["_tick", "callsign", "ATCZone", "thr_distance_nm"]
    xy_present = [c for c in xy_keys if c in df_xy.columns]
    xy_min = df_xy[xy_present].dropna(subset=["_tick"]).copy()

    # 3) Merge por tick + callsign para el precedente y el siguiente
    # Primero asumimos que compute_distance expone 'callsign_preceding' y 'callsign_following'
    dist_df = dist_df.copy()
    if "tick_time_s" in dist_df.columns:
        # Preparar tablas de lookup
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
        # Limpiar columnas auxiliares de merge
        for aux in ["_tick_x","_tick_y","_tick"]:
            if aux in dist_df.columns:
                dist_df = dist_df.drop(columns=[aux])

        # Elegir la zona a usar por muestra: preferir la del 'following'
        dist_df["ATCZone"] = dist_df["ATCZone_fol"].combine_first(dist_df["ATCZone_pre"])
        # Elegir una thr_distance_nm para referencia: preferir la del 'following'
        dist_df["thr_distance_nm"] = dist_df["thr_distance_nm_fol"].combine_first(dist_df["thr_distance_nm_pre"])

    dist_df.to_csv("Outputs/distances_per_tick.csv", index=False)

    # 5) Paso h: mínima radar (usa ATCZone y/o thr_distance_nm ya propagadas)
    checked = check_minima(
        distances_df=dist_df,
        distance_col="distance_nm",
        tick_time_col="tick_time_s",
        pair_keys=("callsign_preceding", "callsign_following"),
        tower_threshold_nm=0.5,
    )
    checked.to_csv("Outputs/distances_minima_checked.csv", index=False)

    # Stats de mínima 3 NM
    _print_minima_stats(checked, zone_col="ATCZone")

    # 6) Paso j: estela (requiere tipos OACI previo/siguiente mapeados en 'checked')
    p3 = pd.read_excel("Inputs/P3_DEP_LEBL.xlsx", sheet_name="Hoja1")
    callsign_to_type = (
        p3[["Indicativo", "TipoAeronave"]]
        .dropna()
        .assign(Indicativo=lambda d: d["Indicativo"].astype(str).str.strip().str.upper())
        .set_index("Indicativo")["TipoAeronave"]
        .to_dict()
    )
    if "callsign_preceding" in checked.columns:
        checked["Aircraft_Type_Preceding"] = checked["callsign_preceding"].astype(str).str.upper().map(callsign_to_type)
    if "callsign_following" in checked.columns:
        checked["Aircraft_Type_Following"] = checked["callsign_following"].astype(str).str.upper().map(callsign_to_type)

    wake_df = check_wake_compliance(
        df_distances_checked=checked,
        type_pre_col="Aircraft_Type_Preceding",
        type_fol_col="Aircraft_Type_Following",
        distance_col="distance_nm",
        zone_col="ATCZone",
        classification_path="Inputs/Tabla_Clasificacion_aeronaves.xlsx",
    )
    wake_df.to_csv("Outputs/wake_checked.csv", index=False)

    # Stats de estela
    _print_wake_stats(wake_df, zone_col="ATCZone", breach_col="wake_is_below")

    loa_df = check_loa_compliance(
        df_in=wake_df,
        zone_col="ATCZone",
        distance_col="distance_nm",
        wake_pre_col="Wake_Pre",
        wake_fol_col="Wake_Fol",
        sid_pre_col="SID_Preceding",    # cambia si tus columnas tienen otros nombres o no las tienes
        sid_fol_col="SID_Following",
    )
    loa_df.to_csv("Outputs/loa_checked_TWR.csv", index=False)

    # Estadísticas simples LoA (solo TWR)
    print("\n" + "="*80)
    print("ESTADÍSTICAS DE INCUMPLIMIENTOS POR LoA (solo TWR)")
    print("="*80)
    if "loa_is_below" in loa_df.columns:
        twr = loa_df[loa_df["ATCZone"] == "TWR"]
        total_twr = len(twr)
        breaches_twr = twr["loa_is_below"].sum() if not twr.empty else 0
        print(f"TWR: muestras={total_twr} | incumplimientos_LoA={breaches_twr}")
    else:
        print("No se han generado columnas de LoA (revisa LOA_MATRIX y columnas Wake/SID).")
if __name__ == "__main__":
    main()
