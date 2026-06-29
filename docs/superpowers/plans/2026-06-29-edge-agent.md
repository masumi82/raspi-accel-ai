# Edge Agent Implementation Plan (raspi-accel-ai プラン2/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raspberry Pi 上で ADXL345（またはシミュレータ）の加速度を読み、特徴量抽出・閾値検知（デバウンス/クールダウン付き）を行い、検知イベントを AWS IoT Core へ MQTT(TLS, X.509) で送信するエッジエージェントを構築する。オフライン時はローカルにバッファし再送する。

**Architecture:** 純粋ロジック（特徴量・検知・イベント生成・バッファ）とハードウェア/クラウド依存（実ADXL345ドライバ・AWS IoT MQTT）を分離。ハードウェア/SDK依存は**遅延import**してオフPiでもモジュールがimportでき、テスト可能にする。実機センサーと実MQTT接続は別途実機/クラウドで検証し、ユニットテストはシミュレータ・フェイク・純関数で網羅する。

**Tech Stack:** Python 3、AWS IoT Device SDK v2 (awsiotsdk, 遅延import)、adafruit-circuitpython-adxl34x (遅延import)、boto3（プロビジョニング）。テストは pytest + moto（プロビジョニングのみ）。プロジェクト共有venv `raspi-accel-ai/.venv` を使用。

## Global Constraints

- イベントJSON契約は**クラウド(プラン1)の `validate_event` と一致**させること（必須）:
  - キー: `device_id`(非空str), `ts`(非空str, ISO8601), `event_hint`(下記集合), `features`(dict), 任意 `samples`(list)
  - `event_hint` ∈ `{normal, vibration, tilt, impact, freefall, transport, unknown}`（範囲外は `unknown`）
  - 送信トピック: `devices/{device_id}/events`
- ハードウェア依存（`board`/`busio`/`adafruit_adxl34x`）と SDK 依存（`awscrt`/`awsiot`）は**関数/メソッド内で遅延import**。モジュールのトップレベルでimportしない（オフPiでimport可能に保つ）
- 秘密情報をコード・ログに出さない。証明書・鍵は `certs/`（Git除外済み）。設定は環境変数
- 加速度の単位は **g**（実ドライバは m/s² を 9.80665 で割って g に変換）
- 並びテストは共有venvで実行: `cd raspi-accel-ai && .venv/bin/python -m pytest edge/tests/ -q`（リポジトリルートから。`edge` はパッケージ）
- ファイルは責務単位で分割

## File Structure

```
edge/
  __init__.py            # package marker
  config.py              # AgentConfig.from_env (設定)
  detector.py            # compute_features (純) + EventDetector (閾値+クールダウン, 純)
  event.py               # build_event / to_iso_z / topic_for (契約)
  sensor.py              # Sensor IF + SimulatedSensor + ADXL345Sensor(遅延import)
  buffer.py              # OfflineBuffer (JSONL 永続 + flush)
  mqtt_client.py         # Publisher IF + AwsIotPublisher(遅延import)
  agent.py               # Agent.process_window + build_agent + run loop
  provision.py           # build_device_policy(純) + provision_device(boto3) + CLI
  requirements.txt       # Pi 実行時依存
  README.md
  tests/
    conftest.py
    fakes.py             # FakePublisher (テストダブル, Task 8 で作成)
    test_config.py
    test_detector_features.py
    test_detector_events.py
    test_event.py
    test_sensor.py
    test_buffer.py
    test_mqtt_client.py
    test_agent.py
    test_provision.py
```

---

### Task 1: エッジ雛形と設定 (config.py)

**Files:**
- Create: `edge/__init__.py` (空)
- Create: `edge/requirements.txt`
- Create: `edge/tests/conftest.py`
- Create: `edge/config.py`
- Test: `edge/tests/test_config.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class AgentConfig` (dataclass): `device_id, endpoint, cert_path, key_path, ca_path, sample_rate_hz:int, window_ms:int, sensor_mode, buffer_path`
  - `AgentConfig.from_env(env: dict | None = None) -> AgentConfig`

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/conftest.py`:

```python
import os
import sys

# repo root on path so `import edge.<mod>` resolves
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
```

`edge/tests/test_config.py`:

```python
from edge.config import AgentConfig


def test_from_env_defaults():
    cfg = AgentConfig.from_env({})
    assert cfg.device_id == "raspi-01"
    assert cfg.sample_rate_hz == 50
    assert cfg.window_ms == 1000
    assert cfg.sensor_mode == "rest"
    assert cfg.buffer_path == "buffer.jsonl"


def test_from_env_overrides_and_int_parsing():
    cfg = AgentConfig.from_env(
        {
            "DEVICE_ID": "raspi-09",
            "IOT_ENDPOINT": "abc.iot.ap-northeast-1.amazonaws.com",
            "SAMPLE_RATE_HZ": "100",
            "WINDOW_MS": "500",
            "SENSOR_MODE": "adxl345",
        }
    )
    assert cfg.device_id == "raspi-09"
    assert cfg.endpoint == "abc.iot.ap-northeast-1.amazonaws.com"
    assert cfg.sample_rate_hz == 100
    assert cfg.window_ms == 500
    assert cfg.sensor_mode == "adxl345"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.config'`)

