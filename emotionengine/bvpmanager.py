from collections import deque
from scipy.signal import lfilter
from emotionengine import ppg_findpeaks
import numpy


class BVPManager:

    def __init__(self, hrstress, hrvstress, accmanager):
        # vital managers passed on by emotionengine
        self.hr_manager = hrstress
        self.hrv_manager = hrvstress
        self.acc_manager = accmanager

        # constants for bvp pre-processing
        self.fir_coefs = [0.05, 0.1, 0.2, 0.3, 0.2, 0.1, 0.05]
        self._kalman_p = 1.0
        self._kalman_x = 0.0
        self._kalman_q = 0.01
        self._kalman_r = 0.1

        # leaky integrator constants for holymatlab
        self._leaky = 0.0
        self._prev_leaky = 0.0
        self._last_crossing = 0.0
        self._sample_count = 0

        # 10 second bvp ring buffer for msptd
        self._bvp_buffer = deque([0.0] * 640, maxlen=640)

        self.stress = 0

        self.calibration_mode = True

    async def calibrate(self):
        await self.hr_manager.calibrate()
        await self.hrv_manager.calibrate()
        self.calibration_mode = False

    def _kalman_filter(self, measurement1: float, measurement2: float) -> float:
        """Kalman filter combining two measurements."""
        measurement = (measurement1 + measurement2) / 2.0

        # Prediction
        p_pred = self._kalman_p + self._kalman_q

        # Update
        kalman_gain = p_pred / (p_pred + self._kalman_r)
        self._kalman_x = self._kalman_x + kalman_gain * (measurement - self._kalman_x)
        self._kalman_p = (1 - kalman_gain) * p_pred

        # Adaptive covariance
        diff1 = abs(measurement1 - measurement2)
        if diff1 > 20:
            self._kalman_p = min(self._kalman_p * 1.2, 10.0)
        else:
            self._kalman_p = max(self._kalman_p * 0.95, 0.01)

        return self._kalman_x

    # fast algo for moving - leaky integrator and zero crossings
    def _hr_holymatlab(self, values: list):  # name comes from what empatica called it
        filtered_kalman = lfilter(self.fir_coefs, [1.0], values)
        bvp = numpy.round(-filtered_kalman * 10.0, 2).astype(float)

        hrs = []
        for sample in bvp:
            self._leaky = sample + 0.7 * self._leaky

            if self._prev_leaky >= 0 > self._leaky:
                if self._last_crossing > 0:
                    interval = (self._sample_count - self._last_crossing) / 64.0
                    if interval > 0:
                        hrs.append(60.0 / interval)
                self._last_crossing = self._sample_count

            self._prev_leaky = self._leaky
            self._sample_count += 1

        return hrs

    # slow algo for stationary - msptdfast
    def _hr_msptd(self, values: list):
        peaks, _ = ppg_findpeaks(numpy.array(self._bvp_buffer), sampling_rate=64)

        hr = 0
        hrv = 0

        if len(peaks) > 3:  # need at least 4 peaks for meaningful RMSSD
            recent_peaks = peaks[-5:]  # last 5 peaks = 4 IBIs = 3 diffs
            ibis = numpy.diff(recent_peaks) / 64.0
            diffs = numpy.diff(ibis)
            hrv = numpy.sqrt(numpy.mean(diffs ** 2))
            hr = 60.0 / ibis[-1]

        return hr, hrv

    def parse(self, values: list):
        greens = values[0::2]
        reds = values[1::2]

        filtered_red = lfilter(self.fir_coefs, [1.0], reds)
        weighted = [(red + green * 10.0) / 11.0 for red, green in zip(reds, greens)]
        filtered_weighted = lfilter(self.fir_coefs, [1.0], weighted)
        kalman_out = [self._kalman_filter(f_r, f_w) for f_r, f_w in zip(filtered_red, filtered_weighted)]

        self._bvp_buffer.extend(kalman_out)

        if self.acc_manager.get_moving():
            hrs = self._hr_holymatlab(kalman_out)
            if hrs:
                self.hr_manager.parse(hrs)
        else:
            hr, hrv = self._hr_msptd(kalman_out)
            if hr > 0:
                self.hr_manager.parse(hr)
            if hrv > 0:
                self.hrv_manager.parse(hrv)

        if not self.calibration_mode:
            hr_stress = self.hr_manager.get_stress()
            hrv_stress = self.hrv_manager.get_stress()
            self.stress = hr_stress * 0.6 if self.acc_manager.get_moving() else (hr_stress * 0.4 + hrv_stress * 0.6)

    def get_stress(self):
        return self.stress
