import math
import board
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

class TailController:
    """
    3-cable continuum tail controller
    
    servo positions on base (clockwise from top):
    - blue:   300° (upper-left)
    - red:    60°  (upper-right)
    - yellow: 180° (bottom)
    
    x/y coords are -1.0 to 1.0

    params are channel value for blue, red, yellow servo
    """

    _BLUE_DIR   = 150.0
    _RED_DIR    = 30.0
    _YELLOW_DIR = 270.0

    _SCALE = 180.0  # internal servo unit range

    def __init__(self, blue_ch, red_ch, yellow_ch):
        i2c = board.I2C()
        self.pca = PCA9685(i2c)
        self.pca.frequency = 50

        self.blue   = servo.Servo(self.pca.channels[blue_ch], min_pulse=500, max_pulse=2500)
        self.red    = servo.Servo(self.pca.channels[red_ch], min_pulse=500, max_pulse=2500)
        self.yellow = servo.Servo(self.pca.channels[yellow_ch], min_pulse=500, max_pulse=2500)

        self._bdir = self._to_vec(self._BLUE_DIR)
        self._rdir = self._to_vec(self._RED_DIR)
        self._ydir = self._to_vec(self._YELLOW_DIR)

        # calibration
        self._offsets = [0, 0, 0]   # added to final servo values (b, r, y)
        self._scales  = [1.0, 1.0, 1.0]  # multiplier per servo

    # ── calibration ──────────────────────────────────────────────

    def calibrate(self, b_offset=0, r_offset=0, y_offset=0,
                        b_scale=1.0, r_scale=1.0, y_scale=1.0):
        """
        offsets: added to final servo value before sending
                 e.g. theory says 100 but reality needs 120 → b_offset=20
        scales:  multiplier if one servo pulls harder/weaker than others
                 e.g. blue is weaker → b_scale=1.2 to compensate
        """
        self._offsets = [b_offset, r_offset, y_offset]
        self._scales  = [b_scale,  r_scale,  y_scale]

    def get_calibration(self):
        """print current calibration so you can save it"""
        b, r, y = self._offsets
        bs, rs, ys = self._scales
        print(f"offsets → b:{b}  r:{r}  y:{y}")
        print(f"scales  → b:{bs} r:{rs} y:{ys}")
        print(f"tail.calibrate(b_offset={b}, r_offset={r}, y_offset={y},")
        print(f"               b_scale={bs}, r_scale={rs}, y_scale={ys})")

    # ── math helpers ─────────────────────────────────────────────

    @staticmethod
    def _to_vec(deg):
        rad = math.radians(deg)
        return (math.cos(rad), math.sin(rad))

    @staticmethod
    def _solve(x, y, d1, d2):
        det = d1[0]*d2[1] - d1[1]*d2[0]
        if abs(det) < 1e-9:
            return 0.0, 0.0
        s1 = (x*d2[1] - y*d2[0]) / det
        s2 = (d1[0]*y - d1[1]*x) / det
        return s1, s2

    def _clamp(self, v):
        return max(0, min(180, round(v)))

    def _apply_calibration(self, b, r, y):
        """apply scale then offset, then clamp"""
        b = self._clamp(b * self._scales[0] + self._offsets[0])
        r = self._clamp(r * self._scales[1] + self._offsets[1])
        y = self._clamp(y * self._scales[2] + self._offsets[2])
        return (b, r, y)

    # ── main interface ────────────────────────────────────────────

    def forward(self, b, r, y):
        """raw servo values (0-180) → (x, y) in -1.0 to 1.0"""
        x  = b*self._bdir[0] + r*self._rdir[0] + y*self._ydir[0]
        yp = b*self._bdir[1] + r*self._rdir[1] + y*self._ydir[1]
        return (x / self._SCALE, yp / self._SCALE)

    def inverse(self, x, y):
        """(x, y) in -1.0 to 1.0 → calibrated (b, r, y) servo values"""
        # scale up to servo units
        x  = x * self._SCALE
        y  = y * self._SCALE

        if x == 0 and y == 0:
            return (0, 0, 0)

        angle = math.degrees(math.atan2(y, x)) % 360

        if 30 <= angle < 150:       # upper region - blue + red
            b, r  = self._solve(x, y, self._bdir, self._rdir)
            yv    = 0.0
        elif 150 <= angle < 270:    # lower-left - blue + yellow
            b, yv = self._solve(x, y, self._bdir, self._ydir)
            r     = 0.0
        else:                       # lower-right - red + yellow
            r, yv = self._solve(x, y, self._rdir, self._ydir)
            b     = 0.0

        return self._apply_calibration(b, r, yv)

    def move(self, state):
        """move with raw (b, r, y) servo values, still applies calibration"""
        state = self._apply_calibration(*state)
        try:
            self.blue.angle   = state[0]
            self.red.angle    = state[1]
            self.yellow.angle = state[2]
            print(f"b{state[0]} r{state[1]} y{state[2]}")
        except ValueError:
            print("servo at angle limit")

    def move_to(self, x, y):
        """move tip to (x, y) in -1.0 to 1.0"""
        state = self.inverse(x, y)
        try:
            self.blue.angle   = state[0]
            self.red.angle    = state[1]
            self.yellow.angle = state[2]
            print(f"b{state[0]} r{state[1]} y{state[2]}")
        except ValueError:
            print("servo at angle limit")

    def where(self):
        """returns current estimated tip position in -1.0 to 1.0"""
        return self.forward(self.blue.angle or 0,
                           self.red.angle  or 0,
                           self.yellow.angle or 0)
    
    def cleanup(self):
        """called when nekolink script is terminated"""
        self.move((0,0,0))
        self.pca.deinit()