- [ ] **Step 3: 実装を書く**

`edge/__init__.py`:

```python
```

(空)

`edge/requirements.txt`:

```
adafruit-circuitpython-adxl34x>=1.0
awsiotsdk>=1.0
boto3>=1.34
```

`edge/config.py`:

```python
import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    device_id: str
    endpoint: str
    cert_path: str
    key_path: str
    ca_path: str
    sample_rate_hz: int
    window_ms: int
    sensor_mode: str
    buffer_path: str

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(
            device_id=env.get("DEVICE_ID", "raspi-01"),
            endpoint=env.get("IOT_ENDPOINT", ""),
            cert_path=env.get("CERT_PATH", "certs/device.cert.pem"),
            key_path=env.get("KEY_PATH", "certs/device.private.key"),
            ca_path=env.get("CA_PATH", "certs/AmazonRootCA1.pem"),
            sample_rate_hz=int(env.get("SAMPLE_RATE_HZ", "50")),
            window_ms=int(env.get("WINDOW_MS", "1000")),
            sensor_mode=env.get("SENSOR_MODE", "rest"),
            buffer_path=env.get("BUFFER_PATH", "buffer.jsonl"),
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/__init__.py edge/requirements.txt edge/tests/conftest.py edge/config.py edge/tests/test_config.py
git commit -m "feat(edge): scaffold edge package with AgentConfig"
```

---

### Task 2: 特徴量抽出 (compute_features)

**Files:**
- Create: `edge/detector.py`
- Test: `edge/tests/test_detector_features.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `def compute_features(samples, sample_period_ms, freefall_threshold_g=0.3) -> dict`
    - `samples`: list of `(x, y, z)` in g
    - 返却キー: `mag_peak, mag_rms, tilt_deg, freefall_ms, window_ms`
    - `mag_rms` は磁界AC成分（平均からの偏差のRMS、静止時≈0）、`mag_peak` は合成加速度の最大、`tilt_deg` は平均加速度ベクトルと+Z軸の角度、`freefall_ms` は連続低magの最長区間長

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_detector_features.py`:

```python
from edge.detector import compute_features


def test_rest_features():
    f = compute_features([(0.0, 0.0, 1.0)] * 10, sample_period_ms=20)
    assert f["mag_peak"] == 1.0
    assert f["mag_rms"] == 0.0
    assert f["tilt_deg"] == 0.0
    assert f["freefall_ms"] == 0
    assert f["window_ms"] == 200


def test_impact_peak():
    samples = [(0.0, 0.0, 1.0)] * 9 + [(0.0, 0.0, 4.0)]
    f = compute_features(samples, sample_period_ms=20)
    assert f["mag_peak"] == 4.0
    assert f["mag_rms"] > 0.0


def test_tilt_ninety_degrees():
    f = compute_features([(1.0, 0.0, 0.0)] * 5, sample_period_ms=20)
    assert abs(f["tilt_deg"] - 90.0) < 0.01


def test_freefall_run_ms():
    samples = [(0.0, 0.0, 1.0)] * 3 + [(0.0, 0.0, 0.0)] * 4 + [(0.0, 0.0, 1.0)] * 3
    f = compute_features(samples, sample_period_ms=20)
    assert f["freefall_ms"] == 80  # 4 consecutive * 20ms


def test_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        compute_features([], sample_period_ms=20)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_detector_features.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.detector'`)

- [ ] **Step 3: 実装を書く**

`edge/detector.py`:

```python
import math


def compute_features(samples, sample_period_ms, freefall_threshold_g=0.3):
    """samples: list of (x, y, z) in g. Returns a features dict."""
    n = len(samples)
    if n == 0:
        raise ValueError("samples must be non-empty")
    mags = [math.sqrt(x * x + y * y + z * z) for (x, y, z) in samples]
    mean_mag = sum(mags) / n
    mag_peak = max(mags)
    mag_rms = math.sqrt(sum((m - mean_mag) ** 2 for m in mags) / n)
    mean_x = sum(s[0] for s in samples) / n
    mean_y = sum(s[1] for s in samples) / n
    mean_z = sum(s[2] for s in samples) / n
    mean_vec = math.sqrt(mean_x * mean_x + mean_y * mean_y + mean_z * mean_z)
    if mean_vec == 0:
        tilt_deg = 0.0
    else:
        cos_t = max(-1.0, min(1.0, mean_z / mean_vec))
        tilt_deg = math.degrees(math.acos(cos_t))
    longest = run = 0
    for m in mags:
        if m < freefall_threshold_g:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return {
        "mag_peak": round(mag_peak, 4),
        "mag_rms": round(mag_rms, 4),
        "tilt_deg": round(tilt_deg, 2),
        "freefall_ms": longest * sample_period_ms,
        "window_ms": n * sample_period_ms,
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_detector_features.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/detector.py edge/tests/test_detector_features.py
git commit -m "feat(edge): add accelerometer feature extraction"
```

