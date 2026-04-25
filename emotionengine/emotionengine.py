import asyncio
from emotionengine import BVPManager, ACCManager, VitalStress
import math

class EmotionEngine:

    def __init__(self):
        self.eda = VitalStress(buffer_size=40, bound=2.0)
        self.hr = VitalStress(buffer_size=30, bound=2.0)
        self.hrv = VitalStress(buffer_size=20, bound=2.0, inverted=True)

        self.acc = ACCManager(threshold=0.01)
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
