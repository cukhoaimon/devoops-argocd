"""
Runtime configuration loaded from environment variables.

Each variable has a sensible default matching the cluster values
defined in spark/values.yaml and satellite-simulator/values.yaml,
so the job works out-of-the-box when deployed with the existing Helm charts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamConfig:
    # Kafka
    kafka_bootstrap: str
    kafka_topic: str
    kafka_starting_offsets: str  # "latest" | "earliest" | json offset map

    # Iceberg / MinIO
    iceberg_catalog_uri: str
    iceberg_warehouse: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    aws_region: str

    # Streaming tuning
    checkpoint_location: str
    trigger_interval_seconds: int  # micro-batch interval

    # Spark
    spark_master: str
    app_name: str

    @classmethod
    def from_env(cls) -> StreamConfig:
        return cls(
            kafka_bootstrap=os.environ.get(
                "KAFKA_BOOTSTRAP",
                "my-cluster-kafka-bootstrap.kafka:9092",
            ),
            kafka_topic=os.environ.get("KAFKA_TOPIC", "satellite-telemetry"),
            kafka_starting_offsets=os.environ.get("KAFKA_STARTING_OFFSETS", "latest"),
            iceberg_catalog_uri=os.environ.get(
                "ICEBERG_CATALOG_URI",
                "http://iceberg-rest-catalog.data-warehouse.svc.cluster.local:8181",
            ),
            iceberg_warehouse=os.environ.get("ICEBERG_WAREHOUSE", "s3://warehouse/"),
            minio_endpoint=os.environ.get(
                "MINIO_ENDPOINT",
                "http://primary-object-store.data-warehouse.svc.cluster.local:9000",
            ),
            minio_access_key=os.environ.get("MINIO_ACCESS_KEY", "minio"),
            minio_secret_key=os.environ.get("MINIO_SECRET_KEY", "minio123"),
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            checkpoint_location=os.environ.get(
                "CHECKPOINT_LOCATION",
                "s3a://warehouse/checkpoints/satellite-telemetry/",
            ),
            trigger_interval_seconds=int(
                os.environ.get("TRIGGER_INTERVAL_SECONDS", "30")
            ),
            spark_master=os.environ.get("SPARK_MASTER", "local[*]"),
            app_name=os.environ.get("APP_NAME", "satellite-telemetry-stream"),
        )