---

### Task 3: イベント検知 (EventDetector)

**Files:**
- Modify: `edge/detector.py`（`EventDetector` を追記）
- Test: `edge/tests/test_detector_events.py`

**Interfaces:**
- Consumes: `compute_features` の返す features dict
- Produces:
  - `class EventDetector` with `__init__(*, impact_peak_g=2.5, vibration_rms_g=0.3, tilt_abs_deg=30.0, freefall_ms=80, cooldown_s=30.0)`
  - `detect(self, features: dict, now: float) -> str | None`（発火時に event_hint、抑制/非該当は None）
  - 分類優先度: freefall > impact > vibration > tilt。`now` は秒。同一 event_hint は `cooldown_s` 未満では再発火しない

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_detector_events.py`:

```python
from edge.detector import EventDetector


def _f(mag_peak=1.0, mag_rms=0.0, tilt_deg=0.0, freefall_ms=0):
    return {
        "mag_peak": mag_peak,
        "mag_rms": mag_rms,
        "tilt_deg": tilt_deg,
        "freefall_ms": freefall_ms,
        "window_ms": 1000,
    }


def test_classify_priority_freefall_over_impact():
    d = EventDetector()
    assert d.detect(_f(mag_peak=5.0, freefall_ms=200), now=0.0) == "freefall"


def test_impact():
    d = EventDetector()
    assert d.detect(_f(mag_peak=3.0), now=0.0) == "impact"


def test_vibration():
    d = EventDetector()
    assert d.detect(_f(mag_rms=0.5), now=0.0) == "vibration"


def test_tilt():
    d = EventDetector()
    assert d.detect(_f(tilt_deg=45.0), now=0.0) == "tilt"


def test_normal_returns_none():
    d = EventDetector()
    assert d.detect(_f(), now=0.0) is None


def test_cooldown_suppresses_then_allows():
    d = EventDetector(cooldown_s=30.0)
    assert d.detect(_f(mag_peak=3.0), now=0.0) == "impact"
    assert d.detect(_f(mag_peak=3.0), now=10.0) is None  # within cooldown
    assert d.detect(_f(mag_peak=3.0), now=40.0) == "impact"  # after cooldown
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_detector_events.py -v`
Expected: FAIL (`ImportError: cannot import name 'EventDetector'`)

- [ ] **Step 3: 実装を書く（detector.py に追記）**

`edge/detector.py` の末尾に追記:

```python
class EventDetector:
    def __init__(
        self,
        *,
        impact_peak_g=2.5,
        vibration_rms_g=0.3,
        tilt_abs_deg=30.0,
        freefall_ms=80,
        cooldown_s=30.0,
    ):
        self.impact_peak_g = impact_peak_g
        self.vibration_rms_g = vibration_rms_g
        self.tilt_abs_deg = tilt_abs_deg
        self.freefall_ms = freefall_ms
        self.cooldown_s = cooldown_s
        self._last_fire = {}

    def _classify(self, features):
        if features["freefall_ms"] >= self.freefall_ms:
            return "freefall"
        if features["mag_peak"] >= self.impact_peak_g:
            return "impact"
        if features["mag_rms"] >= self.vibration_rms_g:
            return "vibration"
        if features["tilt_deg"] >= self.tilt_abs_deg:
            return "tilt"
        return None

    def detect(self, features, now):
        hint = self._classify(features)
        if hint is None:
            return None
        last = self._last_fire.get(hint)
        if last is not None and (now - last) < self.cooldown_s:
            return None
        self._last_fire[hint] = now
        return hint
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_detector_events.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/detector.py edge/tests/test_detector_events.py
git commit -m "feat(edge): add event detector with cooldown"
```

---

### Task 4: イベント生成と契約 (event.py)

**Files:**
- Create: `edge/event.py`
- Test: `edge/tests/test_event.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `ALLOWED_HINTS: set[str]`
  - `def to_iso_z(dt) -> str`（UTC ISO8601, ミリ秒, 末尾 `Z`）
  - `def build_event(device_id, ts_iso, event_hint, features, samples=None) -> dict`（クラウド契約に一致。範囲外hintは `unknown`）
  - `def topic_for(device_id) -> str`（`devices/{device_id}/events`）

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_event.py`:

```python
from datetime import datetime, timezone

from edge.event import build_event, to_iso_z, topic_for, ALLOWED_HINTS


def test_to_iso_z_format():
    dt = datetime(2026, 6, 29, 12, 34, 56, 789000, tzinfo=timezone.utc)
    assert to_iso_z(dt) == "2026-06-29T12:34:56.789Z"


def test_build_event_contract():
    ev = build_event("raspi-01", "2026-06-29T12:34:56.789Z", "impact", {"mag_peak": 4.0})
    assert ev == {
        "device_id": "raspi-01",
        "ts": "2026-06-29T12:34:56.789Z",
        "event_hint": "impact",
        "features": {"mag_peak": 4.0},
    }


