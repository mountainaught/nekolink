from collections import deque
import numpy


class VitalStress:

    def __init__(self, buffer_size, bound, inverted=False):
        self.calibration_mode = True

        self.buffer_size = buffer_size
        self.buffer = deque([0.0] * self.buffer_size, maxlen=self.buffer_size)  # ring buffer

        self.baseline_mean = 0
        self.baseline_std = 0

        self.bound = bound
        self.inverted = inverted
        self.stress = 0

    async def calibrate(self):
        self.baseline_mean = numpy.mean(self.buffer)
        self.baseline_std = numpy.std(self.buffer)
        self.calibration_mode = False

    def parse(self, values):
        if not hasattr(values, '__iter__'):
            values = [values]
    
        if not self.calibration_mode:
            current_mean = numpy.mean(values)

            buffer_array = numpy.array(self.buffer)  # avoids doing deque>arr twice
            buffer_mean = numpy.mean(buffer_array)
            buffer_std = numpy.std(buffer_array)

            if buffer_std == 0 or self.baseline_std == 0:
                self.stress = 0
                return

            if self.inverted:
                base = self.baseline_mean - current_mean
                buffer = buffer_mean - current_mean
            else:
                base = current_mean - self.baseline_mean
                buffer = current_mean - buffer_mean

            z_base = min(max(base / self.baseline_std, 0), self.bound) / self.bound
            z_buffer = min(max(buffer / buffer_std, 0), self.bound) / self.bound

            self.stress = (z_base * 0.3) + (z_buffer * 0.7)
        self.buffer.extend(values)

    def get_stress(self):
        return self.stress

    def get_buffer(self):
        return numpy.array(self.buffer)

    @property
    def is_calibrated(self):
        return not self.calibration_mode
