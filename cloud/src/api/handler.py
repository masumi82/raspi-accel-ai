import json
import os

import boto3

from .query import query_events, to_jsonable

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["EVENTS_TABLE"])
    return _table


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    if http.get("method") != "GET":
        return _response(405, {"error": "method not allowed"})
    qs = event.get("queryStringParameters") or {}
    device_id = qs.get("deviceId", "raspi-01")
    try:
        limit = int(qs.get("limit", "50"))
    except (TypeError, ValueError):
        return _response(400, {"error": "limit must be an integer"})
    limit = max(1, min(limit, 200))
    try:
        items = query_events(_get_table(), device_id, limit)
    except Exception:
        return _response(500, {"error": "internal error"})
    return _response(
        200,
        {"deviceId": device_id, "count": len(items), "events": to_jsonable(items)},
    )
