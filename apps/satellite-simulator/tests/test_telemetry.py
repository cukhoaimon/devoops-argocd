import json
from datetime import datetime, timezone
from app.telemetry import TelemetryMessage
from app.states import SatelliteState
from app.orbit import OrbitalData
from app.power import PowerData
from app.thermal import ThermalData
from app.payload import PayloadData


def _make_message() -> TelemetryMessage:
    return TelemetryMessage(
        satellite_id="SAT-001",
        satellite_name="Explorer-1",
        timestamp_utc=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        state=SatelliteState.NOMINAL,
        orbital=OrbitalData(altitude_km=550.0, latitude_deg=12.4,
                            longitude_deg=-43.1, velocity_km_s=7.59, phase_rad=1.23),
        power=PowerData(battery_v=28.1, solar_w=142.0, consumption_w=95.0),
        thermal=ThermalData(cpu_temp_c=38.5, battery_temp_c=22.1, structure_temp_c=-5.3),
        payload=PayloadData(packets=[]),
    )


def test_to_json_is_valid_json():
    msg = _make_message()
    parsed = json.loads(msg.to_json())
    assert isinstance(parsed, dict)


def test_to_json_top_level_fields():
    parsed = json.loads(_make_message().to_json())
    assert parsed["satellite_id"] == "SAT-001"
    assert parsed["satellite_name"] == "Explorer-1"
    assert parsed["state"] == "NOMINAL"
    assert parsed["timestamp_utc"] == "2026-04-01T12:00:00+00:00"


def test_to_json_orbital_section():
    parsed = json.loads(_make_message().to_json())
    assert parsed["orbital"]["altitude_km"] == 550.0
    assert parsed["orbital"]["latitude_deg"] == 12.4
    assert parsed["orbital"]["longitude_deg"] == -43.1
    assert parsed["orbital"]["velocity_km_s"] == 7.59
    assert parsed["orbital"]["phase_rad"] == 1.23


def test_to_json_power_section():
    parsed = json.loads(_make_message().to_json())
    assert parsed["power"]["battery_v"] == 28.1
    assert parsed["power"]["solar_w"] == 142.0
    assert parsed["power"]["consumption_w"] == 95.0


def test_to_json_thermal_section():
    parsed = json.loads(_make_message().to_json())
    assert parsed["thermal"]["cpu_temp_c"] == 38.5
    assert parsed["thermal"]["battery_temp_c"] == 22.1
    assert parsed["thermal"]["structure_temp_c"] == -5.3


def test_to_json_payload_packets_empty_list():
    parsed = json.loads(_make_message().to_json())
    assert parsed["payload_packets"] == []
