# Cloud Backend Implementation Plan (raspi-accel-ai プラン1/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加速度イベントを AWS IoT Core 経由で受け取り、Bedrock(Claude Sonnet) で解釈・分類して DynamoDB に保存するサーバーレスバックエンドを SAM で構築する。

**Architecture:** IoT Core トピック `devices/+/events` を IoT Rule で受け、analyzer Lambda が起動。Lambda は純粋ロジック（検証・プロンプト生成・応答パース）と外部呼び出し（Bedrock・DynamoDB）を分離し、各々を単体テスト可能にする。非同期呼び出しの失敗は SQS(DLQ) へ退避。

**Tech Stack:** AWS SAM, Python 3.12, boto3, Amazon Bedrock (Converse API), DynamoDB, IoT Core, SQS。テストは pytest + moto。

## Global Constraints

- Python ランタイム: `python3.12`（exact）
- 通信はすべて TLS/HTTPS。HTTP は使わない
- 秘密情報をコード・ログに出力しない。設定は環境変数/SAM パラメータ
- DynamoDB は数値を `Decimal` で保存（boto3 resource は `float` を拒否する）
- Bedrock モデルは SAM パラメータ `BedrockModelId` で外部化（既定値は要・リージョンのモデルアクセス有効化）
- ファイルは責務単位で分割（検証/プロンプト/パース/Bedrock/保存/ハンドラ）

---

## File Structure

```
cloud/
  template.yaml                  # SAM: DynamoDB, Analyzer Lambda, IoT Rule, DLQ
  samconfig.toml                 # sam deploy 既定設定
  src/
    analyzer/
      __init__.py
      validate.py                # イベント検証 (純粋)
      prompt.py                  # プロンプト生成 (純粋)
      analysis.py                # モデル応答パース (純粋)
      bedrock_client.py          # Bedrock Converse 呼び出し
      store.py                   # DynamoDB 保存
      handler.py                 # Lambda エントリ (配線)
  events/
    sample_impact.json           # ローカル/結合テスト用イベント
  tests/
    requirements-dev.txt
    conftest.py
    test_validate.py
    test_prompt.py
    test_analysis.py
    test_bedrock_client.py
    test_store.py
    test_handler.py
```

各タスクは独立してテスト可能な成果物で終わる。

---

### Task 1: SAM プロジェクト雛形と DynamoDB テーブル

**Files:**
- Create: `cloud/template.yaml`
- Create: `cloud/samconfig.toml`
- Create: `cloud/src/analyzer/__init__.py`
- Create: `cloud/tests/requirements-dev.txt`

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces: `EventsTable`（DynamoDB, PK `deviceId`:S / SK `ts`:S, PAY_PER_REQUEST）, SAM パラメータ `BedrockModelId`。後続タスクの Lambda はこのテーブルを参照する。

- [ ] **Step 1: SAM テンプレートを作成**

`cloud/template.yaml`:

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: raspi-accel-ai cloud backend (IoT -> Bedrock -> DynamoDB)

Parameters:
  BedrockModelId:
    Type: String
    Default: anthropic.claude-sonnet-4-20250514-v1:0
    Description: Bedrock model id or inference profile id for Claude Sonnet (must be enabled in the region)

Globals:
  Function:
    Runtime: python3.12
    Timeout: 30
    MemorySize: 256

Resources:
  EventsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: deviceId
          AttributeType: S
        - AttributeName: ts
          AttributeType: S
      KeySchema:
        - AttributeName: deviceId
          KeyType: HASH
        - AttributeName: ts
          KeyType: RANGE

Outputs:
  EventsTableName:
    Value: !Ref EventsTable
