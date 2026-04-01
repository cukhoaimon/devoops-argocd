import base64
import struct
from datetime import datetime, timezone
from app.payload import CCSDSPacket, APID_HK, APID_EO, APID_SCI


def _now() -> datetime:
    return datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_packet_length_no_user_data():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=_now())
    data = pkt.to_bytes()
    # 6 bytes primary header + 6 bytes CDS secondary header + 0 user data
    assert len(data) == 12


def test_packet_length_with_user_data():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=_now(), user_data=b"\x00\x01")
    data = pkt.to_bytes()
    assert len(data) == 14


def test_apid_encoded_in_primary_header():
    pkt = CCSDSPacket(apid=APID_EO, sequence_count=0, timestamp=_now())
    data = pkt.to_bytes()
    word1 = struct.unpack(">H", data[0:2])[0]
    assert word1 & 0x7FF == APID_EO


def test_sequence_count_encoded_in_primary_header():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=42, timestamp=_now())
    data = pkt.to_bytes()
    word2 = struct.unpack(">H", data[2:4])[0]
    assert word2 & 0x3FFF == 42


def test_sequence_flags_are_standalone():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=_now())
    data = pkt.to_bytes()
    word2 = struct.unpack(">H", data[2:4])[0]
    assert (word2 >> 14) & 0x3 == 0b11


def test_secondary_header_flag_set():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=_now())
    data = pkt.to_bytes()
    word1 = struct.unpack(">H", data[0:2])[0]
    assert (word1 >> 11) & 0x1 == 1


def test_to_dict_contains_required_fields():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=10, timestamp=_now())
    d = pkt.to_dict()
    assert d["apid"] == APID_HK
    assert d["sequence_count"] == 10
    assert d["packet_type"] == "TM"
    assert "cds_day" in d
    assert "cds_ms" in d
    assert "raw_b64" in d


def test_raw_b64_decodes_to_same_bytes():
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=_now())
    d = pkt.to_dict()
    assert base64.b64decode(d["raw_b64"]) == pkt.to_bytes()


def test_cds_day_matches_j2000_offset():
    # 2000-01-01T12:00:00Z is J2000 epoch → day 0
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pkt = CCSDSPacket(apid=APID_HK, sequence_count=0, timestamp=j2000)
    d = pkt.to_dict()
    assert d["cds_day"] == 0
    assert d["cds_ms"] == 0


from app.payload import Payload, PayloadData
from app.states import SatelliteState


def test_payload_returns_payload_data():
    pl = Payload()
    data = pl.update(SatelliteState.NOMINAL, _now())
    assert isinstance(data, PayloadData)


def test_no_packets_in_eclipse():
    pl = Payload()
    data = pl.update(SatelliteState.ECLIPSE, _now())
    assert data.packets == []


def test_no_packets_in_safe_mode():
    pl = Payload()
    data = pl.update(SatelliteState.SAFE_MODE, _now())
    assert data.packets == []


def test_hk_packet_emitted_every_nominal_tick():
    pl = Payload()
    data = pl.update(SatelliteState.NOMINAL, _now())
    apids = [p["apid"] for p in data.packets]
    assert APID_HK in apids


def test_hk_packet_emitted_in_downlink():
    pl = Payload()
    data = pl.update(SatelliteState.DOWNLINK_PASS, _now())
    apids = [p["apid"] for p in data.packets]
    assert APID_HK in apids


def test_hk_sequence_counter_increments_per_tick():
    pl = Payload()
    now = _now()
    d1 = pl.update(SatelliteState.NOMINAL, now)
    d2 = pl.update(SatelliteState.NOMINAL, now)
    hk1 = next(p for p in d1.packets if p["apid"] == APID_HK)
    hk2 = next(p for p in d2.packets if p["apid"] == APID_HK)
    assert hk2["sequence_count"] == hk1["sequence_count"] + 1


def test_sequence_counter_wraps_at_14_bits():
    pl = Payload()
    pl._seq_counters[APID_HK] = 16383
    now = _now()
    pl.update(SatelliteState.NOMINAL, now)
    d = pl.update(SatelliteState.NOMINAL, now)
    hk = next(p for p in d.packets if p["apid"] == APID_HK)
    assert hk["sequence_count"] == 0


def test_science_packet_emitted_every_10_ticks():
    pl = Payload()
    now = _now()
    sci_packets = []
    for _ in range(10):
        data = pl.update(SatelliteState.NOMINAL, now)
        sci_packets.extend(p for p in data.packets if p["apid"] == APID_SCI)
    assert len(sci_packets) == 1


def test_eo_packet_emitted_in_downlink_pass():
    pl = Payload()
    data = pl.update(SatelliteState.DOWNLINK_PASS, _now())
    apids = [p["apid"] for p in data.packets]
    assert APID_EO in apids
