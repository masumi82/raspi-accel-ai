# 設計書：raspi-accel-ai — 加速度センサー × 生成AI × ダッシュボード

- 作成日: 2026-06-29
- ステータス: 承認済み（実装計画フェーズへ）
- スコープ: 自己開発（個人プロジェクト）

## 1. 目的

Raspberry Pi に接続した3軸加速度センサー ADXL345 で動き・振動・傾き・衝撃・落下などを
自律的に監視し、閾値超過/変化を検知したときだけ AWS へイベントを送信する。
クラウド側では生成AI（Amazon Bedrock / Claude Sonnet）がイベントを解釈・分類し、
深刻度と短い自然文の説明を生成して保存する。利用者は Web ダッシュボードで
加速度の時系列グラフと AI 判定を後から振り返る。

「ユーザーが指示を出す」のではなく「ラズパイがセンサー値の変化をトリガーに自律的に
AI へ問い合わせる」点が本システムの中心。

## 2. 確定した方針（意思決定ログ）

| 項目 | 決定 | 補足 |
|---|---|---|
| ユースケース | IoTテレメトリ＋AI解析＋ダッシュボード | 当初「デバイス制御」から、実機（加速度センサーのみ）に合わせて収束 |
| トリガー | センサー値の変化/閾値 | 自律ループ。常時LLM呼び出しはしない |
| エッジ機器 | Raspberry Pi ＋ ADXL345（I2C） | SLR-429(LoRaモデム)は本システムでは使用しない |
| 通信方式 | AWS IoT Core（MQTT over TLS, X.509） | IoTの標準。将来の複数台拡張も容易 |
| AI解析 | Amazon Bedrock / Claude Sonnet | 高精度な状況推論・原因推定を優先 |
| ストレージ | DynamoDB（オンデマンド） | 生波形が必要なら S3 を追加 |
| 可視化 | React + Vite + グラフライブラリ（SPA） | S3静的ホスティング＋CloudFront |
| ダッシュボードAPI | API Gateway(HTTP API) → Lambda → DynamoDB | |
| 認証 | Amazon Cognito（ホステッドUIログイン） | |
| IaC | AWS SAM | 既存 aws_service と同流儀。`sam local` 可 |
| 開発方針 | シミュレータ先行 → 実機差し替え | フルサーバーレス・コスト最適化 |

## 3. アーキテクチャ

```
[Raspberry Pi]                              [AWS Cloud]
 ADXL345 (I2C)
   │ 連続サンプリング
   ▼
 特徴量抽出 + 閾値/変化検知
   │ (閾値超過イベントのみ・クールダウン付き)
   ▼  MQTT over TLS (X.509)
 AWS IoT Core ──► IoT Rule ──► Lambda(analyzer)
                                  │  ├─► Amazon Bedrock (Claude Sonnet) で解釈・分類
                                  │  └─► DynamoDB に保存（特徴量＋AI判定）
                                  └─(失敗時)─► SQS (DLQ)

 [Dashboard]
 ブラウザ ─► CloudFront ─► S3 (静的SPA: React+Vite)
        │
        └─► API Gateway (HTTP API) ─► Lambda(api) ─► DynamoDB
                    ▲
              Cognito (認証)
```

### コンポーネント境界（責務）

- **edge/ (Raspberry Pi エージェント)**: センサー読取・特徴量抽出・閾値検知・MQTT送信。
  クラウドの内部実装を知らず、契約は「イベントJSONを所定トピックへ publish」のみ。
- **cloud/analyzer (Lambda)**: イベント受信 → Bedrock呼出 → DynamoDB保存。
  入力はIoTイベント、出力はDynamoDBレコード。
- **cloud/api (Lambda)**: DynamoDB読取専用のクエリAPI。書き込みはしない。
- **frontend/ (SPA)**: APIを叩いて可視化するだけ。データ生成・保存はしない。

各ユニットは独立してテスト可能（境界が明確）。

## 4. エッジ側（Raspberry Pi）詳細

- 言語: Python 3
- センサー: ADXL345 を I2C 接続（`adafruit-circuitpython-adxl34x` もしくは `smbus2`）
- 通信: AWS IoT Device SDK for Python (v2) で MQTT publish（TLS, X.509クライアント証明書）
- 処理フロー:
  1. 加速度を連続サンプリング（例: 50–100 Hz）
  2. スライディングウィンドウで特徴量を計算
     - 合成加速度の大きさ（magnitude）、ピーク、分散/RMS
     - 傾き角（重力ベクトルからの推定）
     - 自由落下判定（magnitude が ~0g に近い区間）
  3. 閾値・急変検知（振動RMS超過 / 傾き変化 / 衝撃スパイク / 落下 など）
  4. 検知時のみ、イベントメッセージを MQTT publish
- イベントメッセージ（例）:
  ```json
  {
    "device_id": "raspi-01",
    "ts": "2026-06-29T12:34:56.789Z",
    "event_hint": "impact",
    "features": {
      "mag_peak": 3.21, "mag_rms": 1.05, "tilt_deg": 47.2,
      "freefall_ms": 0, "window_ms": 1000
    },
    "samples": [/* 任意: 短い生波形スニペット */]
  }
  ```
