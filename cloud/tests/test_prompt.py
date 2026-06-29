import json
from analyzer.validate import ParsedEvent
from analyzer.prompt import SYSTEM_PROMPT, build_user_message


def _event():
    return ParsedEvent(
        device_id="raspi-01",
        ts="2026-06-29T12:34:56.789Z",
        event_hint="impact",
        features={"mag_peak": 3.21},
    )


def test_system_prompt_is_nonempty():
    assert isinstance(SYSTEM_PROMPT, str) and SYSTEM_PROMPT.strip()


def test_build_user_message_contains_features_json():
    msg = build_user_message(_event())
    assert "mag_peak" in msg
    assert "impact" in msg
    # JSON 部分が含まれ、パース可能であること
    assert json.dumps({"mag_peak": 3.21}, ensure_ascii=False) in msg


def test_build_user_message_requests_json_schema():
    msg = build_user_message(_event())
    assert "label" in msg and "severity" in msg and "explanation" in msg
