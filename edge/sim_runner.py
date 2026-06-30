"""Send simulated accelerometer events to AWS IoT Core.

Cycles through scenarios (impact / tilt / freefall / vibration) and publishes
each as an event, so the cloud pipeline and dashboard can be exercised without
real ADXL345 hardware.

Usage (run from the repo root with the edge venv):
  IOT_ENDPOINT=... DEVICE_ID=raspi-01 python -m edge.sim_runner --count 8 --interval 2
  # --count 0 runs forever (NOTE: each event invokes Bedrock => ongoing cost).
"""

import argparse
import random
import time
from datetime import datetime, timezone

from edge.agent import Agent
from edge.buffer import OfflineBuffer
from edge.config import AgentConfig
from edge.detector import EventDetector
from edge.mqtt_client import AwsIotPublisher
from edge.sensor import SimulatedSensor

MODES = ["impact", "tilt", "freefall", "vibration"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=0,
                        help="number of events to attempt (0 = run forever)")
    parser.add_argument("--interval", type=float, default=60.0,
                        help="seconds between events")
    args = parser.parse_args()

    cfg = AgentConfig.from_env()
    publisher = AwsIotPublisher(
        endpoint=cfg.endpoint, cert_path=cfg.cert_path, key_path=cfg.key_path,
        ca_path=cfg.ca_path, client_id=cfg.device_id,
    )
    publisher.connect()
    # cooldown 0: this runner paces events itself, so don't suppress them.
    agent = Agent(SimulatedSensor(), EventDetector(cooldown_s=0.0), publisher,
                  OfflineBuffer(cfg.buffer_path), cfg, connected=True)
    window_n = max(1, int(cfg.sample_rate_hz * cfg.window_ms / 1000))

    i = 0
    try:
        while args.count == 0 or i < args.count:
            mode = MODES[i % len(MODES)]
            sensor = SimulatedSensor(mode=mode, seed=random.randint(0, 1_000_000))
            samples = [sensor.read() for _ in range(window_n)]
            event = agent.process_window(samples, now=float(i), dt=datetime.now(timezone.utc))
            sent = event["event_hint"] if event else "none"
            print(f"[{datetime.now(timezone.utc).isoformat()}] mode={mode} sent={sent}", flush=True)
            i += 1
            if args.count and i >= args.count:
                break
            time.sleep(args.interval)
    finally:
        publisher.disconnect()


if __name__ == "__main__":
    main()
