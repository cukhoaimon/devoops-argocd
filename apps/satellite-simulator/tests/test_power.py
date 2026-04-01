from app.power import PowerSystem, PowerData
from app.states import SatelliteState


def test_update_returns_power_data():
    ps = PowerSystem()
    data = ps.update(SatelliteState.NOMINAL, dt=1.0)
    assert isinstance(data, PowerData)


def test_solar_output_zero_in_eclipse():
    ps = PowerSystem()
    data = ps.update(SatelliteState.ECLIPSE, dt=1.0)
    assert data.solar_w == 0.0


def test_battery_drains_in_eclipse():
    ps = PowerSystem(battery_v=28.0)
    ps.update(SatelliteState.ECLIPSE, dt=1.0)
    assert ps.battery_v < 28.0


def test_battery_does_not_go_below_minimum():
    ps = PowerSystem(battery_v=22.0)
    for _ in range(10000):
        ps.update(SatelliteState.ECLIPSE, dt=1.0)
    assert ps.battery_v >= 22.0


def test_low_consumption_in_safe_mode():
    ps = PowerSystem()
    data = ps.update(SatelliteState.SAFE_MODE, dt=1.0)
    assert data.consumption_w < 50.0


def test_higher_consumption_in_downlink_vs_nominal():
    ps_nominal = PowerSystem()
    ps_downlink = PowerSystem()
    nominal_data = ps_nominal.update(SatelliteState.NOMINAL, dt=1.0)
    downlink_data = ps_downlink.update(SatelliteState.DOWNLINK_PASS, dt=1.0)
    assert downlink_data.consumption_w > nominal_data.consumption_w
