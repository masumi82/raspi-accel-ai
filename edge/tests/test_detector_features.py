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
