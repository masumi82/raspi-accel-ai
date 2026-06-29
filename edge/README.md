# raspi-accel-ai edge agent

Raspberry Pi 上で ADXL345 を読み、特徴量抽出・閾値検知し、検知イベントを
AWS IoT Core (MQTT, X.509) へ送信するエッジエージェント。オフライン時は
ローカルにバッファして再送する。

## 構成
- `config.py` 設定（環境変数）/ `detector.py` 特徴量+検知 / `event.py` イベント契約
- `sensor.py` センサー（実機 ADXL345 / シミュレータ）/ `buffer.py` オフラインバッファ
- `mqtt_client.py` AWS IoT パブリッシャ / `agent.py` メインループ / `provision.py` 端末プロビジョニング

## テスト（開発機, 共有venv）
```bash
cd /home/m-horiuchi/persol_ws/raspi-accel-ai
.venv/bin/python -m pytest edge/tests/ -q
```
注: `test_mqtt_client.py::test_connect_without_sdk_raises_import_error` は dev venv に
awsiotsdk が無い前提で遅延import設計を検証する。SDK 導入環境では skip すること。

## デバイスプロビジョニング（AWS 資格情報のある環境で1回）
```bash
python -m edge.provision --thing-name raspi-01 --region ap-northeast-1 --cert-dir certs
# 出力された証明書/鍵が certs/ に保存される。Amazon Root CA1 を取得:
curl -s https://www.amazontrust.com/repository/AmazonRootCA1.pem -o certs/AmazonRootCA1.pem
```

## Raspberry Pi での実行

> 重要: DEVICE_ID は provision で作成した --thing-name と必ず一致させること。IoTポリシーは ${iot:Connection.Thing.ThingName} でスコープされ、不一致だと接続/発行が拒否される。

```bash
pip install -r edge/requirements.txt   # adafruit-circuitpython-adxl34x, awsiotsdk
export IOT_ENDPOINT="$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text)"
export DEVICE_ID=raspi-01
export SENSOR_MODE=adxl345     # シミュレータは rest/vibration/tilt/impact/freefall
export CERT_PATH=certs/device.cert.pem KEY_PATH=certs/device.private.key CA_PATH=certs/AmazonRootCA1.pem
python -c "from edge.agent import build_agent; from edge.config import AgentConfig; build_agent(AgentConfig.from_env()).run()"
```

## 開発機でのシミュレーション実行
`SENSOR_MODE` に `impact` 等を指定し、`IOT_ENDPOINT`/証明書を設定すれば実 IoT Core へ
シミュレートイベントを送信できる（クラウド側プラン1の結合確認に利用）。

## イベント契約（クラウドと一致）
トピック `devices/{device_id}/events`、ペイロード:
`{"device_id","ts","event_hint","features",("samples")}`、
`event_hint` ∈ normal/vibration/tilt/impact/freefall/transport/unknown。
