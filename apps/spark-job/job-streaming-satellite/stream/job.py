"""
Spark Structured Streaming job: Kafka → Iceberg bronze.satellite_telemetry.

SparkSession is built entirely from code so the job is self-contained and
does not rely on a spark-defaults.conf being mounted at runtime.
All tunables are injected via StreamConfig (env vars).
"""
from __future__ import annotations

import logging

from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery

from stream.config import StreamConfig
from stream.transform import transform_telemetry

logger = logging.getLogger(__name__)

_TARGET_TABLE = "iceberg.bronze.satellite_telemetry"


def build_spark_session(cfg: StreamConfig) -> SparkSession:
    """
    Construct a SparkSession with:
      - Iceberg REST catalog wired to MinIO
      - S3A filesystem for checkpoint storage
      - UTC session timezone (needed for ISO-8601 TZ-aware timestamp casting)
    """
    builder = (
        SparkSession.builder
        .master(cfg.spark_master)
        .appName(cfg.app_name)
        # ── Iceberg extensions ────────────────────────────────────────
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        # ── Iceberg REST catalog ──────────────────────────────────────
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "rest")
        .config("spark.sql.catalog.iceberg.uri", cfg.iceberg_catalog_uri)
        .config("spark.sql.catalog.iceberg.warehouse", cfg.iceberg_warehouse)
        # FileIO: write data files via S3FileIO → MinIO
        .config(
            "spark.sql.catalog.iceberg.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO",
        )
        .config("spark.sql.catalog.iceberg.s3.endpoint", cfg.minio_endpoint)
        .config("spark.sql.catalog.iceberg.s3.path-style-access", "true")
        .config("spark.sql.catalog.iceberg.s3.access-key-id", cfg.minio_access_key)
        .config(
            "spark.sql.catalog.iceberg.s3.secret-access-key", cfg.minio_secret_key
        )
        .config("spark.sql.catalog.iceberg.s3.region", cfg.aws_region)
        .config("spark.sql.defaultCatalog", "iceberg")
        # ── S3A filesystem (checkpoint + scratch) ─────────────────────
        .config("spark.hadoop.fs.s3a.endpoint", cfg.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", cfg.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", cfg.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        # ── Timestamp handling ────────────────────────────────────────
        .config("spark.sql.session.timeZone", "UTC")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    logger.info("SparkSession created: %s", spark.version)
    return spark


def read_kafka_stream(spark: SparkSession, cfg: StreamConfig):
    """
    Create a streaming DataFrame from the Kafka topic.

    Options:
      startingOffsets  – "latest" in prod to avoid reprocessing history;
                         set to "earliest" for backfill runs.
      failOnDataLoss   – False: tolerate Kafka log compaction / retention gaps
                         without crashing the stream.
      maxOffsetsPerTrigger – throttle ingestion rate to avoid memory spikes.
    """
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", cfg.kafka_bootstrap)
        .option("subscribe", cfg.kafka_topic)
        .option("startingOffsets", cfg.kafka_starting_offsets)
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 10_000)
        .load()
    )


def write_to_iceberg(
    transformed_df,
    cfg: StreamConfig,
) -> StreamingQuery:
    """
    Write the transformed stream to the Iceberg table.

    Uses Trigger.ProcessingTime to control micro-batch frequency.
    toTable() commits each micro-batch as an Iceberg snapshot, which is
    atomic and respects the table's partitioning (days(timestamp_utc)).
    """
    return (
        transformed_df.writeStream
        .format("iceberg")
        .outputMode("append")
        .trigger(processingTime=f"{cfg.trigger_interval_seconds} seconds")
        .option("checkpointLocation", cfg.checkpoint_location)
        .toTable(_TARGET_TABLE)
    )


def run_streaming_job(cfg: StreamConfig) -> None:
    """Entry point: wire up source → transform → sink and await termination."""
    spark = build_spark_session(cfg)

    logger.info(
        "Reading from Kafka: bootstrap=%s topic=%s offsets=%s",
        cfg.kafka_bootstrap,
        cfg.kafka_topic,
        cfg.kafka_starting_offsets,
    )
    raw_stream = read_kafka_stream(spark, cfg)
    transformed = transform_telemetry(raw_stream)

    logger.info(
        "Writing to Iceberg table: %s  checkpoint=%s",
        _TARGET_TABLE,
        cfg.checkpoint_location,
    )
    query = write_to_iceberg(transformed, cfg)

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received — stopping stream gracefully")
        query.stop()
    finally:
        spark.stop()
        logger.info("SparkSession stopped")