def test_build_event_unknown_hint_normalized():
    ev = build_event("d", "t", "explosion", {})
    assert ev["event_hint"] == "unknown"


def test_build_event_includes_samples_when_given():
    ev = build_event("d", "t", "impact", {}, samples=[[0, 0, 1]])
    assert ev["samples"] == [[0, 0, 1]]


def test_allowed_hints_match_cloud_contract():
    assert ALLOWED_HINTS == {
        "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
    }


def test_topic_for():
    assert topic_for("raspi-01") == "devices/raspi-01/events"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_event.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.event'`)

- [ ] **Step 3: 実装を書く**

`edge/event.py`:

```python
from datetime import timezone

ALLOWED_HINTS = {
    "normal", "vibration", "tilt", "impact", "freefall", "transport", "unknown",
}


def to_iso_z(dt):
    return (
        dt.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_event(device_id, ts_iso, event_hint, features, samples=None):
    hint = event_hint if event_hint in ALLOWED_HINTS else "unknown"
    event = {
        "device_id": device_id,
        "ts": ts_iso,
        "event_hint": hint,
        "features": features,
    }
    if samples is not None:
        event["samples"] = samples
    return event


def topic_for(device_id):
    return f"devices/{device_id}/events"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_event.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/event.py edge/tests/test_event.py
git commit -m "feat(edge): add event builder matching cloud contract"
```

---

### Task 5: センサー抽象とシミュレータ (sensor.py)

**Files:**
- Create: `edge/sensor.py`
- Test: `edge/tests/test_sensor.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class Sensor`（IF: `read() -> (x, y, z)` in g）
  - `class SimulatedSensor(Sensor)`: `__init__(mode="rest", seed=0)`、`read()` が mode に応じた合成値を返す（`rest`=(0,0,1)、`tilt`=(1,0,0)、`freefall`=(0,0,0)、`vibration`=ノイズ、`impact`=周期スパイク）
  - `class ADXL345Sensor(Sensor)`: 実機。`board/busio/adafruit_adxl34x` を `__init__` 内で**遅延import**。`read()` は m/s² を g に変換

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_sensor.py`:

```python
from edge.sensor import SimulatedSensor, ADXL345Sensor, Sensor


def test_rest_mode_returns_one_g_up():
    s = SimulatedSensor(mode="rest")
    assert s.read() == (0.0, 0.0, 1.0)


def test_tilt_mode():
    assert SimulatedSensor(mode="tilt").read() == (1.0, 0.0, 0.0)


def test_freefall_mode():
    assert SimulatedSensor(mode="freefall").read() == (0.0, 0.0, 0.0)


def test_vibration_mode_is_bounded_and_seeded():
    s = SimulatedSensor(mode="vibration", seed=42)
    x, y, z = s.read()
    assert -1.0 <= x <= 1.0 and -1.0 <= y <= 1.0 and 0.0 <= z <= 2.0


def test_impact_mode_spikes_periodically():
    s = SimulatedSensor(mode="impact")
    reads = [s.read() for _ in range(50)]
    assert any(z >= 3.0 for (_, _, z) in reads)


def test_adxl345_class_is_a_sensor_and_module_imports_offdevice():
    # Importing the module and referencing the class must not require Pi libs;
    # hardware imports are deferred to __init__.
    assert issubclass(ADXL345Sensor, Sensor)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_sensor.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.sensor'`)

- [ ] **Step 3: 実装を書く**

`edge/sensor.py`:

```python
import random


class Sensor:
    def read(self):
        raise NotImplementedError


class SimulatedSensor(Sensor):
    """Synthetic accelerometer in g. Deterministic given a seed."""

    def __init__(self, mode="rest", seed=0):
        self.mode = mode
        self._rng = random.Random(seed)
        self._t = 0

    def read(self):
        self._t += 1
        if self.mode == "tilt":
            return (1.0, 0.0, 0.0)
        if self.mode == "freefall":
            return (0.0, 0.0, 0.0)
        if self.mode == "vibration":
            j = lambda: (self._rng.random() - 0.5) * 0.8
            return (j(), j(), 1.0 + j())
        if self.mode == "impact":
            if self._t % 50 == 0:
                return (0.0, 0.0, 4.0)
            return (0.0, 0.0, 1.0)
        return (0.0, 0.0, 1.0)


class ADXL345Sensor(Sensor):
    """Real ADXL345 over I2C. Requires Raspberry Pi + adafruit lib.
    Hardware deps are imported lazily so this module imports off-Pi."""

    _G = 9.80665

    def __init__(self):
        import board
        import busio
        import adafruit_adxl34x

        i2c = busio.I2C(board.SCL, board.SDA)
        self._acc = adafruit_adxl34x.ADXL345(i2c)

    def read(self):
        x, y, z = self._acc.acceleration  # m/s^2
        return (x / self._G, y / self._G, z / self._G)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_sensor.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/sensor.py edge/tests/test_sensor.py
git commit -m "feat(edge): add sensor interface, simulator, and ADXL345 driver"
```

