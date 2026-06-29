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
