# raspi-accel-ai dashboard (frontend)

React + Vite の SPA。Cognito Hosted UI でログインし、ダッシュボードAPI(プラン3a)から
加速度イベントを取得して時系列グラフと一覧で表示する。

## セットアップ
```bash
cd frontend
npm install
cp .env.example .env   # 値を sam デプロイの Outputs で埋める
```
`.env` に設定する値（`cloud` スタックの Outputs より）:
- `VITE_API_URL` = DashboardApiUrl
- `VITE_COGNITO_AUTHORITY` = `https://cognito-idp.<region>.amazonaws.com/<UserPoolId>`
- `VITE_COGNITO_CLIENT_ID` = UserPoolClientId
- `VITE_COGNITO_DOMAIN` = HostedUiDomain
- `VITE_REDIRECT_URI` = ローカルは `http://localhost:5173/`、本番は `FrontendUrl` ＋ `/`
- `VITE_DEVICE_ID` = 例 `raspi-01`

## 開発
```bash
npm run dev      # http://localhost:5173
npm test         # vitest (api/series/auth)
npm run build    # dist/ を生成
```

## デプロイ（S3 + CloudFront）
```bash
npm run build
aws s3 sync dist/ "s3://<FrontendBucketName>/" --delete
aws cloudfront create-invalidation --distribution-id <DistId> --paths '/*'
```
`FrontendUrl`（CloudFront ドメイン）にアクセス → Cognito Hosted UI ログイン → ダッシュボード表示。
（CloudFront ドメインは Cognito CallbackURLs と API CORS に登録済み。`.env` の REDIRECT_URI を本番URLにして再ビルドすること。）

## テスト方針
純ロジック（`api.js`/`series.js`/`auth.js`）は vitest で検証。React UI（OIDC・recharts）は
`npm run build` の成功で検証する。
