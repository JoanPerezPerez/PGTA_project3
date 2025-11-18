# step5_main_turns_pipeline.py 
import os
import json
import webbrowser
from datetime import datetime, timezone
import random

from functions.detect_turn_start import detect_turns_all_flights
from functions.compute_radial_bcn import add_radial_from_bcn
from functions.load_and_join_radar import join_plan_radar

import pandas as pd
import simplekml


# -------------------------------------------------------------------
#   NUEVO: generar KML con TODAS las curvas detectadas
# -------------------------------------------------------------------
def build_kml_for_all_turns(df_joined: pd.DataFrame, df_turns: pd.DataFrame, output_path: str):

    kml = simplekml.Kml()

    df_filtered = df_turns[df_turns["turn_found"] == True]

    for idx, row in df_filtered.iterrows():
        flight_id = row["id"]
        df_flight = df_joined[df_joined["id"] == flight_id]

        # Crear carpeta por vuelo
        folder = kml.newfolder(name=f"Flight {flight_id}")

        # Color aleatorio en formato KML AABBGGRR
        r, g, b = [random.randint(50, 255) for _ in range(3)]
        color_hex = f"ff{b:02x}{g:02x}{r:02x}"

        # Construir trayectoria 3D
        coords = [
            (float(r["lon"]), float(r["lat"]), float(r["Hft"]) * 0.3048)
            for _, r in df_flight.iterrows()
        ]

        line = folder.newlinestring(
            name=f"Turn {flight_id}",
            coords=coords,
            altitudemode=simplekml.AltitudeMode.absolute
        )
        line.style.linestyle.color = color_hex
        line.style.linestyle.width = 3

    kml.save(output_path)


# -------------------------------------------------------------------
def main_turns_pipeline():
    os.makedirs("Outputs", exist_ok=True)

    df_joined = join_plan_radar(
        "Inputs/P3_DEP_LEBL.xlsx",
        "Inputs/P3_04h_08h.csv",
    )

    df_turns = detect_turns_all_flights(df_joined)
    df_turns = add_radial_from_bcn(df_turns)
    df_turns.to_csv("Outputs/turns_start_24L_with_radial.csv", index=False)

    # Exportar trayectorias originales
    for flight_id, g in df_joined.groupby("id"):
        callsign = g["callsign_norm"].iloc[0]
        out_path = f"Outputs/trajectory_{flight_id}_{callsign}.csv"
        g[["Time", "lat", "lon", "Hft"]].to_csv(out_path, index=False)

    # Generar KML con todas las curvas detectadas
    kml_path = "Outputs/all_turns.kml"
    build_kml_for_all_turns(df_joined, df_turns, kml_path)

    # Abrir en Google Earth
    abs_kml = os.path.abspath(kml_path)
    webbrowser.open(f"file://{abs_kml}")
    print("KML generado correctamente:", abs_kml)


if __name__ == "__main__":
    main_turns_pipeline()
