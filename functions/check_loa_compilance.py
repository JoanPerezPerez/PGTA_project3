import re
import pandas as pd


# ---------- Clasificación ICAO -> Grupo de LoA ----------

def _build_icao_to_group(path_class="Inputs/Tabla_Clasificacion_aeronaves.xlsx", sheet="Hoja1"):
    """
    Carga la tabla de clasificación y devuelve un dict ICAO -> Grupo ('HP','R','LP','NR+','NR-','NO REACTOR').
    """
    dfc = pd.read_excel(path_class, sheet_name=sheet)
    icao_to_group = {}
    for col in dfc.columns:
        series = (
            dfc[col]
            .dropna()
            .astype(str)
            .str.split(',')
            .explode()
            .str.strip()
            .str.upper()
        )
        for code in series:
            if code:
                icao_to_group[code] = col.strip().upper()
    return icao_to_group  # ej.: {"A320":"HP", "B738":"HP", "AT72":"LP", ...}


def _fallback_group_by_icao_prefix(icao: str) -> str | None:
    """
    Cobertura para modelos comunes no presentes en la tabla de clasificación.
    """
    if not icao:
        return None
    icao = icao.upper().strip()
    # Reactores comerciales (HP)
    if icao.startswith(("A31", "A32", "A33", "A34", "A35", "A20", "A21")):  # A319/A320/A321/A330/A350/Neo
        return "HP"
    if icao.startswith(("B73", "B38", "B39", "B78", "B77", "B74")):        # 737/Max/787/777/747
        return "HP"
    if icao.startswith(("E19", "E17", "E90")):                              # E190/195/E170/175
        return "HP"
    if icao in {"FA7X", "GLF4", "GLF5", "GLF6", "CL60", "CL35", "CL30", "C56X", "C68A", "C680", "C25C"}:
        return "HP"
    if icao in {"A339", "A338", "A332", "A333", "B789", "B788", "B78X", "B77W", "B772", "B773"}:
        return "HP"
    # Turboprop / ligeros (LP)
    if icao in {"AT72", "AT76", "DH8A", "DH8B", "DH8C", "DH8D"}:
        return "LP"
    if icao in {"C200", "C25A", "C25B", "C208", "BN2P", "DA42", "DA62"}:
        return "LP"
    # Por defecto: si parece ICAO válido con letra + al menos 2 dígitos, asumir HP (reactor)
    if re.match(r'^[A-Z]\d{2,}', icao):
        return "HP"
    return None


# ---------- Tablas de "misma SID" por pista ----------

def _load_same_sid_sets(runway: str):
    """
    Devuelve lista de sets; cada set corresponde a una columna de la tabla 'Misma SID' de la pista.
    Los valores de los sets son claves tipo 'LOTOS-C', 'OLOXO-R', etc.
    """
    if runway == "LEBL-06R":
        df = pd.read_excel("Inputs/Tabla_misma_SID_06R.xlsx", sheet_name="Hoja1")
    elif runway == "LEBL-24L":
        df = pd.read_excel("Inputs/Tabla_misma_SID_24L.xlsx", sheet_name="Hoja1")
    else:
        return []
    groups = []
    for col in df.columns:
        vals = (
            df[col]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )
        groups.append(set(vals))
    return groups


# ---------- Normalización de procedimientos (SIDs) ----------

def _sid_base(proc: str) -> str:
    """
    Devuelve el nombre base de la SID (primeras 5 letras).
    Ej.: 'LOTOS1C' -> 'LOTOS' ; 'LARPA4R' -> 'LARPA'
    """
    s = str(proc).strip().upper()
    m = re.match(r'([A-Z]{5})', s)
    return m.group(1) if m else ""


def _proc_to_table_key(proc: str, runway: str) -> str:
    """
    Convierte un ProcDesp a la clave usada en las tablas: BASE-<C|R>
    - BASE = primeras 5 letras del nombre de la SID (p. ej., LOTOS, LARPA, OLOXO, GRAUS...)
    - 24L -> sufijo '-C'
    - 06R -> sufijo '-R'
    Si la pista es distinta a 24L/06R, devuelve '' para forzar 'distinta SID'.
    """
    if pd.isna(proc) or proc is None:
        return ""
    base = _sid_base(proc)
    if not base or len(base) < 3:
        return ""
    suffix = "-C" if runway == "LEBL-24L" else "-R" if runway == "LEBL-06R" else ""
    return f"{base}{suffix}" if suffix else ""