```

- [ ] **Step 2: samconfig を作成**

`cloud/samconfig.toml`:

```toml
version = 0.1
[default.deploy.parameters]
stack_name = "raspi-accel-ai"
resolve_s3 = true
capabilities = "CAPABILITY_IAM"
confirm_changeset = true
```

- [ ] **Step 3: パッケージ初期化とテスト依存を作成**

`cloud/src/analyzer/__init__.py`:

```python
```

（空ファイル）

`cloud/tests/requirements-dev.txt`:

```
boto3>=1.34
pytest>=8.0
moto[dynamodb]>=5.0
```

- [ ] **Step 4: テンプレートを検証**

Run: `cd cloud && sam validate --lint`
Expected: `... is a valid SAM Template`（警告0、エラー0）

- [ ] **Step 5: Commit**

```bash
git add cloud/template.yaml cloud/samconfig.toml cloud/src/analyzer/__init__.py cloud/tests/requirements-dev.txt
git commit -m "feat(cloud): scaffold SAM app with DynamoDB events table"
```

---

### Task 2: イベント検証 (validate.py)

**Files:**
- Create: `cloud/src/analyzer/validate.py`
- Create: `cloud/tests/conftest.py`
- Test: `cloud/tests/test_validate.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class ParsedEvent` (dataclass): `device_id:str, ts:str, event_hint:str, features:dict, samples:list|None`
  - `class InvalidEvent(ValueError)`
  - `def validate_event(raw: dict) -> ParsedEvent`

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/conftest.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
```

`cloud/tests/test_validate.py`:

```python
import pytest
from analyzer.validate import validate_event, ParsedEvent, InvalidEvent


def _valid_raw():
    return {
        "device_id": "raspi-01",
        "ts": "2026-06-29T12:34:56.789Z",
        "event_hint": "impact",
        "features": {"mag_peak": 3.21, "mag_rms": 1.05, "tilt_deg": 47.2},
    }


def test_validate_event_returns_parsed_event():
    parsed = validate_event(_valid_raw())
    assert isinstance(parsed, ParsedEvent)
    assert parsed.device_id == "raspi-01"
    assert parsed.event_hint == "impact"
    assert parsed.features["mag_peak"] == 3.21
    assert parsed.samples is None


def test_validate_event_unknown_hint_becomes_unknown():
    raw = _valid_raw()
    raw["event_hint"] = "explosion"
    assert validate_event(raw).event_hint == "unknown"


def test_validate_event_missing_device_id_raises():
    raw = _valid_raw()
    del raw["device_id"]
    with pytest.raises(InvalidEvent):
        validate_event(raw)


def test_validate_event_bad_features_raises():
    raw = _valid_raw()
    raw["features"] = "not-a-dict"
    with pytest.raises(InvalidEvent):
        validate_event(raw)


def test_validate_event_bad_samples_raises():
    raw = _valid_raw()
    raw["samples"] = "not-a-list"
    with pytest.raises(InvalidEvent):
        validate_event(raw)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_validate.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.validate'`）

- [ ] **Step 3: 最小実装を書く**

`cloud/src/analyzer/validate.py`:

```python
from dataclasses import dataclass

ALLOWED_HINTS = {
    "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
}


@dataclass
class ParsedEvent:
    device_id: str
    ts: str
    event_hint: str
    features: dict
    samples: list | None = None


class InvalidEvent(ValueError):
    pass


def validate_event(raw: dict) -> ParsedEvent:
    if not isinstance(raw, dict):
        raise InvalidEvent("event must be an object")
    device_id = raw.get("device_id")
    ts = raw.get("ts")
    features = raw.get("features")
    if not isinstance(device_id, str) or not device_id:
        raise InvalidEvent("device_id is required")
    if not isinstance(ts, str) or not ts:
        raise InvalidEvent("ts is required")
    if not isinstance(features, dict):
        raise InvalidEvent("features must be an object")
    event_hint = raw.get("event_hint", "unknown")
    if event_hint not in ALLOWED_HINTS:
        event_hint = "unknown"
    samples = raw.get("samples")
    if samples is not None and not isinstance(samples, list):
        raise InvalidEvent("samples must be a list when present")
    return ParsedEvent(
        device_id=device_id,
        ts=ts,
        event_hint=event_hint,
        features=features,
        samples=samples,
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_validate.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add cloud/src/analyzer/validate.py cloud/tests/conftest.py cloud/tests/test_validate.py
git commit -m "feat(cloud): add event validation"
```

