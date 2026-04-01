import logging
from kafka import KafkaProducer as _KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaProducer:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._topic = topic
        self._producer = self._build_producer(bootstrap_servers)

    def _build_producer(self, bootstrap_servers: str) -> _KafkaProducer:
        return _KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
        )

    def send(self, key: str, value: str) -> None:
        future = self._producer.send(self._topic, key=key, value=value)
        try:
            future.get(timeout=10)
        except KafkaError as exc:
            logger.error("Failed to produce message: %s", exc)

    def close(self) -> None:
        self._producer.close()
