import random
from datetime import datetime, timezone
from app.states import SatelliteState
from app.orbit import Orbit
from app.power import PowerSystem
from app.thermal import ThermalSystem
from app.payload import Payload
from app.telemetry import TelemetryMessage


class Satellite:
    def __init__(
        self,
        id: str,
        name: str,
        orbit: Orbit,
        anomaly_probability: float = 0.005,
        power: PowerSystem = None,
        thermal: ThermalSystem = None,
        payload: Payload = None,
        state: SatelliteState = SatelliteState.NOMINAL,
    ):
        self.id = id
        self.name = name
        self.orbit = orbit
        self.anomaly_probability = anomaly_probability
        self.power = power or PowerSystem()
        self.thermal = thermal or ThermalSystem()
        self.payload = payload or Payload()
        self.state = state
        self._safe_mode_ticks = 0
        self._safe_mode_recovery = 30

    def tick(self, dt: float) -> TelemetryMessage:
        now = datetime.now(timezone.utc)
        orbital_data = self.orbit.step(dt)
        self._transition_state()
        power_data = self.power.update(self.state, dt)
        thermal_data = self.thermal.update(self.state, dt)
        payload_data = self.payload.update(self.state, now)
        return TelemetryMessage(
            satellite_id=self.id,
            satellite_name=self.name,
            timestamp_utc=now,
            state=self.state,
            orbital=orbital_data,
            power=power_data,
            thermal=thermal_data,
            payload=payload_data,
        )

    def _transition_state(self) -> None:
        if self.state == SatelliteState.SAFE_MODE:
            self._safe_mode_ticks += 1
            if self._safe_mode_ticks >= self._safe_mode_recovery:
                self.state = SatelliteState.NOMINAL
                self._safe_mode_ticks = 0
            return

        # ECLIPSE takes priority over everything
        if self.orbit.is_eclipse():
            self.state = SatelliteState.ECLIPSE
            return

        # Exiting ECLIPSE always goes to NOMINAL first
        if self.state == SatelliteState.ECLIPSE:
            self.state = SatelliteState.NOMINAL
            return

        # Random anomaly → SAFE_MODE
        if random.random() < self.anomaly_probability:
            self.state = SatelliteState.SAFE_MODE
            self._safe_mode_ticks = 0
            return

        if self.orbit.is_downlink_window():
            self.state = SatelliteState.DOWNLINK_PASS
        else:
            self.state = SatelliteState.NOMINAL