---

### Task 6: オフラインバッファ (buffer.py)

**Files:**
- Create: `edge/buffer.py`
- Test: `edge/tests/test_buffer.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class OfflineBuffer`: `__init__(path)`, `add(event: dict)`, `pending() -> list[dict]`, `flush(publish_fn) -> int`
  - `flush` は各イベントを `publish_fn(event)` で送信。例外発生で停止し未送分を残す。全送信成功でファイル削除。送信件数を返す

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_buffer.py`:

```python
from edge.buffer import OfflineBuffer


def test_add_and_pending(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "b.jsonl"))
    buf.add({"a": 1})
    buf.add({"b": 2})
    assert buf.pending() == [{"a": 1}, {"b": 2}]


def test_flush_all_success_clears(tmp_path):
    path = str(tmp_path / "b.jsonl")
    buf = OfflineBuffer(path)
    buf.add({"a": 1})
    buf.add({"b": 2})
    sent = []
    n = buf.flush(lambda ev: sent.append(ev))
    assert n == 2
    assert sent == [{"a": 1}, {"b": 2}]
    assert buf.pending() == []


def test_flush_stops_on_failure_keeps_remainder(tmp_path):
    path = str(tmp_path / "b.jsonl")
    buf = OfflineBuffer(path)
    buf.add({"a": 1})
    buf.add({"b": 2})
    buf.add({"c": 3})

    def publish(ev):
        if ev == {"b": 2}:
            raise ConnectionError("offline")

    n = buf.flush(publish)
    assert n == 1
    assert buf.pending() == [{"b": 2}, {"c": 3}]


def test_pending_empty_when_no_file(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "missing.jsonl"))
    assert buf.pending() == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_buffer.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.buffer'`)

- [ ] **Step 3: 実装を書く**

`edge/buffer.py`:

```python
import json
import os


class OfflineBuffer:
    def __init__(self, path):
        self.path = path

    def add(self, event):
        with open(self.path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def pending(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def flush(self, publish_fn):
        items = self.pending()
        sent = 0
        for i, event in enumerate(items):
            try:
                publish_fn(event)
                sent += 1
            except Exception:
                remainder = items[i:]
                with open(self.path, "w") as f:
                    for r in remainder:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                return sent
        if os.path.exists(self.path):
            os.remove(self.path)
        return sent
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_buffer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/buffer.py edge/tests/test_buffer.py
git commit -m "feat(edge): add offline buffer with flush"
```

---

### Task 7: MQTT パブリッシャ (mqtt_client.py)

**Files:**
- Create: `edge/mqtt_client.py`
- Test: `edge/tests/test_mqtt_client.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `class Publisher`（IF: `connect()`, `publish(topic, payload: dict)`, `disconnect()`）
  - `class AwsIotPublisher(Publisher)`: `__init__(*, endpoint, cert_path, key_path, ca_path, client_id)` は SDK を import しない（構築は軽量）。`awscrt`/`awsiot` は `connect()`/`publish()` 内で**遅延import**

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_mqtt_client.py`:

```python
from edge.mqtt_client import Publisher, AwsIotPublisher


def test_aws_publisher_is_a_publisher():
    assert issubclass(AwsIotPublisher, Publisher)


def test_construction_does_not_import_sdk():
    # Must construct without awsiotsdk installed (deferred import in connect/publish).
    pub = AwsIotPublisher(
        endpoint="x.iot.ap-northeast-1.amazonaws.com",
        cert_path="certs/c.pem",
        key_path="certs/k.pem",
        ca_path="certs/ca.pem",
        client_id="raspi-01",
    )
    assert pub is not None


def test_connect_without_sdk_raises_import_error():
    pub = AwsIotPublisher(
        endpoint="x",
        cert_path="c",
        key_path="k",
        ca_path="ca",
        client_id="raspi-01",
    )
    # awsiotsdk is not installed in the dev venv → connect() should surface ImportError.
    import pytest

    with pytest.raises(ModuleNotFoundError):
        pub.connect()
```

> 注: `test_connect_without_sdk_raises_import_error` は dev venv に `awsiotsdk` 未導入であることを前提に、遅延import設計（接続時まで import しない）を検証する。実機/SDK導入環境ではこのテストは外す/skip すること。Pi 実機では `pip install -r edge/requirements.txt` で SDK を導入し、実接続を別途検証する。

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_mqtt_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.mqtt_client'`)

- [ ] **Step 3: 実装を書く**

`edge/mqtt_client.py`:

