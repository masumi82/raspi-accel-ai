from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

import analyzer.handler as handler_mod
from analyzer.handler import handler
from analyzer.validate import InvalidEvent


class FakeBedrock:
    def converse(self, **kwargs):
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": '{"label": "impact", "severity": "high", '
                            '"explanation": "衝撃検知"}'
                        }
                    ]
                }
            }
        }


@mock_aws
def test_handler_end_to_end(monkeypatch):
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
    table = ddb.Table("events")

    monkeypatch.setenv("EVENTS_TABLE", "events")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "model-x")
    monkeypatch.setattr(handler_mod, "_get_bedrock", lambda: FakeBedrock())
    monkeypatch.setattr(handler_mod, "_get_table", lambda: table)

    event = {
        "device_id": "raspi-01",
        "ts": "2026-06-29T12:34:56.789Z",
        "event_hint": "impact",
        "features": {"mag_peak": 3.21},
    }
    result = handler(event, None)
    assert result["status"] == "ok"
    assert result["label"] == "impact"

    got = table.get_item(
        Key={"deviceId": "raspi-01", "ts": "2026-06-29T12:34:56.789Z"}
    )["Item"]
    assert got["label"] == "impact"
    assert got["features"]["mag_peak"] == Decimal("3.21")


def test_handler_invalid_event_raises(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "model-x")
    with pytest.raises(InvalidEvent):
        handler({"features": {}}, None)
