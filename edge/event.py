from datetime import timezone

ALLOWED_HINTS = {
    "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
}


def to_iso_z(dt):
    return (
        dt.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_event(device_id, ts_iso, event_hint, features, samples=None):
    hint = event_hint if event_hint in ALLOWED_HINTS else "unknown"
    event = {
        "device_id": device_id,
        "ts": ts_iso,
        "event_hint": hint,
        "features": features,
    }
    if samples is not None:
        event["samples"] = samples
    return event


def topic_for(device_id):
    return f"devices/{device_id}/events"
