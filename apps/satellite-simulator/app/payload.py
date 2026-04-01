import base64
import struct
from dataclasses import dataclass
from datetime import datetime, timezone

J2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

APID_HK = 0x64   # 100 — housekeeping (every active tick)
APID_EO = 0x65   # 101 — earth observation (on image capture)
APID_SCI = 0x66  # 102 — science instrument (periodic)


@dataclass
class CCSDSPacket:
    apid: int
    sequence_count: int  # 14-bit, 0–16383
    timestamp: datetime
    user_data: bytes = b""

    def to_bytes(self) -> bytes:
        delta = self.timestamp.astimezone(timezone.utc) - J2000
        cds_day = delta.days
        cds_ms = delta.seconds * 1000 + delta.microseconds // 1000
        secondary_header = struct.pack(">HI", cds_day, cds_ms)  # 6 bytes

        data_field = secondary_header + self.user_data
        data_length = len(data_field) - 1  # per CCSDS spec: value = length - 1

        # word1: version=0(3b) | type=TM(1b) | sec_hdr=1(1b) | apid(11b)
        word1 = (1 << 11) | (self.apid & 0x7FF)
        # word2: seq_flags=STANDALONE(2b) | seq_count(14b)
        word2 = (0b11 << 14) | (self.sequence_count & 0x3FFF)
        primary_header = struct.pack(">HHH", word1, word2, data_length)
        return primary_header + data_field

    def to_dict(self) -> dict:
        delta = self.timestamp.astimezone(timezone.utc) - J2000
        return {
            "apid": self.apid,
            "sequence_count": self.sequence_count,
            "packet_type": "TM",
            "cds_day": delta.days,
            "cds_ms": delta.seconds * 1000 + delta.microseconds // 1000,
            "raw_b64": base64.b64encode(self.to_bytes()).decode(),
        }
