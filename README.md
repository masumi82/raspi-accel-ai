# raspi-accel-ai

Raspberry Pi の3軸加速度センサー **ADXL345** で動き・振動・傾き・落下を自律監視し、
**AWS IoT Core** 経由で **Amazon Bedrock (Claude Sonnet)** が状況を解釈・分類、
結果を **DynamoDB** に蓄積して **ダッシュボード**で可視化する、IoT × 生成AI の自己開発プロジェクトです。

> ユーザーが指示を出すのではなく、**ラズパイがセンサー値の変化をトリガーに自律的にAIへ問い合わせて判断する**のが本システムの中心です。

## 特徴

- **フルサーバーレス**：常時起動の計算リソースなし。LLM呼び出しは閾値イベント時のみ（＋クールダウン）でコスト最適化
- **エッジ自律検知**：Pi 側で特徴量抽出・閾値判定を行い、必要なイベントだけを送信
- **生成AIによる解釈**：加速度の特徴量を Bedrock(Claude Sonnet) が `label / severity / explanation` に分類
- **堅牢な通信**：MQTT over mTLS（X.509）、オフライン時はローカルバッファ＋再送、失敗イベントは SQS DLQ へ
- **セキュリティ重視**：デバイス個別証明書・最小権限IoTポリシー・秘密鍵 600・秘密情報は非コミット
- **テスト駆動**：62 テスト（cloud 20 / edge 42）。実機・SDK 非依存のシミュレータとモックで CI 可能

## アーキテクチャ

```
[Raspberry Pi (edge/)]                         [AWS Cloud (cloud/)]
 ADXL345 (I2C)
   │ 連続サンプリング
   ▼
 特徴量抽出 + 閾値/変化検知（クールダウン付き）
   │ 検知イベントのみ
   ▼  MQTT over TLS (X.509)
 AWS IoT Core ──► IoT Rule ──► Lambda(analyzer)
   ▲                              │  ├─► Amazon Bedrock (Claude Sonnet) で解釈・分類
   │ オフライン時はローカルバッファ   │  └─► DynamoDB に保存（特徴量＋AI判定）
   └─ 再接続で再送                  └─(失敗)─► SQS (DLQ)

 [Dashboard (plan 3, 予定)]
 ブラウザ ─► CloudFront ─► S3 (React/Vite SPA)
        └─► API Gateway ─► Lambda(api) ─► DynamoDB   （認証: Cognito）
```

イベントJSON契約（エッジ→クラウド共通、トピック `devices/{device_id}/events`）:

```json
{
  "device_id": "raspi-01",
  "ts": "2026-06-29T12:34:56.789Z",
  "event_hint": "impact",
  "features": { "mag_peak": 3.21, "mag_rms": 1.05, "tilt_deg": 47.2, "freefall_ms": 0, "window_ms": 1000 }
}
```
`event_hint` ∈ `normal | vibration | tilt | impact | freefall | transport | unknown`

## コンポーネント

| サブシステム | 状態 | 内容 | ドキュメント |
|---|---|---|---|
| **cloud/** クラウドバックエンド | ✅ 完了 | SAM: IoT Core → analyzer Lambda(Bedrock) → DynamoDB、SQS DLQ | [cloud/README.md](cloud/README.md) |
| **edge/** エッジエージェント | ✅ 完了 | Pi: ADXL345読取・検知・MQTT送信・オフラインバッファ・端末プロビジョニング | [edge/README.md](edge/README.md) |
| **frontend/** ダッシュボード | ✅ 完了 | React/Vite SPA + API Gateway/Lambda + Cognito | [frontend/README.md](frontend/README.md) |

## 技術スタック

- **エッジ**: Python 3、AWS IoT Device SDK v2 (awsiotsdk)、adafruit-circuitpython-adxl34x
- **クラウド**: AWS SAM、Python 3.12 Lambda、Amazon Bedrock (Converse API)、DynamoDB、IoT Core、SQS
- **可視化(予定)**: React + Vite、API Gateway (HTTP API)、Amazon Cognito、S3 + CloudFront
- **テスト**: pytest、moto

## リポジトリ構成

```
raspi-accel-ai/
├── cloud/                # AWS SAM サーバーレスバックエンド
│   ├── template.yaml
│   ├── src/analyzer/     # 検証 / プロンプト / 解析 / Bedrock / 保存 / ハンドラ
│   └── tests/
├── edge/                 # Raspberry Pi エージェント
│   ├── config / detector / event / sensor / buffer / mqtt_client / agent / provision
│   └── tests/
├── docs/superpowers/     # 設計書(spec)と実装計画(plan)
└── README.md
```

## クイックスタート

### テスト
```bash
python -m venv .venv && . .venv/bin/activate
pip install boto3 pytest "moto[dynamodb]"
# エッジ（リポジトリルートから）
python -m pytest edge/tests/ -q
# クラウド
(cd cloud && pip install -r tests/requirements-dev.txt && python -m pytest tests/ -q)
```

### クラウドのデプロイ（概要）
東京リージョンで Claude Sonnet のモデルアクセスを有効化のうえ:
```bash
cd cloud
sam build && sam deploy --guided   # 既定モデル: apac.anthropic.claude-sonnet-4-20250514-v1:0
```
詳細は [cloud/README.md](cloud/README.md)。

### エッジ（Raspberry Pi）
```bash
python -m edge.provision --thing-name raspi-01 --region ap-northeast-1 --cert-dir certs
# 出力された `export DEVICE_ID=raspi-01` を設定し、SENSOR_MODE/証明書を指定して実行
```
詳細は [edge/README.md](edge/README.md)。シミュレータ（`SENSOR_MODE=impact` 等）で実機なしの動作確認も可能です。

## セキュリティ

- すべての通信は TLS/HTTPS（MQTT は mTLS / X.509）
- デバイスは個別 X.509 証明書、IoTポリシーは `${iot:Connection.Thing.ThingName}` でトピック/クライアントIDをスコープした最小権限
- 秘密鍵はファイル作成時から `0o600`。`.env`・`*.pem`・`*.key`・`certs/` は `.gitignore` 済みで非コミット
- Lambda は最小権限 IAM。設定はパラメータ/環境変数で外部化

## ロードマップ

- [x] プラン1: クラウドバックエンド（IoT → Bedrock → DynamoDB）
- [x] プラン2: エッジエージェント（ADXL345 → MQTT、プロビジョニング、オフラインバッファ）
- [x] プラン3: ダッシュボード（React/Vite + API + Cognito）
- [ ] 実機ブリングアップ（実 ADXL345 / 実 IoT 接続 / Bedrock 結合）

## ライセンス

[MIT](LICENSE)

---
🤖 設計・実装は [Claude Code](https://claude.com/claude-code) を用いた spec → plan → TDD 実装 → レビューのワークフローで進めています。
