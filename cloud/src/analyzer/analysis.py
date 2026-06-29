import json
from dataclasses import dataclass

ALLOWED_LABELS = {"normal", "vibration", "tilt", "impact", "freefall", "transport"}
ALLOWED_SEVERITY = {"low", "medium", "high"}


@dataclass
class Analysis:
    label: str
    severity: str
    explanation: str


class AnalysisParseError(ValueError):
    pass


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AnalysisParseError("no JSON object found in model output")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AnalysisParseError(f"invalid JSON: {exc}") from exc


def parse_analysis(text: str) -> Analysis:
    data = _extract_json(text)
    label = data.get("label")
    severity = data.get("severity")
    explanation = data.get("explanation")
    if label not in ALLOWED_LABELS:
        raise AnalysisParseError(f"invalid label: {label!r}")
    if severity not in ALLOWED_SEVERITY:
        raise AnalysisParseError(f"invalid severity: {severity!r}")
    if not isinstance(explanation, str) or not explanation.strip():
        raise AnalysisParseError("explanation must be a non-empty string")
    return Analysis(label=label, severity=severity, explanation=explanation.strip())
