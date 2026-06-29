# Dashboard API & Infra Implementation Plan (raspi-accel-ai プラン3a/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DynamoDB の加速度イベントを読み取る認証付きHTTP API（API Gateway HTTP API + Lambda + Cognito JWT）を SAM で構築し、ダッシュボードフロント(プラン3b)が叩けるバックエンドを用意する。

**Architecture:** 既存 `cloud/` の SAM スタックに、読み取り専用の `api` Lambda（DynamoDB query）、HTTP API（CORS + Cognito JWT オーソライザ）、Cognito ユーザープール/クライアント/ホステッドUIドメインを追加する。Lambda は純粋なクエリ/直列化ロジック（moto でテスト）と薄い HTTP ハンドラに分離。

**Tech Stack:** AWS SAM、Python 3.12 Lambda、DynamoDB（query）、API Gateway HTTP API、Amazon Cognito（JWT authorizer / Hosted UI）。テストは pytest + moto。ローカル検証は cfn-lint（sam 未導入のため）。

## Global Constraints

- Python ランタイム: `python3.12`（exact）
- API は **読み取り専用**（DynamoDBReadPolicy のみ。書き込み権限を持たせない）
- DynamoDB の `Decimal` は JSON 応答で int/float へ変換（整数値は int、その他は float）
- すべて HTTPS。CORS は許可するが認証は Cognito JWT 必須（DefaultAuthorizer）
- 秘密情報はコード・ログに出さない。設定は環境変数/SAM パラメータ
- 既存 `cloud/template.yaml` の EventsTable/AnalyzerFunction/AnalyzerDLQ/Parameters/Globals は変更しない（追加のみ）
- api Lambda は `cloud/src/api/` パッケージ（analyzer と同じ CodeUri `src/`）。テストは `cd cloud && <repo>/.venv/bin/python -m pytest tests/`

## File Structure

```
cloud/
  template.yaml              # 追加: UserPool/Client/Domain, DashboardApi(HttpApi), ApiFunction, Outputs
  src/api/
    __init__.py
    query.py                 # query_events + to_jsonable (純)
    handler.py               # HTTP API v2 ハンドラ
  tests/
    test_api_query.py
    test_api_handler.py
```

---

### Task 1: クエリ/直列化モジュール (api/query.py)

**Files:**
- Create: `cloud/src/api/__init__.py` (空)
- Create: `cloud/src/api/query.py`
- Test: `cloud/tests/test_api_query.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `def query_events(table, device_id: str, limit: int = 50) -> list[dict]`（`deviceId` で query、`ts` 降順=新しい順、Limit 適用）
  - `def to_jsonable(obj)`（`Decimal`→整数なら int / それ以外 float、dict/list 再帰）

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_api_query.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/test_api_query.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'api.query'`)

- [ ] **Step 3: 実装を書く**

`cloud/src/api/__init__.py`:

```python
```

(空)

`cloud/src/api/query.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/test_api_query.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add cloud/src/api/__init__.py cloud/src/api/query.py cloud/tests/test_api_query.py
git commit -m "feat(cloud): add dashboard api query and decimal serialization"
```

---

### Task 2: HTTP API ハンドラ (api/handler.py)

**Files:**
- Create: `cloud/src/api/handler.py`
- Test: `cloud/tests/test_api_handler.py`

