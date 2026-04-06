"""
Spark schema definitions for the satellite telemetry Kafka messages.

The JSON schema mirrors the TelemetryMessage.to_json() output produced by
apps/satellite-simulator/app/telemetry.py.

Key difference from the Iceberg table schema:
  Kafka JSON  →  raw_b64  (base64-encoded string)
  Iceberg     →  raw_data (BINARY / bytes)
The transform step decodes base64 before writing.
"""
from pyspark.sql.types import (
    ArrayType,
    BinaryType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ── Sub-structs ───────────────────────────────────────────────────────────────

ORBITAL_SCHEMA = StructType([
    StructField("altitude_km", DoubleType(), nullable=True),
    StructField("latitude_deg", DoubleType(), nullable=True),
    StructField("longitude_deg", DoubleType(), nullable=True),
    StructField("velocity_km_s", DoubleType(), nullable=True),
    StructField("phase_rad", DoubleType(), nullable=True),
])

POWER_SCHEMA = StructType([
    StructField("battery_v", DoubleType(), nullable=True),
    StructField("solar_w", DoubleType(), nullable=True),
    StructField("consumption_w", DoubleType(), nullable=True),
])

THERMAL_SCHEMA = StructType([
    StructField("cpu_temp_c", DoubleType(), nullable=True),
    StructField("battery_temp_c", DoubleType(), nullable=True),
    StructField("structure_temp_c", DoubleType(), nullable=True),
])

# Note: field is "raw_b64" (string) in Kafka JSON; transform.py converts it
# to "raw_data" (binary) before writing to Iceberg.
PAYLOAD_PACKET_KAFKA_SCHEMA = StructType([
    StructField("apid", IntegerType(), nullable=True),
    StructField("sequence_count", IntegerType(), nullable=True),
    StructField("packet_type", StringType(), nullable=True),
    StructField("cds_day", IntegerType(), nullable=True),
    StructField("cds_ms", IntegerType(), nullable=True),
    StructField("raw_b64", StringType(), nullable=True),  # decoded in transform
])

# Iceberg table column type for payload_packets after decoding
PAYLOAD_PACKET_ICEBERG_SCHEMA = StructType([
    StructField("apid", IntegerType(), nullable=True),
    StructField("sequence_count", IntegerType(), nullable=True),
    StructField("packet_type", StringType(), nullable=True),
    StructField("cds_day", IntegerType(), nullable=True),
    StructField("cds_ms", IntegerType(), nullable=True),
    StructField("raw_data", BinaryType(), nullable=True),
])

# ── Top-level Kafka message schema ────────────────────────────────────────────

# timestamp_utc is parsed as StringType first; it's cast to TimestampType
# in the transform step because Spark's from_json cannot natively parse
# ISO-8601 strings with timezone offsets (e.g. "+00:00") directly.
TELEMETRY_KAFKA_SCHEMA = StructType([
    StructField("satellite_id", StringType(), nullable=True),
    StructField("satellite_name", StringType(), nullable=True),
    StructField("timestamp_utc", StringType(), nullable=True),
    StructField("state", StringType(), nullable=True),
    StructField("orbital", ORBITAL_SCHEMA, nullable=True),
    StructField("power", POWER_SCHEMA, nullable=True),
    StructField("thermal", THERMAL_SCHEMA, nullable=True),
    StructField("payload_packets", ArrayType(PAYLOAD_PACKET_KAFKA_SCHEMA), nullable=True),
])