- コスト/負荷制御: デバウンス＋クールダウン（例: 同種イベントは30秒に1回まで）
- 耐障害性: オフライン時はローカルにバッファし、再接続後に再送
- セキュリティ: デバイス個別 X.509 証明書、秘密鍵は権限 `600`、
  IoTポリシーは該当トピックへの publish のみ許可（最小権限）

### シミュレータ（開発先行）

実機 ADXL345 を使う前に、合成加速度データ（正常/振動/傾き/衝撃/落下のパターン）を
生成して同じイベント契約で publish する `simulator` を用意する。
これによりクラウド側を実機なしで開発・テスト可能にし、後で実センサー実装に差し替える。
`sensor.py` は「実機ドライバ」と「シミュレータ」を同一インターフェースで切替可能にする。

## 5. AWS取り込み＋AI解析

- **IoT Core**: Thing 登録 / 証明書 / ポリシー。トピック `devices/{deviceId}/events`
- **IoT Rule**: 該当トピックを SELECT → Lambda(analyzer) を起動
- **Lambda(analyzer)** (Python):
  1. イベント受信、入力バリデーション
  2. プロンプト生成（特徴量＋直近コンテキスト）
  3. **Amazon Bedrock（Claude Sonnet）** 呼び出し。構造化出力（JSON）で取得:
     - `label`: normal / vibration / tilt / impact / freefall / transport 等
     - `severity`: low / medium / high
     - `explanation`: 短い自然文（日本語）
  4. **DynamoDB** に保存
  5. 失敗時は SQS(DLQ) へ
- Bedrock 呼び出しはスロットリング対策のリトライ/指数バックオフを実装

### DynamoDB データモデル（events テーブル）

- PK: `deviceId` (S)
- SK: `ts` (S, ISO8601)
- 属性: `event_hint`, `features`(Map), `label`, `severity`, `explanation`,
  `model_id`, `created_at`
- 課金: オンデマンド
- 必要に応じ、最近イベント取得用に GSI（例: `deviceId` + `severity`）を後付け可能

## 6. ダッシュボード（自作軽量Webアプリ）

- フロント: React + Vite + グラフライブラリ（Recharts もしくは Chart.js）
- ホスティング: S3 静的ホスティング ＋ CloudFront（HTTPS）
- API: API Gateway (HTTP API) → Lambda(api) → DynamoDB（読取専用）
  - `GET /events?deviceId=&limit=` 最近イベント一覧
  - `GET /events/{deviceId}/{ts}` イベント詳細
  - （任意）`GET /timeseries?deviceId=&from=&to=` 時系列データ
- 認証: Amazon Cognito ユーザープール（ホステッドUI）。API は Cognito オーソライザで保護
- 表示: 加速度特徴量の時系列グラフ＋イベントごとの AI 判定（ラベル・深刻度・説明文）

## 7. 横断事項

### セキュリティ
- デバイス: X.509 クライアント証明書、最小権限 IoTポリシー
- IAM: Lambda は最小権限（Bedrock invoke / DynamoDB 該当テーブルのみ 等）
- 通信: すべて HTTPS / TLS。HTTP は使わない
- 秘密情報: 環境変数 / SSM Parameter Store。`.env` は Git 除外、`.env.example` を用意
- API: Cognito 認証必須

### コスト最適化
- 常時起動の計算リソースなし（フルサーバーレス）
- LLM 呼び出しはイベント時のみ＋クールダウン
- DynamoDB オンデマンド、S3/CloudFront は低コスト
- 個人利用想定で月額は低水準を見込む

### エラー処理
- Pi: MQTT 再接続、オフラインバッファ
- analyzer: 入力バリデーション、Bedrock リトライ/バックオフ、失敗は DLQ
- api: 入力バリデーション、404/400 の適切な返却

### テスト
- edge: 特徴量抽出・閾値判定の単体テスト（合成データ）、シミュレータでの送信テスト
- cloud: analyzer/api の単体テスト（Bedrock/DynamoDB をモック）、`sam local` でローカル実行
- 結合: シミュレータ → IoT Core → analyzer → DynamoDB → api → フロントの一連動作確認

## 8. リポジトリ構成（予定）

```
raspi-accel-ai/
  edge/                 # Raspberry Pi エージェント (Python)
    agent.py
    sensor.py           # ADXL345実機 + シミュレータを同一IFで
    detector.py         # 特徴量・閾値ロジック
    mqtt_client.py
    simulator.py
    requirements.txt
    tests/
  cloud/                # SAM アプリ
    template.yaml
    src/
      analyzer/         # Lambda: イベント → Bedrock → DynamoDB
      api/              # Lambda: ダッシュボードAPI
    tests/
  frontend/             # ダッシュボード SPA (React + Vite)
    src/
    package.json
  docs/
    superpowers/specs/
  .env.example
  .gitignore
  README.md
```

## 9. スコープ外（YAGNI）

- SLR-429 (LoRa) を用いた長距離無線・分散ノード構成
- 物理アクチュエータによるデバイス制御（GPIO出力）
- 複数台デバイスのフリート管理（設計は拡張容易だが初期実装は1台）
- リアルタイムストリーミング表示（初期はイベント単位の記録・可視化）

## 10. 未確定/実装時に詰める点

- Bedrock の正確なモデルID（Claude Sonnet 系。リージョンのモデルアクセス有効化が前提）
- グラフライブラリの最終選定（Recharts / Chart.js）
- 閾値の初期値（実機/シミュレータで調整）
- サンプリング周波数とウィンドウ幅の最終値
