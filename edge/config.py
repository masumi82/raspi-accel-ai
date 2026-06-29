import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    device_id: str
    endpoint: str
    cert_path: str
    key_path: str
    ca_path: str
    sample_rate_hz: int
    window_ms: int
    sensor_mode: str
    buffer_path: str
    buffer_max_entries: int

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(
            device_id=env.get("DEVICE_ID", "raspi-01"),
            endpoint=env.get("IOT_ENDPOINT", ""),
            cert_path=env.get("CERT_PATH", "certs/device.cert.pem"),
            key_path=env.get("KEY_PATH", "certs/device.private.key"),
            ca_path=env.get("CA_PATH", "certs/AmazonRootCA1.pem"),
            sample_rate_hz=int(env.get("SAMPLE_RATE_HZ", "50")),
            window_ms=int(env.get("WINDOW_MS", "1000")),
            sensor_mode=env.get("SENSOR_MODE", "rest"),
            buffer_path=env.get("BUFFER_PATH", "buffer.jsonl"),
            buffer_max_entries=int(env.get("BUFFER_MAX_ENTRIES", "5000")),
        )
