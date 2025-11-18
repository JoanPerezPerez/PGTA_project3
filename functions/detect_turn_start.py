# step3_detect_turn_start.py

import numpy as np
import pandas as pd

RUNWAY_24L_TRACK = 240.0  # aprox
ROLL_THRESHOLD_DEG = 3.0
TRACK_DELTA_DEG = 1.0
MIN_TURN_ALT_FT = 500.0


def angle_diff(a: float, b: float) -> float:
    diff = (a - b + 180) % 360 - 180
    return abs(diff)


def detect_turn_start_for_flight(group: pd.DataFrame) -> pd.Series:
    """
    Recibe todas las trazas de un vuelo (mismo id) y devuelve una fila con:
      - id
      - callsign
      - turn_found (bool)
      - time_turn, time_turn_seconds
      - lat_turn, lon_turn
      - x_turn, y_turn
      - alt_ft_turn, roll_turn_deg, track_turn_deg
    """
    g = group.sort_values("time_seconds").copy()

    # Identificadores básicos
    flight_id = g["id"].iloc[0] if "id" in g.columns else None
    callsign = (
        g["callsign_norm"].iloc[0]
        if "callsign_norm" in g.columns
        else g["callsign"].iloc[0] if "callsign" in g.columns
        else None
    )

    # Si faltan columnas clave, devolvemos una fila "sin viraje" pero con campos definidos
    required_cols = ["track_rate", "ROLL", "Hft", "lat", "lon"]
    if not all(c in g.columns for c in required_cols):
        return pd.Series(
            {
                "id": flight_id,
                "callsign": callsign,
                "turn_found": False,
                "time_turn": None,
                "time_turn_seconds": np.nan,
                "lat_turn": np.nan,
                "lon_turn": np.nan,
                "x_turn": np.nan,
                "y_turn": np.nan,
                "alt_ft_turn": np.nan,
                "roll_turn_deg": np.nan,
                "track_turn_deg": np.nan,
            }
        )

    # Cálculo del ángulo relativo al rumbo de pista
    g["track_delta_runway"] = g["track_rate"].apply(
        lambda x: angle_diff(x, RUNWAY_24L_TRACK)
    )

    cond_roll = g["ROLL"].abs() >= ROLL_THRESHOLD_DEG
    cond_track = g["track_delta_runway"] >= TRACK_DELTA_DEG
    cond_alt = g["Hft"] >= MIN_TURN_ALT_FT

    idx_candidates = g.index[cond_roll & cond_track & cond_alt]

    # Ningún punto pasa los umbrales → sin viraje
    if len(idx_candidates) == 0:
        return pd.Series(
            {
                "id": flight_id,
                "callsign": callsign,
                "turn_found": False,
                "time_turn": None,
                "time_turn_seconds": np.nan,
                "lat_turn": np.nan,
                "lon_turn": np.nan,
                "x_turn": np.nan,
                "y_turn": np.nan,
                "alt_ft_turn": np.nan,
                "roll_turn_deg": np.nan,
                "track_turn_deg": np.nan,
            }
        )

    # Primer punto que cumple condiciones de viraje
    idx_turn = idx_candidates[0]
    row = g.loc[idx_turn]

    return pd.Series(
        {
            "id": flight_id,
            "callsign": callsign,
            "turn_found": True,
            "time_turn": row["Time"] if "Time" in row.index else None,
            "time_turn_seconds": row["time_seconds"],
            "lat_turn": row["lat"],
            "lon_turn": row["lon"],
            "x_turn": row.get("X", np.nan),
            "y_turn": row.get("Y", np.nan),
            "alt_ft_turn": row["Hft"],
            "roll_turn_deg": row["ROLL"],
            "track_turn_deg": row["track_rate"],
        }
    )
def detect_turns_all_flights(df_joined: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve un DataFrame plano con una fila por vuelo:
    ['id','callsign','turn_found','time_turn','time_turn_seconds',
     'lat_turn','lon_turn','x_turn','y_turn',
     'alt_ft_turn','roll_turn_deg','track_turn_deg']
    """
    # Agrupar por id sin añadir la columna de grupo al resultado
    results = df_joined.groupby(
        "id", group_keys=False
    ).apply(detect_turn_start_for_flight)

    # Asegurar DataFrame y resetear índice
    df_res = pd.DataFrame(results).reset_index(drop=True)

    # Reordenar columnas a un orden coherente
    cols_order = [
        "id",
        "callsign",
        "turn_found",
        "time_turn",
        "time_turn_seconds",
        "lat_turn",
        "lon_turn",
        "x_turn",
        "y_turn",
        "alt_ft_turn",
        "roll_turn_deg",
        "track_turn_deg",
    ]
    # Mantener solo las que existan, en ese orden
    cols_final = [c for c in cols_order if c in df_res.columns]
    df_res = df_res[cols_final]

    # Por seguridad, si falta turn_found, crearlo como False
    if "turn_found" not in df_res.columns:
        df_res["turn_found"] = False

    return df_res
