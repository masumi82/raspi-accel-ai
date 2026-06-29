from decimal import Decimal

from boto3.dynamodb.conditions import Key


def query_events(table, device_id, limit=50):
    resp = table.query(
        KeyConditionExpression=Key("deviceId").eq(device_id),
        ScanIndexForward=False,  # newest (highest ts) first
        Limit=limit,
    )
    return resp.get("Items", [])


def to_jsonable(obj):
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
