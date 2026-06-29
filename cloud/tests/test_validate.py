import pytest
from analyzer.validate import validate_event, ParsedEvent, InvalidEvent


def _valid_raw():
    return {
        "device_id": "raspi-01",
        "ts": "2026-06-29T12:34:56.789Z",
        "event_hint": "impact",
        "features": {"mag_peak": 3.21, "mag_rms": 1.05, "tilt_deg": 47.2},
    }


def test_validate_event_returns_parsed_event():
    parsed = validate_event(_valid_raw())
    assert isinstance(parsed, ParsedEvent)
    assert parsed.device_id == "raspi-01"
    assert parsed.event_hint == "impact"
    assert parsed.features["mag_peak"] == 3.21
    assert parsed.samples is None


def test_validate_event_unknown_hint_becomes_unknown():
    raw = _valid_raw()
    raw["event_hint"] = "explosion"
    assert validate_event(raw).event_hint == "unknown"


def test_validate_event_missing_device_id_raises():
    raw = _valid_raw()
    del raw["device_id"]
    with pytest.raises(InvalidEvent):
        validate_event(raw)


def test_validate_event_bad_features_raises():
    raw = _valid_raw()
    raw["features"] = "not-a-dict"
    with pytest.raises(InvalidEvent):
        validate_event(raw)


def test_validate_event_bad_samples_raises():
    raw = _valid_raw()
    raw["samples"] = "not-a-list"
    with pytest.raises(InvalidEvent):
        validate_event(raw)
