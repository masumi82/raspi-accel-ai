import os
from datetime import datetime, timezone

import boto3
from botocore.config import Config

from .bedrock_client import analyze
from .store import build_item, save_item
from .validate import validate_event

_bedrock = None
_table = None


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client(
            "bedrock-runtime",
            config=Config(retries={"mode": "adaptive", "max_attempts": 5}),
        )
    return _bedrock


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["EVENTS_TABLE"])
    return _table


def handler(event, context):
    model_id = os.environ["BEDROCK_MODEL_ID"]
    parsed = validate_event(event)
    analysis = analyze(_get_bedrock(), model_id, parsed)
    now_iso = datetime.now(timezone.utc).isoformat()
    item = build_item(parsed, analysis, model_id, now_iso)
    save_item(_get_table(), item)
    return {
        "status": "ok",
        "deviceId": parsed.device_id,
        "ts": parsed.ts,
        "label": analysis.label,
    }