def _are_same_sid(proc_prec: str, proc_foll: str, runway_prec: str, runway_foll: str) -> bool:
    """
    Determina si ambos procedimientos pertenecen a la misma columna de la tabla de la pista.
    Criterios:
    - Si falta uno o ambos procedimientos, o son '-', devuelve False (distinta SID).
    - Si las pistas no coinciden, devuelve False.
    - Para comparar, se usa la clave BASE-<C|R> construida con las 5 letras base y la pista.
    """
    # 1) Procedimientos válidos
    if (proc_prec is None) or (proc_foll is None):
        return False
    if pd.isna(proc_prec) or pd.isna(proc_foll):
        return False
    if str(proc_prec).strip() == "-" or str(proc_foll).strip() == "-":
        return False

    # 2) Misma pista
    if runway_prec != runway_foll:
        return False

    # 3) Tabla de la pista
    groups = _load_same_sid_sets(runway_prec)
    if not groups:
        return False

    # 4) Claves de comparación
    key1 = _proc_to_table_key(proc_prec, runway_prec)
    key2 = _proc_to_table_key(proc_foll, runway_foll)
    if not key1 or not key2:
        return False

    # 5) Misma columna -> misma SID
    for g in groups:
        if key1 in g and key2 in g:
            return True
    return False


# ---------- Matriz mínima LoA (imagen adjunta) ----------

LOA_MIN_NM = {
    "HP": {
        "HP": {"same": 5, "diff": 3},
        "R":  {"same": 5, "diff": 3},
        "LP": {"same": 5, "diff": 3},
        "NR+": {"same": 3, "diff": 3},
        "NR-": {"same": 3, "diff": 3},
        "NO REACTOR": {"same": 3, "diff": 3},
    },
    "R": {
        "HP": {"same": 7, "diff": 5},
        "R":  {"same": 5, "diff": 3},
        "LP": {"same": 5, "diff": 3},
        "NR+": {"same": 3, "diff": 3},
        "NR-": {"same": 3, "diff": 3},
        "NO REACTOR": {"same": 3, "diff": 3},
    },
    "LP": {
        "HP": {"same": 8, "diff": 6},
        "R":  {"same": 6, "diff": 4},
        "LP": {"same": 5, "diff": 3},
        "NR+": {"same": 3, "diff": 3},
        "NR-": {"same": 3, "diff": 3},
        "NO REACTOR": {"same": 3, "diff": 3},
    },
    "NR+": {
        "HP": {"same": 11, "diff": 8},
        "R":  {"same": 9, "diff": 6},
        "LP": {"same": 9, "diff": 6},
        "NR+": {"same": 5, "diff": 3},
        "NR-": {"same": 3, "diff": 3},
        "NO REACTOR": {"same": 3, "diff": 3},
    },
    "NR-": {
        "HP": {"same": 9, "diff": 9},
        "R":  {"same": 9, "diff": 9},
        "LP": {"same": 9, "diff": 9},
        "NR+": {"same": 9, "diff": 6},
        "NR-": {"same": 5, "diff": 3},
        "NO REACTOR": {"same": 3, "diff": 3},
    },
    "NO REACTOR": {
        "HP": {"same": 9, "diff": 9},
        "R":  {"same": 9, "diff": 9},
        "LP": {"same": 9, "diff": 9},
        "NR+": {"same": 9, "diff": 9},
        "NR-": {"same": 9, "diff": 9},
        "NO REACTOR": {"same": 5, "diff": 3},
    },
}


def _normalize_group(g):
    if pd.isna(g):
        return None
    g = str(g).strip().upper()
    aliases = {
        "NO REACTOR": "NO REACTOR",
        "NO_REACTOR": "NO REACTOR",
        "NOREACTOR": "NO REACTOR",
        "NRPLUS": "NR+",
        "NR-PLUS": "NR+",
        "NRMINUS": "NR-",
        "NR-MINUS": "NR-",
    }
    return aliases.get(g, g)


