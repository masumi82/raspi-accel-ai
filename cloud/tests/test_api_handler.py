import json
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

import api.handler as handler_mod
from api.handler import handler


def _make_table():
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="events",
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "deviceId", "AttributeType": "S"},
            {"AttributeName": "ts", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "deviceId", "KeyType": "HASH"},
            {"AttributeName": "ts", "KeyType": "RANGE"},
        ],
    )
    return ddb.Table("events")


def _evt(method="GET", path="/events", qs=None):
    return {
        "version": "2.0",
        "requestContext": {"http": {"method": method, "path": path}},
        "queryStringParameters": qs,
    }


@mock_aws
def test_handler_lists_events_newest_first(monkeypatch):
    table = _make_table()
    table.put_item(Item={"deviceId": "raspi-01", "ts": "2026-06-29T12:00:00Z",
                         "label": "normal", "features": {"mag_peak": Decimal("1.0")}})
    table.put_item(Item={"deviceId": "raspi-01", "ts": "2026-06-29T12:05:00Z",
                         "label": "impact", "features": {"mag_peak": Decimal("3.21")}})
    monkeypatch.setattr(handler_mod, "_get_table", lambda: table)

    resp = handler(_evt(qs={"deviceId": "raspi-01", "limit": "10"}), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["deviceId"] == "raspi-01"
    assert body["count"] == 2
    assert body["events"][0]["ts"] == "2026-06-29T12:05:00Z"  # newest first
    # Decimal converted to JSON number
    assert body["events"][0]["features"]["mag_peak"] == 3.21
    assert resp["headers"]["access-control-allow-origin"] == "*"


@mock_aws
def test_handler_defaults_device_id(monkeypatch):
    table = _make_table()
    table.put_item(Item={"deviceId": "raspi-01", "ts": "2026-06-29T12:00:00Z"})
    monkeypatch.setattr(handler_mod, "_get_table", lambda: table)
    resp = handler(_evt(qs=None), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["deviceId"] == "raspi-01"


def test_handler_bad_limit_returns_400():
    resp = handler(_evt(qs={"limit": "abc"}), None)
    assert resp["statusCode"] == 400


def test_handler_non_get_returns_405():
    resp = handler(_evt(method="POST"), None)
    assert resp["statusCode"] == 405
