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