```python
import json


class Publisher:
    def connect(self):
        raise NotImplementedError

    def publish(self, topic, payload):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError


class AwsIotPublisher(Publisher):
    """AWS IoT Core MQTT over mTLS. awsiotsdk is imported lazily so this
    module and class import/construct off-device. Validated against real
    IoT Core, not unit-tested."""

    def __init__(self, *, endpoint, cert_path, key_path, ca_path, client_id):
        self._endpoint = endpoint
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_path = ca_path
        self._client_id = client_id
        self._conn = None

    def connect(self):
        from awsiot import mqtt_connection_builder

        self._conn = mqtt_connection_builder.mtls_from_path(
            endpoint=self._endpoint,
            cert_filepath=self._cert_path,
            pri_key_filepath=self._key_path,
            ca_filepath=self._ca_path,
            client_id=self._client_id,
            clean_session=False,
            keep_alive_secs=30,
        )
        self._conn.connect().result()

    def publish(self, topic, payload):
        from awscrt import mqtt

        self._conn.publish(
            topic=topic,
            payload=json.dumps(payload, ensure_ascii=False),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )

    def disconnect(self):
        if self._conn is not None:
            self._conn.disconnect().result()
            self._conn = None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_mqtt_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/mqtt_client.py edge/tests/test_mqtt_client.py
git commit -m "feat(edge): add AWS IoT MQTT publisher with lazy SDK import"
```

---

### Task 8: エージェントループ (agent.py)

**Files:**
- Create: `edge/agent.py`
- Create: `edge/tests/fakes.py`
- Test: `edge/tests/test_agent.py`

**Interfaces:**
- Consumes: `compute_features`, `EventDetector`, `build_event`, `to_iso_z`, `topic_for`, `OfflineBuffer`, `SimulatedSensor`, `ADXL345Sensor`, `AgentConfig`
- Produces:
  - `class Agent`: `__init__(sensor, detector, publisher, buffer, config, *, connected=True)`
  - `process_window(self, samples, now, dt) -> dict | None`：特徴量→検知→（発火時）イベント生成→接続時は publish、失敗/オフライン時は buffer.add。発火時にイベントdict、非発火時 None を返す
  - `build_agent(config: AgentConfig) -> Agent`：config からセンサー/検知器/パブリッシャ/バッファを組み立てるファクトリ（`sensor_mode=="adxl345"` で実機、他はシミュレータ）

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/fakes.py`:

```python
from edge.mqtt_client import Publisher


class FakePublisher(Publisher):
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []
        self.connected = False

    def connect(self):
        self.connected = True

    def publish(self, topic, payload):
        if self.fail:
            raise ConnectionError("offline")
        self.published.append((topic, payload))

    def disconnect(self):
        self.connected = False
```

`edge/tests/test_agent.py`:

```python
from datetime import datetime, timezone

from edge.agent import Agent, build_agent
from edge.detector import EventDetector
from edge.buffer import OfflineBuffer
from edge.config import AgentConfig
from edge.sensor import SimulatedSensor
from edge.tests.fakes import FakePublisher


def _cfg(tmp_path, mode="rest"):
    return AgentConfig.from_env(
        {"SENSOR_MODE": mode, "BUFFER_PATH": str(tmp_path / "buf.jsonl"), "SAMPLE_RATE_HZ": "50"}
    )


def _impact_window():
    return [(0.0, 0.0, 1.0)] * 9 + [(0.0, 0.0, 4.0)]


def test_process_window_publishes_on_event(tmp_path):
    pub = FakePublisher()
    agent = Agent(
        SimulatedSensor(), EventDetector(), pub, OfflineBuffer(str(tmp_path / "b.jsonl")),
        _cfg(tmp_path), connected=True,
    )
    dt = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    ev = agent.process_window(_impact_window(), now=0.0, dt=dt)
    assert ev is not None and ev["event_hint"] == "impact"
    assert len(pub.published) == 1
    topic, payload = pub.published[0]
    assert topic == "devices/raspi-01/events"
    assert payload["event_hint"] == "impact"


def test_process_window_no_event_returns_none(tmp_path):
    pub = FakePublisher()
    agent = Agent(
        SimulatedSensor(), EventDetector(), pub, OfflineBuffer(str(tmp_path / "b.jsonl")),
        _cfg(tmp_path), connected=True,
    )
    dt = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    assert agent.process_window([(0.0, 0.0, 1.0)] * 10, now=0.0, dt=dt) is None
    assert pub.published == []


def test_process_window_buffers_when_offline(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "b.jsonl"))
    agent = Agent(
        SimulatedSensor(), EventDetector(), FakePublisher(), buf, _cfg(tmp_path), connected=False,
    )
    dt = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    ev = agent.process_window(_impact_window(), now=0.0, dt=dt)
    assert ev is not None
    assert len(buf.pending()) == 1


def test_process_window_buffers_when_publish_fails(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "b.jsonl"))
    agent = Agent(
        SimulatedSensor(), EventDetector(), FakePublisher(fail=True), buf, _cfg(tmp_path), connected=True,
    )
    dt = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    agent.process_window(_impact_window(), now=0.0, dt=dt)
    assert len(buf.pending()) == 1


def test_build_agent_uses_simulator_for_non_adxl_mode(tmp_path):
    agent = build_agent(_cfg(tmp_path, mode="vibration"))
    assert isinstance(agent.sensor, SimulatedSensor)
    assert agent.sensor.mode == "vibration"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_agent.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.agent'`)

