from app.thermal import ThermalSystem, ThermalData
from app.states import SatelliteState


def test_update_returns_thermal_data():
    ts = ThermalSystem()
    data = ts.update(SatelliteState.NOMINAL, dt=1.0)
    assert isinstance(data, ThermalData)


def test_cpu_temp_rises_in_downlink():
    ts = ThermalSystem(cpu_temp_c=35.0)
    for _ in range(200):
        ts.update(SatelliteState.DOWNLINK_PASS, dt=1.0)
    assert ts.cpu_temp_c > 35.0


def test_cpu_temp_falls_in_eclipse():
    ts = ThermalSystem(cpu_temp_c=35.0)
    for _ in range(200):
        ts.update(SatelliteState.ECLIPSE, dt=1.0)
    assert ts.cpu_temp_c < 35.0


def test_structure_temp_drops_furthest_in_eclipse():
    ts = ThermalSystem(cpu_temp_c=35.0, battery_temp_c=20.0, structure_temp_c=0.0)
    for _ in range(500):
        ts.update(SatelliteState.ECLIPSE, dt=1.0)
    assert ts.structure_temp_c < ts.cpu_temp_c


def test_nominal_temps_stay_near_operating_range():
    ts = ThermalSystem()
    for _ in range(1000):
        ts.update(SatelliteState.NOMINAL, dt=1.0)
    assert 30.0 <= ts.cpu_temp_c <= 45.0
    assert 15.0 <= ts.battery_temp_c <= 30.0
