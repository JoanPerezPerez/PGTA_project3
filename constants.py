"""
constants.py - Constantes del proyecto
Proyecto 3 - PGTA
"""

# Umbrales de pista
THR_24L_LAT = 41 + 17/60 + 31.99/3600  # 41°17'31.99"N
THR_24L_LON = 2 + 6/60 + 11.81/3600    # 2°06'11.81"E

THR_06R_LAT = 41 + 16/60 + 56.32/3600  # 41°16'56.32"N
THR_06R_LON = 2 + 4/60 + 27.66/3600    # 2°04'27.66"E

# Centro de proyección estereográfica (TMA)
TMA_CENTER_LAT = 41 + 6/60 + 56.560/3600  # 41°06'56.560"N
TMA_CENTER_LON = 1 + 41/60 + 33.010/3600  # 1°41'33.010"E

# Radio de la esfera conforme
RADIO_ESFERA_CONFORME_NM = 3438.954  # Radio en NM
RADIO_ESFERA_CONFORME_M = 6368942.808  # Radio en metros

# Mínimas de separación radar (CORREGIDO)
MINIMA_RADAR_TWR_NM = 3.0  # 3 NM en zona TWR
MINIMA_RADAR_TMA_NM = 3.0  # 5 NM en zona TMA

# Distancia inicial para considerar el cálculo
DISTANCIA_INICIAL_CALCULO_NM = 0.5

# Separación por estela turbulenta (NM) - Aplicable en TWR y TMA
WAKE_TURBULENCE_SEPARATION = {
    ('SUPER', 'HEAVY'): 6,
    ('SUPER', 'MEDIUM'): 7,
    ('SUPER', 'LIGHT'): 8,
    ('HEAVY', 'HEAVY'): 4,
    ('HEAVY', 'MEDIUM'): 5,
    ('HEAVY', 'LIGHT'): 6,
    ('MEDIUM', 'LIGHT'): 5,
}

TOLERANCE_TIME_SECONDS = 1