---

### Task 3: プロンプト生成 (prompt.py)

**Files:**
- Create: `cloud/src/analyzer/prompt.py`
- Test: `cloud/tests/test_prompt.py`

**Interfaces:**
- Consumes: `analyzer.validate.ParsedEvent`
- Produces:
  - `SYSTEM_PROMPT: str`
  - `def build_user_message(event: ParsedEvent) -> str`

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_prompt.py`:

```python
import json
from analyzer.validate import ParsedEvent
from analyzer.prompt import SYSTEM_PROMPT, build_user_message


def _event():
    return ParsedEvent(
        device_id="raspi-01",
        ts="2026-06-29T12:34:56.789Z",
        event_hint="impact",
        features={"mag_peak": 3.21},
    )


def test_system_prompt_is_nonempty():
    assert isinstance(SYSTEM_PROMPT, str) and SYSTEM_PROMPT.strip()


def test_build_user_message_contains_features_json():
    msg = build_user_message(_event())
    assert "mag_peak" in msg
    assert "impact" in msg
    # JSON 部分が含まれ、パース可能であること
    assert json.dumps({"mag_peak": 3.21}, ensure_ascii=False) in msg


def test_build_user_message_requests_json_schema():
    msg = build_user_message(_event())
    assert "label" in msg and "severity" in msg and "explanation" in msg
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_prompt.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.prompt'`）

- [ ] **Step 3: 最小実装を書く**

`cloud/src/analyzer/prompt.py`:

```python
import json

from .validate import ParsedEvent

SYSTEM_PROMPT = (
    "あなたは加速度センサーのイベント解析アシスタントです。"
    "与えられた特徴量から、デバイスの状態を分類し、深刻度と短い説明を日本語で返します。"
)


def build_user_message(event: ParsedEvent) -> str:
    payload = {
        "event_hint": event.event_hint,
        "features": event.features,
        "ts": event.ts,
    }
    return (
        "次の加速度イベントを解析してください。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n\n"
        "必ず次のJSON形式のみで回答してください:\n"
        '{"label": "<normal|vibration|tilt|impact|freefall|transport>", '
        '"severity": "<low|medium|high>", '
        '"explanation": "<日本語の短い説明>"}'
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_prompt.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add cloud/src/analyzer/prompt.py cloud/tests/test_prompt.py
git commit -m "feat(cloud): add prompt builder"
```

---

### Task 4: モデル応答パース (analysis.py)

**Files:**
- Create: `cloud/src/analyzer/analysis.py`
- Test: `cloud/tests/test_analysis.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class Analysis` (dataclass): `label:str, severity:str, explanation:str`
  - `class AnalysisParseError(ValueError)`
  - `def parse_analysis(text: str) -> Analysis`

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_analysis.py`:

```python
import pytest
from analyzer.analysis import parse_analysis, Analysis, AnalysisParseError


def test_parse_clean_json():
    text = '{"label": "impact", "severity": "high", "explanation": "強い衝撃を検知"}'
    a = parse_analysis(text)
    assert a == Analysis(label="impact", severity="high", explanation="強い衝撃を検知")


def test_parse_json_with_surrounding_text():
    text = 'はい、結果です:\n{"label": "tilt", "severity": "low", "explanation": "傾き軽微"} 以上'
    a = parse_analysis(text)
    assert a.label == "tilt"
    assert a.severity == "low"


def test_parse_invalid_label_raises():
    text = '{"label": "explosion", "severity": "high", "explanation": "x"}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_invalid_severity_raises():
    text = '{"label": "impact", "severity": "critical", "explanation": "x"}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_empty_explanation_raises():
    text = '{"label": "impact", "severity": "high", "explanation": "  "}'
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


