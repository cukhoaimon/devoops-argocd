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