- [ ] **Step 3: 実装を書く**

`edge/agent.py`:

```python
import time
from datetime import datetime, timezone

from .buffer import OfflineBuffer
from .detector import EventDetector, compute_features
from .event import build_event, to_iso_z, topic_for
from .mqtt_client import AwsIotPublisher
from .sensor import ADXL345Sensor, SimulatedSensor


class Agent:
    def __init__(self, sensor, detector, publisher, buffer, config, *, connected=True):
        self.sensor = sensor
        self.detector = detector
        self.publisher = publisher
        self.buffer = buffer
        self.config = config
        self.connected = connected
        self._period_ms = 1000.0 / config.sample_rate_hz

    def process_window(self, samples, now, dt):
        features = compute_features(samples, self._period_ms)
        hint = self.detector.detect(features, now)
        if hint is None:
            return None
        event = build_event(self.config.device_id, to_iso_z(dt), hint, features)
        topic = topic_for(self.config.device_id)
        try:
            if not self.connected:
                raise ConnectionError("offline")
            self.publisher.publish(topic, event)
        except Exception:
            self.buffer.add(event)
        return event

    def run(self):  # pragma: no cover - real-time loop, validated on device
        window_n = max(1, int(self.config.sample_rate_hz * self.config.window_ms / 1000))
        self.publisher.connect()
        self.connected = True
        try:
            while True:
                samples = [self.sensor.read() for _ in range(window_n)]
                now = time.monotonic()
                self.buffer.flush(lambda ev: self.publisher.publish(topic_for(self.config.device_id), ev))
                self.process_window(samples, now, datetime.now(timezone.utc))
        finally:
            self.publisher.disconnect()


def build_agent(config):
    if config.sensor_mode == "adxl345":
        sensor = ADXL345Sensor()
    else:
        sensor = SimulatedSensor(mode=config.sensor_mode)
    detector = EventDetector()
    publisher = AwsIotPublisher(
        endpoint=config.endpoint,
        cert_path=config.cert_path,
        key_path=config.key_path,
        ca_path=config.ca_path,
        client_id=config.device_id,
    )
    buffer = OfflineBuffer(config.buffer_path)
    return Agent(sensor, detector, publisher, buffer, config, connected=False)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_agent.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/agent.py edge/tests/fakes.py edge/tests/test_agent.py
git commit -m "feat(edge): add agent loop wiring sensor/detector/publisher/buffer"
```

---

### Task 9: デバイスプロビジョニング (provision.py)

**Files:**
- Create: `edge/provision.py`
- Test: `edge/tests/test_provision.py`

**Interfaces:**
- Consumes: なし（boto3 iot クライアントは注入）
- Produces:
  - `def build_device_policy() -> dict`（最小権限IoTポリシー: Connect/Publish を Thing 名スコープに限定する純関数）
  - `def provision_device(iot_client, thing_name, policy_name, cert_dir) -> dict`（thing作成・証明書発行・ポリシー作成/付与・thing付与を行い、証明書/鍵を `cert_dir` に書き出し、`{"certificateArn", "cert_path", "key_path"}` を返す）

- [ ] **Step 1: 失敗するテストを書く**

`edge/tests/test_provision.py`:

```python
import json
import os

import boto3
from moto import mock_aws

from edge.provision import build_device_policy, provision_device


def test_build_device_policy_scopes_to_thing():
    pol = build_device_policy()
    assert pol["Version"] == "2012-10-17"
    actions = [s["Action"] for s in pol["Statement"]]
    assert "iot:Connect" in actions
    assert "iot:Publish" in actions
    # publish is scoped to the device's own events topic via a policy variable
    pub = next(s for s in pol["Statement"] if s["Action"] == "iot:Publish")
    assert "${iot:Connection.Thing.ThingName}" in pub["Resource"]
    assert "/events" in pub["Resource"]


@mock_aws
def test_provision_device_creates_thing_cert_and_files(tmp_path):
    client = boto3.client("iot", region_name="ap-northeast-1")
    result = provision_device(
        client, thing_name="raspi-01", policy_name="raspi-accel-ai-device",
        cert_dir=str(tmp_path),
    )
    # thing exists
    assert client.describe_thing(thingName="raspi-01")["thingName"] == "raspi-01"
    # certificate arn returned and files written
    assert result["certificateArn"]
    assert os.path.exists(result["cert_path"])
    assert os.path.exists(result["key_path"])
    # principal attached to thing
    principals = client.list_thing_principals(thingName="raspi-01")["principals"]
    assert len(principals) == 1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_provision.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'edge.provision'`)

- [ ] **Step 3: 実装を書く**

`edge/provision.py`:

