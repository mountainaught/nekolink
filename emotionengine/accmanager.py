from collections import deque
import numpy


class ACCManager:
    def __init__(self, threshold=0.01):
        self.buffer = deque(maxlen=32)
        self.threshold = threshold
        self._moving = False

    def parse(self, values):
        for x, y, z in values:
            mag = (x ** 2 + y ** 2 + z ** 2) ** 0.5
            self.buffer.append(mag)

        if len(self.buffer) == 32:
            self._moving = numpy.var(self.buffer) > self.threshold

    def get_moving(self):
        return self._moving

    @property
    def variance(self):
        if len(self.buffer) == 32:
            return float(numpy.var(self.buffer))
        return 0.0
