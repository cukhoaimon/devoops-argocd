import random
from dataclasses import dataclass
from app.states import SatelliteState


@dataclass(frozen=True)
class ThermalData:
    cpu_temp_c: float
    battery_temp_c: float
    structure_temp_c: float


@dataclass
class ThermalSystem:
    cpu_temp_c: float = 35.0
    battery_temp_c: float = 20.0
    structure_temp_c: float = -2.0

    def update(self, state: SatelliteState, dt: float) -> ThermalData:
        if state == SatelliteState.ECLIPSE:
            self.cpu_temp_c += (-20.0 - self.cpu_temp_c) * 0.001 * dt
            self.battery_temp_c += (-20.0 - self.battery_temp_c) * 0.001 * dt
            self.structure_temp_c += (-40.0 - self.structure_temp_c) * 0.001 * dt
        elif state == SatelliteState.DOWNLINK_PASS:
            self.cpu_temp_c += (60.0 - self.cpu_temp_c) * 0.01 * dt
            self.battery_temp_c += (25.0 - self.battery_temp_c) * 0.001 * dt
            self.structure_temp_c += (10.0 - self.structure_temp_c) * 0.001 * dt
        elif state == SatelliteState.SAFE_MODE:
            self.cpu_temp_c += (25.0 - self.cpu_temp_c) * 0.005 * dt
            self.battery_temp_c += (18.0 - self.battery_temp_c) * 0.001 * dt
            self.structure_temp_c += (0.0 - self.structure_temp_c) * 0.001 * dt
        else:  # NOMINAL
            self.cpu_temp_c += (38.0 - self.cpu_temp_c) * 0.005 * dt
            self.battery_temp_c += (22.0 - self.battery_temp_c) * 0.001 * dt
            self.structure_temp_c += (-5.0 - self.structure_temp_c) * 0.001 * dt

        return ThermalData(
            cpu_temp_c=round(self.cpu_temp_c + random.uniform(-0.1, 0.1), 1),
            battery_temp_c=round(self.battery_temp_c + random.uniform(-0.1, 0.1), 1),
            structure_temp_c=round(self.structure_temp_c + random.uniform(-0.2, 0.2), 1),
        )