**Interfaces:**
- Consumes: `query_events`, `to_jsonable`
- Produces:
  - `def handler(event, context) -> dict`（HTTP API payload v2 を処理。`GET /events?deviceId=&limit=` を返す）
  - 環境変数: `EVENTS_TABLE`。依存は `_get_table()` 経由でテスト時に monkeypatch
  - 応答: `{statusCode, headers(content-type+CORS), body(JSON)}`。`limit` は 1..200 にクランプ、非整数は 400、GET 以外は 405

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_api_handler.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/test_api_handler.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'api.handler'`)

- [ ] **Step 3: 実装を書く**

`cloud/src/api/handler.py`:

```python
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
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
        },
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
    items = query_events(_get_table(), device_id, limit)
    return _response(
        200,
        {"deviceId": device_id, "count": len(items), "events": to_jsonable(items)},
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/test_api_handler.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add cloud/src/api/handler.py cloud/tests/test_api_handler.py
git commit -m "feat(cloud): add dashboard api http handler"
```

---

### Task 3: SAM テンプレート拡張（Cognito + HTTP API + ApiFunction）

**Files:**
- Modify: `cloud/template.yaml`（Resources に Cognito/HttpApi/ApiFunction 追加、Outputs 追加）

**Interfaces:**
- Consumes: 既存 `EventsTable`、Task 2 の `api.handler.handler`
- Produces: 認証付き `GET /events` エンドポイント、Cognito ユーザープール。Outputs: `DashboardApiUrl`, `UserPoolId`, `UserPoolClientId`, `HostedUiDomain`

- [ ] **Step 1: Resources に追記（`AnalyzerFunction` の後）**

`cloud/template.yaml` の `Resources:` に追加:

```yaml
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: raspi-accel-ai-users
      AdminCreateUserConfig:
        AllowAdminCreateUserOnly: true
      AutoVerifiedAttributes:
        - email
      UsernameAttributes:
        - email
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireLowercase: true
          RequireNumbers: true
          RequireUppercase: true
          RequireSymbols: false

  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      UserPoolId: !Ref UserPool
      GenerateSecret: false
      AllowedOAuthFlowsUserPoolClient: true
      AllowedOAuthFlows:
        - code
      AllowedOAuthScopes:
        - openid
        - email
        - profile
      SupportedIdentityProviders:
        - COGNITO
      CallbackURLs:
        - http://localhost:5173/
      LogoutURLs:
        - http://localhost:5173/

  UserPoolDomain:
    Type: AWS::Cognito::UserPoolDomain
    Properties:
      Domain: !Sub "raspi-accel-ai-${AWS::AccountId}"
      UserPoolId: !Ref UserPool

  DashboardApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins:
          - "*"
        AllowMethods:
          - GET
          - OPTIONS
        AllowHeaders:
          - authorization
          - content-type
      Auth:
        Authorizers:
          CognitoJwt:
            IdentitySource: "$request.header.Authorization"
            JwtConfiguration:
              issuer: !Sub "https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}"
              audience:
                - !Ref UserPoolClient
        DefaultAuthorizer: CognitoJwt

  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: api.handler.handler
      Environment:
        Variables:
          EVENTS_TABLE: !Ref EventsTable
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref EventsTable
      Events:
        ListEvents:
          Type: HttpApi
          Properties:
            ApiId: !Ref DashboardApi
            Method: GET
            Path: /events
```

- [ ] **Step 2: Outputs に追記**

`cloud/template.yaml` の `Outputs:` に追加:

```yaml
  DashboardApiUrl:
    Value: !Sub "https://${DashboardApi}.execute-api.${AWS::Region}.amazonaws.com"
  UserPoolId:
    Value: !Ref UserPool
  UserPoolClientId:
    Value: !Ref UserPoolClient
  HostedUiDomain:
    Value: !Sub "raspi-accel-ai-${AWS::AccountId}.auth.${AWS::Region}.amazoncognito.com"
```

- [ ] **Step 3: テンプレートを検証**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/cfn-lint template.yaml`
Expected: エラー(E…)0件で exit 0。W… 警告が出た場合は全文を報告（ブロッカーではない）。既存リソース（EventsTable 等）に差分が出ていないことも確認。

- [ ] **Step 4: 全クラウドテストを実行（回帰確認）**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/ -q`
Expected: 全テスト緑（analyzer 系 + 新 api 系）

- [ ] **Step 5: Commit**

```bash
git add cloud/template.yaml
git commit -m "feat(cloud): add cognito user pool and authenticated dashboard http api"
```

---

### Task 4: デプロイ手順（cloud/README へ追記）

**Files:**
- Modify: `cloud/README.md`（ダッシュボードAPIのデプロイ/ユーザー作成/トークン取得を追記）

**Interfaces:**
- Consumes: Task 1-3 の成果物
- Produces: API デプロイ・Cognito ユーザー作成・トークン取得手順（コードなし）

- [ ] **Step 1: README にセクション追記**

`cloud/README.md` の末尾に追加:

````markdown
## ダッシュボード API（プラン3a）

`sam deploy` 後、Outputs に `DashboardApiUrl` / `UserPoolId` / `UserPoolClientId` / `HostedUiDomain` が出力される。

### Cognito ユーザー作成（管理者作成のみ）
```bash
aws cognito-idp admin-create-user --user-pool-id <UserPoolId> \
  --username you@example.com --user-attributes Name=email,Value=you@example.com Name=email_verified,Value=true
aws cognito-idp admin-set-user-password --user-pool-id <UserPoolId> \
  --username you@example.com --password 'YourPassw0rd' --permanent
```

### 動作確認（JWT を付けて GET /events）
Hosted UI もしくは Cognito の認証フローで取得した IdToken を使う:
```bash
curl -H "Authorization: Bearer <IdToken>" "<DashboardApiUrl>/events?deviceId=raspi-01&limit=20"
```
認証なし/不正トークンは 401。`events` は新しい順、`features` は JSON 数値（Decimal変換済み）。

> フロントエンド（React/Vite SPA、Cognito Hosted UI ログイン）はプラン3b で実装する。
> 本番の CallbackURLs/LogoutURLs（CloudFront ドメイン）はプラン3b でテンプレートに追加する。
````

- [ ] **Step 2: Commit**

```bash
git add cloud/README.md
git commit -m "docs(cloud): add dashboard api deploy and auth guide"
```

---

## Self-Review

**1. Spec coverage（design spec §6 → タスク）**
- API Gateway(HTTP API) → Lambda → DynamoDB → Task 2 + Task 3
- 最近イベント一覧 `GET /events` → Task 1（query 新しい順）+ Task 2
- 認証 Cognito → Task 3（UserPool/Client/Domain + JWT authorizer）
- 読み取り専用・最小権限 → Task 3（DynamoDBReadPolicy のみ）
- Decimal→JSON → Task 1（to_jsonable）
- IaC=SAM、既存スタック拡張 → Task 3
- 時系列データ取得：`GET /events` のレスポンス features を使って3bでグラフ化（別途 timeseries エンドポイントは作らず、一覧で代替=YAGNI）

**2. Placeholder scan:** TBD/「適切に処理」等なし。各コードステップに実コードあり。CallbackURLs の localhost は3bで本番URL追加と明記（プレースホルダではなく段階的構成）。

**3. Type consistency:** `query_events(table, device_id, limit)` / `to_jsonable(obj)` の署名が Task 1/2 で一致。DynamoDB キー名 `deviceId`/`ts` は既存スタック・query・テストで一致。ハンドラ応答キー `deviceId/count/events` は3bフロントが消費。

**意図的に3bへ送るもの:** React/Vite SPA、Cognito Hosted UI ログイン、S3+CloudFront ホスティング、本番 CallbackURLs。
