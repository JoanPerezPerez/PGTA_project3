# load_dept_24L.py

import pandas as pd


def load_departures_24L(path_excel: str) -> pd.DataFrame:
    df = pd.read_excel(path_excel, sheet_name="Hoja1")

    # Normalizar indicativo
    df["Indicativo_norm"] = df["Indicativo"].astype(str).str.strip().str.upper()

    # Filtrar 24L y 06R si te interesa usar ambos
    df = df[df["PistaDesp"].isin(["LEBL-24L"])].copy()

    return df[["id", "Indicativo_norm", "PistaDesp", "ProcDesp", "ATOT"]]