def _lookup_min_nm(group_prec, group_foll, same_sid: bool):
    """
    Devuelve la separación mínima exigida en NM para la pareja (precedente, sucesiva)
    y el contexto de misma/distinta SID.
    """
    gp = _normalize_group(group_prec)
    gf = _normalize_group(group_foll)
    key = "same" if same_sid else "diff"
    try:
        cell = LOA_MIN_NM[gp][gf]
        return cell[key] if cell is not None else None
    except Exception:
        return None  # sin criterio definido


# ---------- Verificación LoA (solo TWR) ----------

def check_loa_compliance(df_pairs: pd.DataFrame,
                         path_class="Inputs/Tabla_Clasificacion_aeronaves.xlsx") -> pd.DataFrame:
    """
    df_pairs: resultado de get_twr_tma_distances() con columnas:
      - ac_type_preceding, ac_type_following, proc_preceding, proc_following,
        runway_preceding, runway_following, distance_twr_nm, distance_tma_nm
    Devuelve df con columnas añadidas, evaluando LoA SOLO en TWR:
      - engine_group_preceding, engine_group_following
      - same_runway, same_sid
      - loa_min_required_nm
      - twr_ok, tma_ok (True por convención), loa_ok
      - reason
    Las filas sin engine group en cualquiera de los vuelos se consideran mal formadas y se excluyen.
    """
    df = df_pairs.copy()

    # 1) Clasificación ICAO -> grupo con fallback
    icao_to_group = _build_icao_to_group(path_class=path_class)

    def map_group(icao):
        if pd.isna(icao):
            return None
        code = str(icao).strip().upper()
        grp = _normalize_group(icao_to_group.get(code))
        if grp is None:
            grp = _fallback_group_by_icao_prefix(code)
        return grp

    df["engine_group_preceding"] = df["ac_type_preceding"].apply(map_group)
    df["engine_group_following"]  = df["ac_type_following"].apply(map_group)

    # 1b) Marcar y excluir mal formadas por grupo ausente
    df["malformed_engine_group"] = df["engine_group_preceding"].isna() | df["engine_group_following"].isna()
    df_bad = df[df["malformed_engine_group"]].copy()
    df = df[~df["malformed_engine_group"]].copy()

    # 2) Misma pista y misma SID
    df["same_runway"] = df["runway_preceding"] == df["runway_following"]

    same_sid_flags = []
    for _, r in df.iterrows():
        same_sid = _are_same_sid(
            r["proc_preceding"], r["proc_following"],
            r["runway_preceding"], r["runway_following"]
        )
        same_sid_flags.append(same_sid)
    df["same_sid"] = same_sid_flags

    # 3) Mínimo LoA exigido
    df["loa_min_required_nm"] = [
        _lookup_min_nm(r["engine_group_preceding"],
                       r["engine_group_following"],
                       bool(r["same_sid"]))
        for _, r in df.iterrows()
    ]

    # 4) Evaluación LoA SOLO en TWR
    def twr_ok(twr, req):
        if req is None:
            return True
        if pd.isna(twr):
            return False  # sin TWR no se puede validar LoA
        return float(twr) >= float(req)

    df["twr_ok"] = [twr_ok(t, r) for t, r in zip(df["distance_twr_nm"], df["loa_min_required_nm"])]
    df["tma_ok"] = True  # LoA no aplica en TMA
    df["loa_ok"] = df["twr_ok"]

    # 5) Motivo
    def reason_row(ok, twr, req):
        if ok:
            return ""
        if req is None:
            return "Sin requisito LoA aplicable"
        if pd.isna(twr):
            return "Sin distancia TWR disponible"
        return f"TWR {twr:.1f} < {req}"

    df["reason"] = [reason_row(ok, t, r) for ok, t, r in zip(df["loa_ok"],
                                                             df["distance_twr_nm"],
                                                             df["loa_min_required_nm"])]

    # 6) Devolver solo bien formadas; si quieres las mal formadas, descomenta:
    # return df, df_bad
    return df
