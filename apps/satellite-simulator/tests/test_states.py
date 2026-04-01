from app.states import SatelliteState


def test_all_states_exist():
    assert SatelliteState.NOMINAL
    assert SatelliteState.ECLIPSE
    assert SatelliteState.SAFE_MODE
    assert SatelliteState.DOWNLINK_PASS


def test_states_have_string_values():
    assert SatelliteState.NOMINAL.value == "NOMINAL"
    assert SatelliteState.ECLIPSE.value == "ECLIPSE"
    assert SatelliteState.SAFE_MODE.value == "SAFE_MODE"
    assert SatelliteState.DOWNLINK_PASS.value == "DOWNLINK_PASS"
