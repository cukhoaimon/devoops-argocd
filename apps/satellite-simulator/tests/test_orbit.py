import math
import pytest
from app.orbit import Orbit, OrbitalData


def test_step_returns_orbital_data():
    orbit = Orbit()
    data = orbit.step(dt=1.0)
    assert isinstance(data, OrbitalData)
    assert data.altitude_km == pytest.approx(550.0)
    assert data.velocity_km_s == pytest.approx(7.59, abs=0.1)


def test_phase_advances_by_angular_velocity():
    orbit = Orbit(period_s=100.0, phase_rad=0.0)
    orbit.step(dt=25.0)
    expected = 2 * math.pi * 25.0 / 100.0
    assert orbit.phase_rad == pytest.approx(expected)


def test_phase_wraps_at_2pi():
    orbit = Orbit(period_s=100.0, phase_rad=0.0)
    orbit.step(dt=100.0)
    assert orbit.phase_rad == pytest.approx(0.0, abs=1e-9)


def test_eclipse_detected_in_shadow_arc():
    orbit = Orbit()
    orbit.phase_rad = math.pi  # midpoint of shadow arc
    assert orbit.is_eclipse() is True


def test_no_eclipse_at_phase_zero():
    orbit = Orbit()
    orbit.phase_rad = 0.0
    assert orbit.is_eclipse() is False


def test_downlink_window_near_phase_zero():
    orbit = Orbit()
    orbit.phase_rad = 0.05
    assert orbit.is_downlink_window() is True


def test_no_downlink_window_mid_orbit():
    orbit = Orbit()
    orbit.phase_rad = math.pi
    assert orbit.is_downlink_window() is False


def test_position_latitude_bounded_by_inclination():
    orbit = Orbit(inclination_deg=53.0)
    for phase in [i * 0.1 for i in range(63)]:
        orbit.phase_rad = phase
        data = orbit.step(dt=0.0)
        assert -53.0 <= data.latitude_deg <= 53.0
