from unittest.mock import MagicMock, patch
from app.producer import KafkaProducer


@patch("app.producer.KafkaProducer._build_producer")
def test_send_calls_underlying_producer(mock_build):
    mock_kafka = MagicMock()
    mock_future = MagicMock()
    mock_kafka.send.return_value = mock_future
    mock_build.return_value = mock_kafka

    producer = KafkaProducer(bootstrap_servers="localhost:9092", topic="test-topic")
    producer.send(key="SAT-001", value='{"state": "NOMINAL"}')

    mock_kafka.send.assert_called_once_with(
        "test-topic",
        key="SAT-001",
        value='{"state": "NOMINAL"}',
    )
    mock_future.get.assert_called_once_with(timeout=10)


@patch("app.producer.KafkaProducer._build_producer")
def test_close_calls_underlying_producer(mock_build):
    mock_kafka = MagicMock()
    mock_build.return_value = mock_kafka

    producer = KafkaProducer(bootstrap_servers="localhost:9092", topic="test-topic")
    producer.close()

    mock_kafka.close.assert_called_once()
