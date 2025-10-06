# diapo 31
# data_item.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class DataItem:
    """
    Clase que representa un registro de datos radar decodificados CAT048.
    Según las especificaciones del proyecto (diapositivas 31-34).
    """
    
    # Identificación y posición
    time: float  # I140 ToD - Time of Day (segundos desde medianoche)
    track_number: int  # I161 - Número de seguimiento
    callsign: Optional[str]  # I240 Tid - Callsign (puede estar vacío)
    target_address: Optional[str]  # TA - Target Address
    mode_3a: Optional[str]  # Mode 3/A code
    
    # Coordenadas polares
    rho: float  # I040 - Distancia en NM
    theta: float  # I040 - Azimut en grados
    
    # Coordenadas geodésicas
    lat: float  # Latitud en grados decimales
    lon: float  # Longitud en grados decimales
    h: float  # Altitud geométrica en pies
    
    # Coordenadas cartesianas (proyección estereográfica)
    x: Optional[float] = None  # Coordenada X proyectada
    y: Optional[float] = None  # Coordenada Y proyectada
    
    # Altitud y nivel de vuelo
    fl: Optional[float] = None  # I090 FL - Flight Level (no corregido bajo 6000 ft)
    barometric_altitude: Optional[float] = None  # Altitud barométrica corregida por QNH
    
    # Estado de vuelo
    flight_status: Optional[str] = None  # I230 STAT - Flight Status
    
    # BDS 4.0 - Configuración barométrica
    bds40_bp: Optional[float] = None  # I250 BDS 4.0 BP - Barometric Pressure settings
    
    # BDS 5.0 - Parámetros de navegación (refresco 16 sg)
    bds50_roll_angle: Optional[float] = None  # Roll Angle en grados
    bds50_true_track_angle: Optional[float] = None  # TTA - True track angle en grados
    bds50_ground_speed: Optional[float] = None  # GS - Ground Speed en knots
    bds50_track_angle_rate: Optional[float] = None  # TAR - Track angle rate en grados/sg
    bds50_true_airspeed: Optional[float] = None  # TAS - True airspeed en knots
    
    # BDS 6.0 - Parámetros de instrumentos (refresco 4 sg)
    bds60_magnetic_heading: Optional[float] = None  # HDG - Magnetic Heading en grados
    bds60_indicated_airspeed: Optional[float] = None  # IAS - Indicated Airspeed en knots
    bds60_barometric_altitude_rate: Optional[float] = None  # Barometric altitude rate
    bds60_inertial_vertical_velocity: Optional[float] = None  # IVV - Inertial vertical velocity en ft/min
    
    def __post_init__(self):
        """
        Validaciones después de la inicialización.
        Aplica los filtros mencionados en las diapositivas 33-34:
        - Solo tráficos en vuelo (no on ground)
        - Con FL recibido
        """
        pass
    
    def is_on_ground(self) -> bool:
        """
        Determina si la aeronave está en tierra según I230 STAT.
        Retorna True si está en tierra, False si está en vuelo.
        """
        if self.flight_status:
            # Implementar lógica según bits del flight_status
            # Ver Data Item I230-STAT en documentación CAT048
            return False  # Placeholder
        return False
    
    def has_valid_fl(self) -> bool:
        """
        Verifica si tiene un FL válido recibido.
        """
        return self.fl is not None
    
    def is_in_geographic_filter(self) -> bool:
        """
        Verifica si está dentro del filtro geográfico (diapositiva 34):
        40.9° N < Latitud < 41.7° N
        1.5° E < Longitud < 2.6° E
        """
        return (40.9 <= self.lat <= 41.7 and 
                1.5 <= self.lon <= 2.6)
    
    def is_below_6000ft(self) -> bool:
        """
        Verifica si está por debajo de 6000 ft (diapositiva 34).
        Usa altitud corregida por QNH.
        """
        if self.barometric_altitude is not None:
            return self.barometric_altitude <= 6000
        return False
    
    def calculate_qnh_corrected_altitude(self, qnh: float = 1013.25) -> float:
        """
        Calcula la altitud corregida por QNH.
        Por debajo de 6000 ft se debe usar altitud corregida.
        
        Args:
            qnh: Presión QNH en hPa (por defecto ISA standard 1013.25)
        
        Returns:
            Altitud corregida en pies
        """
        if self.bds40_bp and self.fl:
            # Implementar corrección QNH
            # Fórmula aproximada: cada hPa de diferencia = ~27 ft
            qnh_diff = qnh - self.bds40_bp
            correction = qnh_diff * 27
            return (self.fl * 100) + correction
        return self.fl * 100 if self.fl else self.h
    
    def set_stereographic_coordinates(self, x: float, y: float):
        """
        Establece las coordenadas proyectadas estereográficamente.
        
        Args:
            x: Coordenada X en el plano proyectado
            y: Coordenada Y en el plano proyectado
        """
        self.x = x
        self.y = y
    
    def get_time_of_day(self) -> str:
        """
        Convierte el Time of Day (segundos desde medianoche) a formato HH:MM:SS.
        """
        hours = int(self.time // 3600)
        minutes = int((self.time % 3600) // 60)
        seconds = int(self.time % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def __repr__(self) -> str:
        return (f"DataItem(time={self.get_time_of_day()}, "
                f"callsign={self.callsign}, "
                f"track={self.track_number}, "
                f"lat={self.lat:.4f}, lon={self.lon:.4f}, "
                f"alt={self.barometric_altitude or self.h:.0f}ft)")

  