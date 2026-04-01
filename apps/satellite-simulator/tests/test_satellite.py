import math
from app.satellite import Satellite
from app.orbit import Orbit
from app.states import SatelliteState
from app.telemetry import TelemetryMessage


def _make_satellite(**kwargs) -> Satellite:
    return Satellite(
        id="SAT-001",
        name="Explorer-1",
        orbit=Orbit(period_s=5760.0),
        **kwargs,
    )


def test_tick_returns_telemetry_message():
    sat = _make_satellite()
    msg = sat.tick(dt=1.0)
    assert isinstance(msg, TelemetryMessage)
    assert msg.satellite_id == "SAT-001"


def test_initial_state_is_nominal():
    sat = _make_satellite()
    assert sat.state == SatelliteState.NOMINAL


def test_transitions_to_eclipse_when_in_shadow():
    sat = _make_satellite()
    sat.orbit.phase_rad = math.pi  # midpoint of shadow arc
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.ECLIPSE


def test_exits_eclipse_when_outside_shadow():
    sat = _make_satellite()
    sat.state = SatelliteState.ECLIPSE
    sat.orbit.phase_rad = 0.0  # outside shadow
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.NOMINAL


def test_transitions_to_downlink_near_phase_zero():
    sat = _make_satellite(anomaly_probability=0.0)
    sat.orbit.phase_rad = 0.05  # within downlink window
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.DOWNLINK_PASS


def test_eclipse_takes_priority_over_downlink():
    sat = _make_satellite()
    sat.orbit.phase_rad = math.pi
    sat.state = SatelliteState.DOWNLINK_PASS
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.ECLIPSE


def test_recovers_from_safe_mode_after_recovery_ticks():
    sat = _make_satellite()
    sat.state = SatelliteState.SAFE_MODE
    sat._safe_mode_ticks = sat._safe_mode_recovery - 1
    sat.orbit.phase_rad = 1.0  # not in eclipse or downlink
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.NOMINAL


def test_safe_mode_counter_resets_on_recovery():
    sat = _make_satellite()
    sat.state = SatelliteState.SAFE_MODE
    sat._safe_mode_ticks = sat._safe_mode_recovery - 1
    sat.orbit.phase_rad = 1.0
    sat.tick(dt=0.01)
    assert sat._safe_mode_ticks == 0


def test_stays_in_safe_mode_before_recovery():
    sat = _make_satellite()
    sat.state = SatelliteState.SAFE_MODE
    sat._safe_mode_ticks = 0
    sat.tick(dt=0.01)
    assert sat.state == SatelliteState.SAFE_MODE


def test_telemetry_state_matches_satellite_state():
    sat = _make_satellite()
    sat.orbit.phase_rad = math.pi  # eclipse
    msg = sat.tick(dt=0.01)
    assert msg.state == SatelliteState.ECLIPSE
