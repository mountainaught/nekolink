import asyncio
from .bvpmanager import BVPManager
from .accmanager import ACCManager
from .vital import VitalStress
import math
import numpy

class EmotionEngine:

    def __init__(self):
        self.eda = VitalStress(buffer_size=40, bound=2.0)
        self.hr = VitalStress(buffer_size=30, bound=2.0)
        self.hrv = VitalStress(buffer_size=20, bound=2.0, inverted=True)

        self.acc = ACCManager(threshold=0.5)
        self.bvp = BVPManager(self.hr, self.hrv, self.acc)

        self.stress = 0

    async def calibrate(self):
        await asyncio.sleep(60)
        await self.eda.calibrate()
        await self.bvp.calibrate()

    def update_stress(self):
        bvp_stress = self.bvp.get_stress()
        eda_stress = self.eda.get_stress()

        if self.acc.get_moving():
            self.stress = bvp_stress * 0.3 + eda_stress * 0.7
        else:
            self.stress = bvp_stress * 0.6 + eda_stress * 0.4
        return self.stress

    def eda_parser(self):
        return self.eda.parse

    def bvp_parser(self):
        return self.bvp.parse

    def acc_parser(self):
        return self.acc.parse

    def get_buffers(self):
        return self.eda.get_buffer(), self.hr.get_buffer(), self.hrv.get_buffer()

    @property
    def hr_stress(self):
        return self.hr.get_stress()

    @property
    def hrv_stress(self):
        return self.hrv.get_stress()

    @property
    def eda_stress(self):
        return self.eda.get_stress()

    @property
    def bvp_stress(self):
        return self.bvp.stress

    @property
    def is_moving(self):
        return self.acc.get_moving()

    @property
    def is_calibrated(self):
        return not self.bvp.calibration_mode

    @property
    def current_hr(self):
        buf = self.hr.get_buffer()
        return float(buf[-1]) if len(buf) > 0 and buf[-1] != 0 else None

    @property
    def current_hrv(self):
        buf = self.hrv.get_buffer()
        return float(buf[-1]) if len(buf) > 0 and buf[-1] != 0 else None
    
    @property
    def current_eda(self):
        buf = self.eda.get_buffer()
        nonzero = [v for v in buf[-5:] if v != 0]
        return float(nonzero[-1]) if nonzero else None

    @property
    def acc_variance(self):
        if len(self.acc.buffer) > 0:
            return float(numpy.var(self.acc.buffer))
        return 0.0

    def map(self, t):
        A = 1.0 - self.stress
        omega = 2 * math.pi * (0.5 + self.hr.get_stress() * 2) # 0.5hz = low hr, 2.5hz = high hr
        k = 1.0 - self.stress

        x = A * (
                math.sin(omega * t) +
                k * math.sin(3 * omega * t) / 3 +
                k * math.sin(5 * omega * t) / 5
        )

        return max(-1.0, min(1.0, x))
