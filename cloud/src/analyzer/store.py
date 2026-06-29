import json
from decimal import Decimal

from .analysis import Analysis
from .validate import ParsedEvent


def _to_decimal(features: dict) -> dict:
    # float を Decimal へ変換（DynamoDB resource は float を受け付けない）
    return json.loads(json.dumps(features), parse_float=Decimal)


def build_item(
    event: ParsedEvent, analysis: Analysis, model_id: str, now_iso: str
) -> dict:
    return {
        "deviceId": event.device_id,
        "ts": event.ts,
        "event_hint": event.event_hint,
        "features": _to_decimal(event.features),
        "label": analysis.label,
        "severity": analysis.severity,
        "explanation": analysis.explanation,
        "model_id": model_id,
        "created_at": now_iso,
    }


def save_item(table, item: dict) -> None:
    table.put_item(Item=item)
