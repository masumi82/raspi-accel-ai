from dataclasses import dataclass

ALLOWED_HINTS = {
    "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
}


@dataclass
class ParsedEvent:
    device_id: str
    ts: str
    event_hint: str
    features: dict
    samples: list | None = None


class InvalidEvent(ValueError):
    pass


def validate_event(raw: dict) -> ParsedEvent:
    if not isinstance(raw, dict):
        raise InvalidEvent("event must be an object")
    device_id = raw.get("device_id")
    ts = raw.get("ts")
    features = raw.get("features")
    if not isinstance(device_id, str) or not device_id:
        raise InvalidEvent("device_id is required")
    if not isinstance(ts, str) or not ts:
        raise InvalidEvent("ts is required")
    if not isinstance(features, dict):
        raise InvalidEvent("features must be an object")
    event_hint = raw.get("event_hint", "unknown")
    if event_hint not in ALLOWED_HINTS:
        event_hint = "unknown"
    samples = raw.get("samples")
    if samples is not None and not isinstance(samples, list):
        raise InvalidEvent("samples must be a list when present")
    return ParsedEvent(
        device_id=device_id,
        ts=ts,
        event_hint=event_hint,
        features=features,
        samples=samples,
    )
