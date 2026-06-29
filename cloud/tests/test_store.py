from decimal import Decimal

import boto3
from moto import mock_aws

from analyzer.validate import ParsedEvent
from analyzer.analysis import Analysis
from analyzer.store import build_item, save_item


def _event():
    return ParsedEvent(
        device_id="raspi-01",
        ts="2026-06-29T12:34:56.789Z",
        event_hint="impact",
        features={"mag_peak": 3.21, "count": 5},
    )


def _analysis():
    return Analysis(label="impact", severity="high", explanation="衝撃検知")


def test_build_item_shape_and_decimal_features():
    item = build_item(_event(), _analysis(), "model-x", "2026-06-29T12:35:00Z")
    assert item["deviceId"] == "raspi-01"
    assert item["ts"] == "2026-06-29T12:34:56.789Z"
    assert item["label"] == "impact"
    assert item["model_id"] == "model-x"
    assert item["created_at"] == "2026-06-29T12:35:00Z"
    # float は Decimal へ変換されていること
    assert isinstance(item["features"]["mag_peak"], Decimal)
    assert item["features"]["mag_peak"] == Decimal("3.21")


@mock_aws
def test_save_item_writes_to_dynamodb():
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
    item = build_item(_event(), _analysis(), "model-x", "2026-06-29T12:35:00Z")
    save_item(table, item)

    got = table.get_item(
        Key={"deviceId": "raspi-01", "ts": "2026-06-29T12:34:56.789Z"}
    )["Item"]
    assert got["label"] == "impact"
    assert got["features"]["mag_peak"] == Decimal("3.21")
