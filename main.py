# main.py - Programa principal
# Proyecto 3 - PGTA

from typing import List
from functions.P3_loader_and_filter import filtrar_asterix_por_callsigns_y_dominios, leer_callsigns_validos_p3
from functions.add_xy import add_xy_to_filtered_csv

def main():
    # 1) Leer el conjunto de callsigns válidos desde P3
    callsigns_validos = leer_callsigns_validos_p3("Inputs/P3_DEP_LEBL.xlsx", hoja="Hoja1")

    # 2) Aplicar filtro a uno o varios CSV CAT048 ya decodificados
    rutas_csv: List[str] = ["Inputs/P3_04h_08h.csv"]
    _ = filtrar_asterix_por_callsigns_y_dominios(
        rutas_csv_asterix=rutas_csv,
        callsigns_validos=callsigns_validos,
        salida_csv="Outputs/cat048_filtered_LEBL_DEP.csv",
    )

    # 3) Añadir coordenadas X,Y estereográficas al CSV filtrado
    _ = add_xy_to_filtered_csv(
        ruta_csv_filtrado="Outputs/cat048_filtered_LEBL_DEP.csv",
        salida_csv="Outputs/cat048_filtered_LEBL_DEP_with_xy.csv",
        # Usa los nombres REALES del CSV mostrado: 'lat' y 'lon'
        lat_col="lat",
        lon_col="lon",
        # Este CSV usa punto decimal, no coma:
        decimal=None,  # dejar a None para que pandas autodetecte (equivalente a no pasarlo)
        sep=",",       # tu muestra está separada por comas
    )

if __name__ == "__main__":
    main()
