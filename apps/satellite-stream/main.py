"""
Satellite Telemetry Stream — entry point.

Submits the Spark Structured Streaming job that consumes
the 'satellite-telemetry' Kafka topic and writes to the
Iceberg bronze layer: bronze.satellite_telemetry.

Usage (local test):
    SPARK_MASTER=local[*] python main.py

Usage (spark-submit inside K8s pod):
    spark-submit --master local[*] main.py

All runtime settings are controlled via environment variables.
See stream/config.py for the full list and defaults.
"""
import logging

from stream.config import StreamConfig
from stream.job import run_streaming_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = StreamConfig.from_env()
    logger.info(
        "Starting satellite telemetry stream | kafka=%s topic=%s → iceberg=%s",
        cfg.kafka_bootstrap,
        cfg.kafka_topic,
        cfg.checkpoint_location,
    )
    run_streaming_job(cfg)


if __name__ == "__main__":
    main()
