# raspi-accel-ai cloud backend

IoT Core → analyzer Lambda → Bedrock(Claude Haiku 4.5) → DynamoDB のサーバーレスバックエンド。

## 前提
- AWS CLI / SAM CLI 設定済み
- 初回のみ Anthropic モデルのユースケース詳細フォームを提出済み（Bedrockコンソールの Playground でClaudeを初回実行すると表示。有効化に約15分）
- 既定値は東京向け推論プロファイル `jp.anthropic.claude-haiku-4-5-20251001-v1:0`（低コスト）。高精度にするなら `jp.anthropic.claude-sonnet-4-5-20250929-v1:0` を `--parameter-overrides BedrockModelId=...` で指定。デプロイは ap-northeast-1。
- 他リージョンを使う場合は接頭辞を合わせる（us-east-1 → `us.`、欧州 → `eu.`、横断 → `global.`）。In-Region用の素のID（接頭辞なし）はオンデマンドConverse非対応のリージョンがあるため、Geoプロファイルを推奨。

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
