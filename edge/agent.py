import time
from datetime import datetime, timezone

from .buffer import OfflineBuffer
from .detector import EventDetector, compute_features
from .event import build_event, to_iso_z, topic_for
from .mqtt_client import AwsIotPublisher
from .sensor import ADXL345Sensor, SimulatedSensor


class Agent:
    def __init__(self, sensor, detector, publisher, buffer, config, *, connected=True):
        self.sensor = sensor
        self.detector = detector
        self.publisher = publisher
        self.buffer = buffer
        self.config = config
        self.connected = connected
        self._period_ms = 1000.0 / config.sample_rate_hz

    def process_window(self, samples, now, dt):
        features = compute_features(samples, self._period_ms)
        hint = self.detector.detect(features, now)
        if hint is None:
            return None
        event = build_event(self.config.device_id, to_iso_z(dt), hint, features)
        topic = topic_for(self.config.device_id)
        try:
            if not self.connected:
                raise ConnectionError("offline")
            self.publisher.publish(topic, event)
        except Exception:
            self.buffer.add(event)
        return event

    def run(self):  # pragma: no cover - real-time loop, validated on device
        window_n = max(1, int(self.config.sample_rate_hz * self.config.window_ms / 1000))
        self.publisher.connect()
        self.connected = True
        try:
            while True:
                samples = [self.sensor.read() for _ in range(window_n)]
                now = time.monotonic()
                self.buffer.flush(lambda ev: self.publisher.publish(topic_for(self.config.device_id), ev))
                self.process_window(samples, now, datetime.now(timezone.utc))
        finally:
            self.publisher.disconnect()


def build_agent(config):
    if config.sensor_mode == "adxl345":
        sensor = ADXL345Sensor()
    else:
        sensor = SimulatedSensor(mode=config.sensor_mode)
    detector = EventDetector()
    publisher = AwsIotPublisher(
        endpoint=config.endpoint,
        cert_path=config.cert_path,
        key_path=config.key_path,
        ca_path=config.ca_path,
        client_id=config.device_id,
    )
    buffer = OfflineBuffer(config.buffer_path, max_entries=config.buffer_max_entries)
    return Agent(sensor, detector, publisher, buffer, config, connected=False)