```python
import json
import os


def build_device_policy():
    """Least-privilege IoT policy: a device may connect as its own client id
    and publish only to its own events topic, scoped via policy variables."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": "arn:aws:iot:*:*:client/${iot:Connection.Thing.ThingName}",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Publish",
                "Resource": "arn:aws:iot:*:*:topic/devices/${iot:Connection.Thing.ThingName}/events",
            },
        ],
    }


def _ensure_policy(iot_client, policy_name):
    try:
        iot_client.get_policy(policyName=policy_name)
    except iot_client.exceptions.ResourceNotFoundException:
        iot_client.create_policy(
            policyName=policy_name,
            policyDocument=json.dumps(build_device_policy()),
        )


def provision_device(iot_client, thing_name, policy_name, cert_dir):
    iot_client.create_thing(thingName=thing_name)
    keys = iot_client.create_keys_and_certificate(setAsActive=True)
    cert_arn = keys["certificateArn"]
    _ensure_policy(iot_client, policy_name)
    iot_client.attach_policy(policyName=policy_name, target=cert_arn)
    iot_client.attach_thing_principal(thingName=thing_name, principal=cert_arn)

    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "device.cert.pem")
    key_path = os.path.join(cert_dir, "device.private.key")
    with open(cert_path, "w") as f:
        f.write(keys["certificatePem"])
    with open(key_path, "w") as f:
        f.write(keys["keyPair"]["PrivateKey"])
    os.chmod(key_path, 0o600)
    return {"certificateArn": cert_arn, "cert_path": cert_path, "key_path": key_path}


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import boto3

    parser = argparse.ArgumentParser(description="Provision an IoT device (thing + cert + policy).")
    parser.add_argument("--thing-name", default="raspi-01")
    parser.add_argument("--policy-name", default="raspi-accel-ai-device")
    parser.add_argument("--cert-dir", default="certs")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()
    client = boto3.client("iot", region_name=args.region)
    out = provision_device(client, args.thing_name, args.policy_name, args.cert_dir)
    print(f"certificateArn: {out['certificateArn']}")
    print(f"cert: {out['cert_path']}  key: {out['key_path']}")
    print("Download the Amazon Root CA1 to certs/AmazonRootCA1.pem before connecting.")
```

> 注: moto が `create_keys_and_certificate` / `attach_policy` / `attach_thing_principal` のいずれかを未サポートでテストが失敗する場合は、未サポート箇所を `provision_device` から切り出さず、当該アサーションのみを BLOCKED として報告すること（実装は実IoTで検証する）。

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/test_provision.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add edge/provision.py edge/tests/test_provision.py
git commit -m "feat(edge): add device provisioning (thing/cert/policy)"
```

---

### Task 10: エッジ README とフルスイート確認

**Files:**
- Create: `edge/README.md`

**Interfaces:**
- Consumes: 全タスク
- Produces: 実行/プロビジョニング/設定手順（コードなし）

- [ ] **Step 1: フルスイートを実行（全タスク緑を確認）**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai && .venv/bin/python -m pytest edge/tests/ -q`
Expected: PASS（全テスト緑。概ね 37 件前後）

- [ ] **Step 2: README を作成**

`edge/README.md`:

````markdown
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
````

- [ ] **Step 3: Commit**

```bash
git add edge/README.md
git commit -m "docs(edge): add edge agent run and provisioning guide"
```

---

## Self-Review

**1. Spec coverage（design spec §4 / §7 → タスク）**
- センサー読取 ADXL345 I2C → Task 5（実ドライバ, 遅延import）
- 特徴量（magnitude/peak/RMS/tilt/freefall）→ Task 2
- 閾値・急変検知 → Task 3（分類 + クールダウン）
- 検知時のみ送信 + クールダウン → Task 3 + Task 8（process_window は発火時のみ publish）
- MQTT publish (TLS, X.509) → Task 7（AwsIotPublisher）
- イベントメッセージ契約（cloud一致）→ Task 4 + Global Constraints
- オフラインバッファ + 再送 → Task 6 + Task 8（run の flush）
- X.509 証明書・最小権限ポリシー → Task 9（provision + build_device_policy）
- シミュレータ先行 → Task 5（SimulatedSensor）+ Task 8（build_agent 切替）
- 設定（device_id/endpoint/cert/閾値）→ Task 1（AgentConfig）
- セキュリティ（鍵600・certs gitignore・秘密非出力）→ Task 9（chmod 600）+ 既存 .gitignore

**2. Placeholder scan:** TBD/「適切に処理」等なし。各コードステップに実コードあり。`# pragma: no cover` は実時間ループ/CLI（テスト対象外の実機部分）に限定。

**3. Type consistency:** イベントdictのキー（device_id/ts/event_hint/features/samples）が Task 4/8 と cloud契約で一致。`compute_features` の返すキー（mag_peak/mag_rms/tilt_deg/freefall_ms/window_ms）を Task 3 detect と Task 2 が共有。`Publisher.publish(topic, payload)` 署名が Task 7/8/fakes で一致。`topic_for` は event.py に単一定義。

**意図的に実機/クラウド検証へ回すもの（ユニット非対象）:** 実 ADXL345 読取（Task 5, 要ハード）、実 MQTT 接続/送信（Task 7, 要SDK+証明書）、`Agent.run` 実時間ループ（Task 8）。これらは README の実機手順で検証する。
