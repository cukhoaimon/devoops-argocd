import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0
GM_KM3_S2 = 3.986e5  # Earth's gravitational parameter

# Eclipse arc: phase in [0.64π, 1.36π] ≈ 36% of orbit
_ECLIPSE_START = math.pi * 0.64
_ECLIPSE_END = math.pi * 1.36
# Downlink window: within 0.1 rad of phase = 0 (ascending node)
_DOWNLINK_ARC = 0.1


@dataclass
class OrbitalData:
    altitude_km: float
    latitude_deg: float
    longitude_deg: float
    velocity_km_s: float
    phase_rad: float


@dataclass
class Orbit:
    altitude_km: float = 550.0
    inclination_deg: float = 53.0
    period_s: float = 5760.0  # ~96 min LEO
    phase_rad: float = 0.0

    @property
    def _angular_velocity(self) -> float:
        return 2 * math.pi / self.period_s

    @property
    def _velocity_km_s(self) -> float:
        r = EARTH_RADIUS_KM + self.altitude_km
        return math.sqrt(GM_KM3_S2 / r)

    def step(self, dt: float) -> OrbitalData:
        self.phase_rad = (self.phase_rad + self._angular_velocity * dt) % (2 * math.pi)
        inc_rad = math.radians(self.inclination_deg)
        lat = math.degrees(math.asin(math.sin(inc_rad) * math.sin(self.phase_rad)))
        lon = math.degrees(math.atan2(
            math.cos(inc_rad) * math.sin(self.phase_rad),
            math.cos(self.phase_rad),
        ))
        return OrbitalData(
            altitude_km=self.altitude_km,
            latitude_deg=round(lat, 4),
            longitude_deg=round(lon, 4),
            velocity_km_s=round(self._velocity_km_s, 3),
            phase_rad=round(self.phase_rad, 6),
        )

    def is_eclipse(self) -> bool:
        return _ECLIPSE_START <= self.phase_rad <= _ECLIPSE_END

    def is_downlink_window(self) -> bool:
        return self.phase_rad < _DOWNLINK_ARC or self.phase_rad > (2 * math.pi - _DOWNLINK_ARC)
