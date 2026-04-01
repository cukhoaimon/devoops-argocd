import logging
import os
import time

from app.orbit import Orbit
from app.producer import KafkaProducer
from app.satellite import Satellite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    satellite_id = os.environ.get("SATELLITE_ID", "SAT-001")
    satellite_name = os.environ.get("SATELLITE_NAME", "Explorer-1")
    altitude_km = float(os.environ.get("ORBIT_ALTITUDE_KM", "550"))
    inclination_deg = float(os.environ.get("ORBIT_INCLINATION_DEG", "53"))
    period_s = float(os.environ.get("ORBIT_PERIOD_S", "5760"))
    tick_interval_s = float(os.environ.get("TICK_INTERVAL_S", "1"))
    anomaly_probability = float(os.environ.get("ANOMALY_PROBABILITY", "0.005"))
    kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    kafka_topic = os.environ.get("KAFKA_TOPIC", "satellite-telemetry")

    satellite = Satellite(
        id=satellite_id,
        name=satellite_name,
        orbit=Orbit(
            altitude_km=altitude_km,
            inclination_deg=inclination_deg,
            period_s=period_s,
        ),
        anomaly_probability=anomaly_probability,
    )
    producer = KafkaProducer(bootstrap_servers=kafka_bootstrap, topic=kafka_topic)
    logger.info("Satellite simulator started: %s (%s)", satellite_name, satellite_id)

    try:
        while True:
            telemetry = satellite.tick(dt=tick_interval_s)
            producer.send(key=satellite_id, value=telemetry.to_json())
            logger.info(
                "state=%-13s phase=%.2f lat=%6.2f lon=%7.2f bat=%.1fV",
                satellite.state.value,
                satellite.orbit.phase_rad,
                telemetry.orbital.latitude_deg,
                telemetry.orbital.longitude_deg,
                satellite.power.battery_v,
            )
            time.sleep(tick_interval_s)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
