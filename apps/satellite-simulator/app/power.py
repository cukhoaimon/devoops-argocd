import random
from dataclasses import dataclass

from app.states import SatelliteState

_NOMINAL_SOLAR_W = 150.0
_NOMINAL_CONSUMPTION_W = 90.0
_DOWNLINK_EXTRA_W = 15.0
_SAFE_CONSUMPTION_W = 20.0
_BATTERY_MAX_V = 32.0
_BATTERY_MIN_V = 22.0
_CHARGE_RATE = 0.001  # V per second when charging
_DRAIN_RATE = 0.0005  # V per second when in eclipse


@dataclass
class PowerData:
    battery_v: float
    solar_w: float
    consumption_w: float


@dataclass
class PowerSystem:
    battery_v: float = 28.0

    def update(self, state: SatelliteState, dt: float) -> PowerData:
        if state == SatelliteState.ECLIPSE:
            solar_w = 0.0
            consumption_w = _NOMINAL_CONSUMPTION_W
            self.battery_v = max(_BATTERY_MIN_V, self.battery_v - _DRAIN_RATE * dt)
        elif state == SatelliteState.SAFE_MODE:
            solar_w = _NOMINAL_SOLAR_W * 0.8
            consumption_w = _SAFE_CONSUMPTION_W
            self.battery_v = min(_BATTERY_MAX_V, self.battery_v + _CHARGE_RATE * dt)
        elif state == SatelliteState.DOWNLINK_PASS:
            solar_w = _NOMINAL_SOLAR_W + random.uniform(-5, 5)
            consumption_w = _NOMINAL_CONSUMPTION_W + _DOWNLINK_EXTRA_W
            self.battery_v = min(_BATTERY_MAX_V, self.battery_v + _CHARGE_RATE * 0.5 * dt)
        else:  # NOMINAL
            solar_w = _NOMINAL_SOLAR_W + random.uniform(-5, 5)
            consumption_w = _NOMINAL_CONSUMPTION_W
            self.battery_v = min(_BATTERY_MAX_V, self.battery_v + _CHARGE_RATE * 0.5 * dt)

        return PowerData(
            battery_v=round(max(_BATTERY_MIN_V, self.battery_v + random.uniform(-0.05, 0.05)), 2),
            solar_w=round(solar_w, 1),
            consumption_w=round(consumption_w, 1),
        )
