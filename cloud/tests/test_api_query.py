from decimal import Decimal

import boto3
from moto import mock_aws

from api.query import query_events, to_jsonable


def test_to_jsonable_converts_decimals():
    data = {"a": Decimal("3.21"), "b": Decimal("5"), "c": [Decimal("1.5"), {"d": Decimal("2")}]}
    assert to_jsonable(data) == {"a": 3.21, "b": 5, "c": [1.5, {"d": 2}]}
    assert isinstance(to_jsonable(Decimal("5")), int)
    assert isinstance(to_jsonable(Decimal("1.5")), float)


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


@mock_aws
def test_query_events_newest_first_and_limit():
    table = _make_table()
    for ts in ["2026-06-29T12:00:00Z", "2026-06-29T12:01:00Z", "2026-06-29T12:02:00Z"]:
        table.put_item(Item={"deviceId": "raspi-01", "ts": ts, "label": "impact"})
    items = query_events(table, "raspi-01", limit=2)
    assert [i["ts"] for i in items] == ["2026-06-29T12:02:00Z", "2026-06-29T12:01:00Z"]


@mock_aws
def test_query_events_scopes_to_device():
    table = _make_table()
    table.put_item(Item={"deviceId": "raspi-01", "ts": "2026-06-29T12:00:00Z"})
    table.put_item(Item={"deviceId": "raspi-09", "ts": "2026-06-29T12:00:00Z"})
    items = query_events(table, "raspi-01")
    assert len(items) == 1 and items[0]["deviceId"] == "raspi-01"
