import math
import logging

log = logging.getLogger(__name__)


class TailController:
    """
    3-cable continuum tail controller.

    Servo positions on base (clockwise from top):
      blue: 300°  red: 60°  yellow: 180°

    x/y coords are -1.0 to 1.0, viewed from behind.
    Servo range: 0° = loose, 270° = full pull.
    """

    _DIRS = {
        "blue":   150.0,
        "red":     30.0,
        "yellow": 270.0,
    }
    _MAX_ANGLE = 270.0
    _SCALE     = _MAX_ANGLE  # normalisation factor for x/y ↔ servo space

    def __init__(self, blue_ch, red_ch, yellow_ch):
        self._channels = {"blue": blue_ch, "red": red_ch, "yellow": yellow_ch}
        self.pca       = None
        self.servos    = {}
        self.initialized = False

        self._vecs    = {k: self._to_vec(d) for k, d in self._DIRS.items()}
        self._offsets = {"blue": 0,   "red": 0,   "yellow": 0}
        self._scales  = {"blue": 1.0, "red": 1.0, "yellow": 1.0}

    def initialize(self):
        try:
            import board
            from adafruit_pca9685 import PCA9685
            from adafruit_motor import servo as servo_mod

            i2c      = board.I2C()
            self.pca = PCA9685(i2c)
            self.pca.frequency = 50

            self.servos = {
                name: servo_mod.Servo(
                    self.pca.channels[ch],
                    actuation_range=270,
                    min_pulse=500,
                    max_pulse=2500,
                )
                for name, ch in self._channels.items()
            }
            self.initialized = True
            return True, "PCA9685 connected, servos ready"
        except Exception as e:
            return False, str(e)

    def calibrate(self, offsets=None, scales=None):
        """
        offsets: {"blue": 20, ...}  — added to final servo angle
        scales:  {"blue": 1.2, ...} — multiplier per servo
        """
        if offsets:
            self._offsets.update(offsets)
        if scales:
            self._scales.update(scales)

    @property
    def calibration(self):
        return {"offsets": dict(self._offsets), "scales": dict(self._scales)}

    # ------------------------------------------------------------------ maths

    @staticmethod
    def _to_vec(deg):
        rad = math.radians(deg)
        return (math.cos(rad), math.sin(rad))

    @staticmethod
    def _solve(x, y, d1, d2):
        det = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(det) < 1e-9:
            return 0.0, 0.0
        return (x * d2[1] - y * d2[0]) / det, (d1[0] * y - d1[1] * x) / det

    def _clamp(self, name, val):
        scaled = round(val * self._scales[name] + self._offsets[name])
        return max(0, min(int(self._MAX_ANGLE), scaled))

    # ------------------------------------------------------------------ I/O

    def _write(self, b, r, y):
        if not self.initialized:
            return
        vals = {
            "blue":   self._clamp("blue",   b),
            "red":    self._clamp("red",    r),
            "yellow": self._clamp("yellow", y),
        }
        try:
            for name, v in vals.items():
                self.servos[name].angle = v
            log.debug("servos: %s", vals)
        except ValueError:
            log.warning("servo at angle limit")

    # ------------------------------------------------------------------ API

    def forward(self, b, r, y):
        """Servo values → (x, y) tip position in -1..1 space."""
        v = self._vecs
        x  = b * v["blue"][0] + r * v["red"][0] + y * v["yellow"][0]
        yp = b * v["blue"][1] + r * v["red"][1] + y * v["yellow"][1]
        return (x / self._SCALE, yp / self._SCALE)

    def inverse(self, x, y):
        """(x, y) tip position → (blue, red, yellow) servo values."""
        if x == 0 and y == 0:
            return (0, 0, 0)

        sx = x * self._SCALE
        sy = y * self._SCALE

        angle = math.degrees(math.atan2(sy, sx)) % 360
        v = self._vecs

        if 30 <= angle < 150:
            b, r  = self._solve(sx, sy, v["blue"], v["red"])
            yv    = 0.0
        elif 150 <= angle < 270:
            b, yv = self._solve(sx, sy, v["blue"], v["yellow"])
            r     = 0.0
        else:
            r, yv = self._solve(sx, sy, v["red"], v["yellow"])
            b     = 0.0

        return (b, r, yv)

    def move(self, b, r, y):
        """Write raw servo values directly (calibration still applied)."""
        self._write(b, r, y)

    def move_to(self, x, y):
        """Move tail tip to (x, y) in -1..1 space."""
        self._write(*self.inverse(x, y))

    def where(self):
        """Return estimated current tip position."""
        if not self.initialized:
            return None
        angles = (self.servos[k].angle or 0 for k in ("blue", "red", "yellow"))
        return self.forward(*angles)

    def cleanup(self):
        self.move(0, 0, 0)
        self.pca.deinit()