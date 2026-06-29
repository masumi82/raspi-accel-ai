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