def test_parse_no_json_raises():
    with pytest.raises(AnalysisParseError):
        parse_analysis("no json here")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_analysis.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.analysis'`）

- [ ] **Step 3: 最小実装を書く**

`cloud/src/analyzer/analysis.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_analysis.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add cloud/src/analyzer/analysis.py cloud/tests/test_analysis.py
git commit -m "feat(cloud): add model response parser"
```

---

### Task 5: Bedrock 呼び出し (bedrock_client.py)

**Files:**
- Create: `cloud/src/analyzer/bedrock_client.py`
- Test: `cloud/tests/test_bedrock_client.py`

**Interfaces:**
- Consumes: `ParsedEvent`, `SYSTEM_PROMPT`, `build_user_message`, `parse_analysis`, `Analysis`
- Produces:
  - `def analyze(client, model_id: str, event: ParsedEvent) -> Analysis`
    - `client` は boto3 `bedrock-runtime` 互換（`.converse(...)` を持つ）。テストではモックを注入。

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_bedrock_client.py`:

```python
from analyzer.validate import ParsedEvent
from analyzer.analysis import Analysis
from analyzer.bedrock_client import analyze


class FakeBedrock:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    def converse(self, **kwargs):
        self.last_kwargs = kwargs
        return {"output": {"message": {"content": [{"text": self._text}]}}}


def _event():
    return ParsedEvent(
        device_id="raspi-01",
        ts="2026-06-29T12:34:56.789Z",
        event_hint="impact",
        features={"mag_peak": 3.21},
    )


def test_analyze_returns_analysis():
    client = FakeBedrock(
        '{"label": "impact", "severity": "high", "explanation": "衝撃検知"}'
    )
    result = analyze(client, "model-x", _event())
    assert result == Analysis(label="impact", severity="high", explanation="衝撃検知")


def test_analyze_passes_model_id_and_system_prompt():
    client = FakeBedrock(
        '{"label": "normal", "severity": "low", "explanation": "正常"}'
    )
    analyze(client, "model-x", _event())
    assert client.last_kwargs["modelId"] == "model-x"
    assert client.last_kwargs["system"][0]["text"]
    assert client.last_kwargs["messages"][0]["role"] == "user"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_bedrock_client.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.bedrock_client'`）

- [ ] **Step 3: 最小実装を書く**

`cloud/src/analyzer/bedrock_client.py`:

```python
from .analysis import Analysis, parse_analysis
from .prompt import SYSTEM_PROMPT, build_user_message
from .validate import ParsedEvent


def analyze(client, model_id: str, event: ParsedEvent) -> Analysis:
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {"role": "user", "content": [{"text": build_user_message(event)}]}
        ],
        inferenceConfig={"maxTokens": 300, "temperature": 0.0},
    )
    text = response["output"]["message"]["content"][0]["text"]
    return parse_analysis(text)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_bedrock_client.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add cloud/src/analyzer/bedrock_client.py cloud/tests/test_bedrock_client.py
git commit -m "feat(cloud): add bedrock converse client"
```

---

### Task 6: DynamoDB 保存 (store.py)

**Files:**
- Create: `cloud/src/analyzer/store.py`
- Test: `cloud/tests/test_store.py`

**Interfaces:**
- Consumes: `ParsedEvent`, `Analysis`
- Produces:
  - `def build_item(event: ParsedEvent, analysis: Analysis, model_id: str, now_iso: str) -> dict`
    - 返却 item のキー: `deviceId, ts, event_hint, features, label, severity, explanation, model_id, created_at`
    - `features` は `Decimal` 変換済みの dict（DynamoDB 互換）
  - `def save_item(table, item: dict) -> None`（`table.put_item(Item=item)` を呼ぶ）

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_store.py`:

```python
from decimal import Decimal

import boto3
import pytest
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_store.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.store'`）

- [ ] **Step 3: 最小実装を書く**

