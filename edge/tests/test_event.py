from datetime import datetime, timezone

from edge.event import build_event, to_iso_z, topic_for, ALLOWED_HINTS


def test_to_iso_z_format():
    dt = datetime(2026, 6, 29, 12, 34, 56, 789000, tzinfo=timezone.utc)
    assert to_iso_z(dt) == "2026-06-29T12:34:56.789Z"


def test_build_event_contract():
    ev = build_event("raspi-01", "2026-06-29T12:34:56.789Z", "impact", {"mag_peak": 4.0})
    assert ev == {
        "device_id": "raspi-01",
        "ts": "2026-06-29T12:34:56.789Z",
        "event_hint": "impact",
        "features": {"mag_peak": 4.0},
    }


def test_build_event_unknown_hint_normalized():
    ev = build_event("d", "t", "explosion", {})
    assert ev["event_hint"] == "unknown"


def test_build_event_includes_samples_when_given():
    ev = build_event("d", "t", "impact", {}, samples=[[0, 0, 1]])
    assert ev["samples"] == [[0, 0, 1]]


def test_allowed_hints_match_cloud_contract():
    assert ALLOWED_HINTS == {
        "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
    }


def test_topic_for():
    assert topic_for("raspi-01") == "devices/raspi-01/events"
