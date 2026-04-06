"""
DataFrame transformations from raw Kafka value → Iceberg-ready schema.

Pipeline:
  1. Parse JSON bytes to structured columns using TELEMETRY_KAFKA_SCHEMA.
  2. Cast timestamp_utc string (ISO-8601 + TZ offset) to TimestampType.
  3. Decode raw_b64 (base64 string) → raw_data (BINARY) inside the
     payload_packets array using F.transform + F.unbase64.
  4. Drop the intermediate parsed column and return a flat DataFrame
     whose schema exactly matches bronze.satellite_telemetry.
"""
from __future__ import annotations

import logging

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from stream.schema import TELEMETRY_KAFKA_SCHEMA

logger = logging.getLogger(__name__)


def parse_kafka_value(raw_df: DataFrame) -> DataFrame:
    """
    Decode the Kafka 'value' bytes as UTF-8 JSON and expand into columns.

    Returns a DataFrame with one column per top-level JSON field.
    Malformed messages produce null values (permissive mode) so the stream
    never halts on a single bad record.
    """
    return raw_df.select(
        F.from_json(
            F.col("value").cast("string"),
            TELEMETRY_KAFKA_SCHEMA,
            # PERMISSIVE: bad records become nulls rather than crashing
            options={"mode": "PERMISSIVE"},
        ).alias("msg"),
        # Preserve Kafka metadata for debugging / DLQ use
        F.col("topic"),
        F.col("partition"),
        F.col("offset"),
        F.col("timestamp").alias("kafka_timestamp"),
    ).select("msg.*", "topic", "partition", "offset", "kafka_timestamp")


def decode_payload_packets(df: DataFrame) -> DataFrame:
    """
    Within the payload_packets array, rename raw_b64 → raw_data
    and decode the base64 string to binary bytes.

    When payload_packets is NULL or empty (ECLIPSE / SAFE_MODE states),
    the transform returns the column unchanged (F.transform on null → null,
    on empty array → empty array).
    """
    return df.withColumn(
        "payload_packets",
        F.transform(
            F.col("payload_packets"),
            lambda pkt: F.struct(
                pkt["apid"].alias("apid"),
                pkt["sequence_count"].alias("sequence_count"),
                pkt["packet_type"].alias("packet_type"),
                pkt["cds_day"].alias("cds_day"),
                pkt["cds_ms"].alias("cds_ms"),
                F.unbase64(pkt["raw_b64"]).alias("raw_data"),
            ),
        ),
    )


def cast_timestamp(df: DataFrame) -> DataFrame:
    """
    Convert ISO-8601 timestamp string with TZ offset to TimestampType.

    The simulator emits e.g. "2026-04-06T07:58:22.761949+00:00".
    With session.timeZone=UTC, Spark's to_timestamp handles this correctly.
    """
    return df.withColumn(
        "timestamp_utc",
        F.to_timestamp(F.col("timestamp_utc")),
    )


def drop_kafka_metadata(df: DataFrame) -> DataFrame:
    """Remove the Kafka routing columns before writing to Iceberg."""
    return df.drop("topic", "partition", "offset", "kafka_timestamp")


def filter_valid_records(df: DataFrame) -> DataFrame:
    """
    Drop rows where mandatory fields are null (e.g. JSON parse failures).
    This prevents NULL partition values in Iceberg (days(timestamp_utc)).
    """
    return df.filter(
        F.col("satellite_id").isNotNull()
        & F.col("timestamp_utc").isNotNull()
    )


def transform_telemetry(raw_df: DataFrame) -> DataFrame:
    """
    Full transformation pipeline: raw Kafka DataFrame → Iceberg-ready DataFrame.

    Stages:
      parse → cast_timestamp → decode_payload_packets → filter → drop_metadata
    """
    return (
        raw_df
        .transform(parse_kafka_value)
        .transform(cast_timestamp)
        .transform(decode_payload_packets)
        .transform(filter_valid_records)
        .transform(drop_kafka_metadata)
    )
