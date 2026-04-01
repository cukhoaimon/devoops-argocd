import base64
import random
import struct
from dataclasses import dataclass
from datetime import datetime, timezone

from app.states import SatelliteState

J2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

APID_HK = 0x64   # 100 — housekeeping (every active tick)
APID_EO = 0x65   # 101 — earth observation (on image capture)
APID_SCI = 0x66  # 102 — science instrument (periodic)

_OBSERVATION_TARGETS = [
    "Amazon Basin", "Sahara Desert", "Himalayan Range",
    "Pacific Ocean", "Arctic Ice Sheet", "Mediterranean Sea",
    "Congo Rainforest", "Australian Outback",
]


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


@dataclass
class PayloadData:
    packets: list[dict]


class Payload:
    def __init__(self) -> None:
        self._image_count: int = 0
        self._seq_counters: dict[int, int] = {APID_HK: 0, APID_EO: 0, APID_SCI: 0}
        self._sci_tick: int = 0

    def _next_seq(self, apid: int) -> int:
        count = self._seq_counters[apid]
        self._seq_counters[apid] = (count + 1) & 0x3FFF  # 14-bit wrap
        return count

    def update(self, state: SatelliteState, now: datetime) -> PayloadData:
        if state in (SatelliteState.SAFE_MODE, SatelliteState.ECLIPSE):
            return PayloadData(packets=[])

        packets: list[dict] = []

        # HK packet every active tick
        packets.append(CCSDSPacket(
            apid=APID_HK,
            sequence_count=self._next_seq(APID_HK),
            timestamp=now,
            user_data=struct.pack(">H", self._image_count),
        ).to_dict())

        if state == SatelliteState.NOMINAL:
            # Random EO capture (~10% chance per tick)
            if random.random() < 0.1:
                target = random.choice(_OBSERVATION_TARGETS)
                self._image_count += 1
                packets.append(CCSDSPacket(
                    apid=APID_EO,
                    sequence_count=self._next_seq(APID_EO),
                    timestamp=now,
                    user_data=target.encode("utf-8"),
                ).to_dict())

            # Science reading every 10 ticks
            self._sci_tick += 1
            if self._sci_tick >= 10:
                self._sci_tick = 0
                packets.append(CCSDSPacket(
                    apid=APID_SCI,
                    sequence_count=self._next_seq(APID_SCI),
                    timestamp=now,
                    user_data=struct.pack(">f", random.uniform(0.1, 100.0)),
                ).to_dict())

        elif state == SatelliteState.DOWNLINK_PASS:
            # Flush buffered image count
            packets.append(CCSDSPacket(
                apid=APID_EO,
                sequence_count=self._next_seq(APID_EO),
                timestamp=now,
                user_data=f"DOWNLINK:{self._image_count}".encode("utf-8"),
            ).to_dict())

        return PayloadData(packets=packets)