`cloud/src/analyzer/store.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_store.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add cloud/src/analyzer/store.py cloud/tests/test_store.py
git commit -m "feat(cloud): add dynamodb store"
```

---

### Task 7: Lambda ハンドラ配線 + IoT Rule + DLQ

**Files:**
- Create: `cloud/src/analyzer/handler.py`
- Create: `cloud/events/sample_impact.json`
- Test: `cloud/tests/test_handler.py`
- Modify: `cloud/template.yaml`（Analyzer 関数・IoT Rule イベント・DLQ・権限を追加）

**Interfaces:**
- Consumes: `validate_event`, `analyze`, `build_item`, `save_item`
- Produces:
  - `def handler(event: dict, context) -> dict`（戻り値 `{"status","deviceId","ts","label"}`）
  - 環境変数: `EVENTS_TABLE`, `BEDROCK_MODEL_ID`
  - テスト用に内部関数を注入可能にする: `handler` は `_get_bedrock()` / `_get_table()` 経由で依存を取得し、テストでこれらを monkeypatch する。

- [ ] **Step 1: 失敗するテストを書く**

`cloud/tests/test_handler.py`:

```python
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

import analyzer.handler as handler_mod
from analyzer.handler import handler


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
    with pytest.raises(Exception):
        handler({"features": {}}, None)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd cloud && python -m pytest tests/test_handler.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyzer.handler'`）

- [ ] **Step 3: ハンドラ実装を書く**

`cloud/src/analyzer/handler.py`:

```python
import os
from datetime import datetime, timezone

import boto3

from .bedrock_client import analyze
from .store import build_item, save_item
from .validate import validate_event

_bedrock = None
_table = None


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime")
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd cloud && python -m pytest tests/test_handler.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: サンプルイベントを作成**

`cloud/events/sample_impact.json`:

```json
{
  "device_id": "raspi-01",
  "ts": "2026-06-29T12:34:56.789Z",
  "event_hint": "impact",
  "features": { "mag_peak": 3.21, "mag_rms": 1.05, "tilt_deg": 47.2, "freefall_ms": 0, "window_ms": 1000 }
}
```

- [ ] **Step 6: template.yaml に Analyzer 関数・IoT Rule・DLQ を追加**

`cloud/template.yaml` の `Resources:` 配下（`EventsTable` の後）に追記し、`Outputs:` も追記:

```yaml
  AnalyzerDLQ:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600

  AnalyzerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: analyzer.handler.handler
      Environment:
        Variables:
          EVENTS_TABLE: !Ref EventsTable
          BEDROCK_MODEL_ID: !Ref BedrockModelId
      DeadLetterQueue:
        Type: SQS
        TargetArn: !GetAtt AnalyzerDLQ.Arn
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref EventsTable
        - SQSSendMessagePolicy:
            QueueName: !GetAtt AnalyzerDLQ.QueueName
        - Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
              Resource: "*"
      Events:
        AccelEvent:
          Type: IoTRule
          Properties:
            Sql: "SELECT * FROM 'devices/+/events'"
```

`Outputs:` に追記:

```yaml
  AnalyzerFunctionName:
    Value: !Ref AnalyzerFunction
  AnalyzerDLQUrl:
    Value: !Ref AnalyzerDLQ
