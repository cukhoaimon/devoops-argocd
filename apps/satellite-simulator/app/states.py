from enum import Enum


class SatelliteState(Enum):
    NOMINAL = "NOMINAL"
    ECLIPSE = "ECLIPSE"
    SAFE_MODE = "SAFE_MODE"
    DOWNLINK_PASS = "DOWNLINK_PASS"
