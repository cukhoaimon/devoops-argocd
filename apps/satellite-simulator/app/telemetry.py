import json
from dataclasses import dataclass
from datetime import datetime
from app.states import SatelliteState
from app.orbit import OrbitalData
from app.power import PowerData
from app.thermal import ThermalData
from app.payload import PayloadData


@dataclass
class TelemetryMessage:
    satellite_id: str
    satellite_name: str
    timestamp_utc: datetime
    state: SatelliteState
    orbital: OrbitalData
    power: PowerData
    thermal: ThermalData
    payload: PayloadData

    def to_json(self) -> str:
        return json.dumps({
            "satellite_id": self.satellite_id,
            "satellite_name": self.satellite_name,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "state": self.state.value,
            "orbital": {
                "altitude_km": self.orbital.altitude_km,
                "latitude_deg": self.orbital.latitude_deg,
                "longitude_deg": self.orbital.longitude_deg,
                "velocity_km_s": self.orbital.velocity_km_s,
                "phase_rad": self.orbital.phase_rad,
            },
            "power": {
                "battery_v": self.power.battery_v,
                "solar_w": self.power.solar_w,
                "consumption_w": self.power.consumption_w,
            },
            "thermal": {
                "cpu_temp_c": self.thermal.cpu_temp_c,
                "battery_temp_c": self.thermal.battery_temp_c,
                "structure_temp_c": self.thermal.structure_temp_c,
            },
            "payload_packets": self.payload.packets,
        })
