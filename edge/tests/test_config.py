from edge.config import AgentConfig


def test_from_env_defaults():
    cfg = AgentConfig.from_env({})
    assert cfg.device_id == "raspi-01"
    assert cfg.sample_rate_hz == 50
    assert cfg.window_ms == 1000
    assert cfg.sensor_mode == "rest"
    assert cfg.buffer_path == "buffer.jsonl"
    assert cfg.buffer_max_entries == 5000


def test_from_env_overrides_and_int_parsing():
    cfg = AgentConfig.from_env(
        {
            "DEVICE_ID": "raspi-09",
            "IOT_ENDPOINT": "abc.iot.ap-northeast-1.amazonaws.com",
            "SAMPLE_RATE_HZ": "100",
            "WINDOW_MS": "500",
            "SENSOR_MODE": "adxl345",
        }
    )
    assert cfg.device_id == "raspi-09"
    assert cfg.endpoint == "abc.iot.ap-northeast-1.amazonaws.com"
    assert cfg.sample_rate_hz == 100
    assert cfg.window_ms == 500
    assert cfg.sensor_mode == "adxl345"
