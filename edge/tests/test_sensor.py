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
