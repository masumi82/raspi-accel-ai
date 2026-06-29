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