```

> 注: `bedrock:InvokeModel` の `Resource` は `"*"` で開始するが、デプロイ後に使用モデル/推論プロファイルの ARN へ絞ることを推奨（最小権限）。

- [ ] **Step 7: テンプレートとビルドを検証**

Run: `cd cloud && sam validate --lint && sam build`
Expected: `... is a valid SAM Template` ののち `Build Succeeded`

- [ ] **Step 8: 全テストを実行**

Run: `cd cloud && python -m pytest tests/ -v`
Expected: PASS（全テスト緑）

- [ ] **Step 9: Commit**

```bash
git add cloud/src/analyzer/handler.py cloud/events/sample_impact.json cloud/tests/test_handler.py cloud/template.yaml
git commit -m "feat(cloud): wire analyzer handler with IoT rule and DLQ"
```

---

### Task 8: デプロイ手順とローカル結合確認（ドキュメント）

**Files:**
- Create: `cloud/README.md`

**Interfaces:**
- Consumes: 全タスクの成果物
- Produces: デプロイ/検証手順（コードなし）

- [ ] **Step 1: README を作成**

`cloud/README.md`:

````markdown
# raspi-accel-ai cloud backend

IoT Core → analyzer Lambda → Bedrock(Claude Sonnet) → DynamoDB のサーバーレスバックエンド。

## 前提
- AWS CLI / SAM CLI 設定済み
- 対象リージョンで Bedrock の Claude Sonnet モデルアクセスを有効化済み
- `template.yaml` の `BedrockModelId` 既定値を、有効化したモデル/推論プロファイルIDに合わせる

## テスト
```bash
cd cloud
python -m pip install -r tests/requirements-dev.txt
python -m pytest tests/ -v
```

## ローカル実行（Lambda 単体・Bedrock はモック不可のため要実 API）
```bash
sam build
sam local invoke AnalyzerFunction -e events/sample_impact.json \
  --env-vars <(echo '{"AnalyzerFunction":{"EVENTS_TABLE":"<table>","BEDROCK_MODEL_ID":"<model-id>"}}')
```

## デプロイ
```bash
sam build
sam deploy --guided   # 初回。以後は sam deploy
```

## 結合確認（MQTT テスト発行）
AWS IoT コンソールの「MQTT テストクライアント」で、トピック `devices/raspi-01/events` に
`events/sample_impact.json` の内容を publish し、DynamoDB の `EventsTable` にレコードが
追加されること、失敗時は `AnalyzerDLQ` にメッセージが入ることを確認する。
````

- [ ] **Step 2: Commit**

```bash
git add cloud/README.md
git commit -m "docs(cloud): add backend deploy and verification guide"
```

---

## Self-Review

**1. Spec coverage（spec の各要素 → タスク対応）**
- IoT Core(MQTT) 受信 → Task 7（IoT Rule）/ デバイス証明書発行はプラン2(エッジ)で実施
- IoT Rule → Lambda → Task 7
- Bedrock(Claude Sonnet) 解釈・分類 → Task 5 + パラメータ `BedrockModelId`
- 構造化出力(label/severity/explanation) → Task 4（パース）/ Task 3（プロンプト）
- DynamoDB 保存（PK deviceId / SK ts、Decimal） → Task 1（テーブル）/ Task 6（保存）
- 失敗時 DLQ → Task 7（SQS + DeadLetterQueue）
- エラー処理(入力検証・リトライ) → Task 2（検証）/ Lambda 非同期の自動リトライ + DLQ。Bedrock のリトライは boto3 既定（standard）に委ねる（必要なら後続で `Config(retries=...)` 追加）
- コスト最適化（イベント時のみ・サーバーレス） → アーキ全体（常時起動なし）
- IaC=SAM → Task 1/7
- セキュリティ（最小権限・秘密はパラメータ） → Task 7 ポリシー / `BedrockModelId` パラメータ
- ダッシュボード/API/Cognito → 本プラン対象外（プラン3）
- エッジ(Pi)・シミュレータ → 本プラン対象外（プラン2）

**2. Placeholder scan:** TBD/TODO/「適切に処理」等なし。各コードステップに実コードあり。

**3. Type consistency:** `ParsedEvent`/`Analysis` のフィールド名、`validate_event`/`analyze`/`build_item`/`save_item`/`handler` のシグネチャがタスク間で一致。DynamoDB キー名 `deviceId`/`ts` は Task 1・6・7 で一致。

**未カバーで意図的に次プランへ送るもの:** デバイス X.509 証明書のプロビジョニング（プラン2 エッジで実施。Lambda 側は受信のみで証明書不要）。
