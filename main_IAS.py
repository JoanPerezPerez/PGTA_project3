import pandas as pd
from functions.ias_functions import extract_IAS_by_altitude, save_results_csv
from functions.load_and_join_radar import join_plan_radar


def main_IAS():
    path_plan = "Inputs/P3_DEP_LEBL.xlsx"
    path_rad = "Inputs/P3_04h_08h.csv"
    output_csv = "Outputs/IAS_altitudes.csv"

    # Para 24L
    df_24L = join_plan_radar(path_plan, path_rad, runway="LEBL-24L")
    df_24L_stats = extract_IAS_by_altitude(df_24L)

    # Para 06R
    df_06R = join_plan_radar(path_plan, path_rad, runway="LEBL-06R")
    df_06R_stats = extract_IAS_by_altitude(df_06R)

    # Concatenar resultados
    df_all = pd.concat([df_06R_stats, df_24L_stats], ignore_index=True)

    save_results_csv(df_all, output_csv)

if __name__ == "__main__":
    main_IAS()
