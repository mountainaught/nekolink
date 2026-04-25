import numpy as np
import scipy.signal


def ppg_findpeaks(
        signal,
        sampling_rate=1000,
        win_durn=6,
):
    """Implementation of MSPTDfastv2, as described in:
    Charlton, P. H. et al. (2025). The MSPTDfast photoplethysmography beat detection algorithm: design, benchmarking,
    and open-source distribution. Physiological Measurement, 46, 035002, doi:10.1088/1361-6579/adb89e

    Also, when win_durn=8, this is an implementation of MSPTDfastv1, as described in:
    Charlton, P. H. et al. (2024). MSPTDfast: An Efficient Photoplethysmography Beat Detection Algorithm. Proc CinC.
    """

    # Inner functions

    def find_m_max(x, N, max_scale, m_max):
        """Find local maxima scalogram for peaks"""

        for k in range(1, max_scale + 1):  # scalogram scales
            for i in range(k + 2, N - k + 2):
                if x[i - 2] > x[i - k - 2] and x[i - 2] > x[i + k - 2]:
                    m_max[k - 1, i - 2] = True

        return m_max

    def find_m_min(x, N, max_scale, m_min):
        """Find local minima scalogram for onsets"""

        for k in range(1, max_scale + 1):  # scalogram scales
            for i in range(k + 2, N - k + 2):
                if x[i - 2] < x[i - k - 2] and x[i - 2] < x[i + k - 2]:
                    m_min[k - 1, i - 2] = True

        return m_min

    def find_lms_using_msptd_approach(max_scale, x, options):
        """Find local maxima (or minima) scalogram(s) using the
        MSPTD approach
        """

        # Setup
        N = len(x)

        # Find local maxima scalogram (if required)
        if options["find_pks"]:
            m_max = np.full((max_scale, N), False)  # matrix for maxima
            m_max = find_m_max(x, N, max_scale, m_max)
        else:
            m_max = None

        # Find local minima scalogram (if required)
        if options["find_trs"]:
            m_min = np.full((max_scale, N), False)  # matrix for minima
            m_min = find_m_min(x, N, max_scale, m_min)
        else:
            m_min = None

        return m_max, m_min

    def downsample(win_sig, ds_factor):
        """Downsamples signal by picking out every nth sample, where n is
        specified by ds_factor
        """

        return win_sig[::ds_factor]

    def detect_peaks_and_onsets_using_msptd(signal, fs, options):
        """Detect peaks and onsets in a PPG signal using a modified MSPTD approach
        (where the modifications are those specified in Charlton et al. 2024)
        """

        # Setup
        N = len(signal)
        L = int(np.ceil(N / 2) - 1)

        # Step 0: Don't calculate scales outside the range of plausible HRs

        plaus_hr_hz = np.array(options["plaus_hr_bpm"]) / 60  # in Hz
        init_scales = np.arange(1, L + 1)
        durn_signal = len(signal) / fs
        init_scales_fs = (L / init_scales) / durn_signal
        if options["use_reduced_lms_scales"]:
            init_scales_inc_log = init_scales_fs >= plaus_hr_hz[0]
        else:
            init_scales_inc_log = np.ones_like(init_scales_fs, dtype=bool)  # DIDN"T FULLY UNDERSTAND

        max_scale_index = np.where(init_scales_inc_log)[0]  # DIDN"T FULLY UNDERSTAND THIS AND NEXT FEW LINES
        if max_scale_index.size > 0:
            max_scale = max_scale_index[-1] + 1  # Add 1 to convert from 0-based to 1-based index
        else:
            max_scale = None  # Or handle the case where no scales are valid

        # Step 1: calculate local maxima and local minima scalograms

        # - detrend
        x = scipy.signal.detrend(signal, type="linear")

        # - populate LMS matrices
        [m_max, m_min] = find_lms_using_msptd_approach(max_scale, x, options)

        # Step 2: find the scale with the most local maxima (or local minima)

        # - row-wise summation (i.e. sum each row)
        if options["find_pks"]:
            gamma_max = np.sum(m_max, axis=1)  # the "axis=1" option makes it row-wise
        if options["find_trs"]:
            gamma_min = np.sum(m_min, axis=1)
        # - find scale with the most local maxima (or local minima)
        if options["find_pks"]:
            lambda_max = np.argmax(gamma_max)
        if options["find_trs"]:
            lambda_min = np.argmax(gamma_min)

        # Step 3: Use lambda to remove all elements of m for which k>lambda
        first_scale_to_include = np.argmax(init_scales_inc_log)
        if options["find_pks"]:
            m_max = m_max[first_scale_to_include: lambda_max + 1, :]
        if options["find_trs"]:
            m_min = m_min[first_scale_to_include: lambda_min + 1, :]

        # Step 4: Find peaks (and onsets)
        # - column-wise summation
        if options["find_pks"]:
            m_max_sum = np.sum(m_max == False, axis=0)
            peaks = np.where(m_max_sum == 0)[0].astype(int)
        else:
            peaks = []

        if options["find_trs"]:
            m_min_sum = np.sum(m_min == False, axis=0)
            onsets = np.where(m_min_sum == 0)[0].astype(int)
        else:
            onsets = []

        return peaks, onsets

    # ~~~ Main function ~~~

    # Specify settings
    # - version: optimal selection (CinC 2024)
    options = {
        "find_trs": False,  # whether or not to find onsets
        "find_pks": True,  # whether or not to find peaks
        "do_ds": True,  # whether or not to do downsampling
        "ds_freq": 20,  # the target downsampling frequency
        "use_reduced_lms_scales": True,  # whether or not to reduce the number of scales (default 30 bpm)
        "win_len": win_durn,
        # duration of individual windows for analysis (8 secs for MSPTDfastv1; 6 secs for MSPTDfastv2)
        "win_overlap": 0.2,  # proportion of window overlap
        "plaus_hr_bpm": [40, 180],  # range of plausible HRs (only the lower bound is used)
        "tol_durn": 0.05,
        # tolerance window (+/- tol_durn) within which to search for true peak either side of candidate peak
    }

    options["tol_durn"] = 0.15  # added for neurokit implementation

    # Split into overlapping windows
    no_samps_in_win = options["win_len"] * sampling_rate
    if len(signal) <= no_samps_in_win:
        win_starts = 0
        win_ends = len(signal) - 1
    else:
        win_offset = round(no_samps_in_win * (1 - options["win_overlap"]))
        win_starts = list(range(0, len(signal) - no_samps_in_win + 1, win_offset))
        win_ends = [start + 1 + no_samps_in_win for start in win_starts]
        if win_ends[-1] < len(signal):
            win_starts.append(len(signal) - 1 - no_samps_in_win)
            win_ends.append(len(signal))
        # this ensures that the windows include the entire signal duration

    # Set up downsampling if the sampling frequency is particularly high
    if options["do_ds"]:
        min_fs = options["ds_freq"]
        if sampling_rate > min_fs:
            ds_factor = int(np.floor(sampling_rate / min_fs))
            ds_fs = sampling_rate / np.floor(sampling_rate / min_fs)
        else:
            options["do_ds"] = False

    # detect peaks and onsets in each window
    peaks = []
    onsets = []

    # cycle through each window
    for win_no in range(len(win_starts)):
        # Extract this window's data
        win_sig = signal[win_starts[win_no]: win_ends[win_no]]

        # Downsample signal
        if options["do_ds"]:
            rel_sig = downsample(win_sig, ds_factor)
            rel_fs = ds_fs
        else:
            rel_sig = win_sig
            rel_fs = sampling_rate

        # Detect peaks and onsets
        p, t = detect_peaks_and_onsets_using_msptd(rel_sig, rel_fs, options)

        # Resample peaks
        if options["do_ds"]:
            p = [peak * ds_factor for peak in p]
            t = [onset * ds_factor for onset in t]

        # Correct peak indices by finding highest point within tolerance either side of detected peaks
        tol_durn = options["tol_durn"]  # note that this is only used if sampling frequency is 20 Hz or higher.
        if rel_fs < 10:
            tol_durn = 0.2
        elif rel_fs < 20:
            tol_durn = 0.1
        tol = int(np.ceil(rel_fs * tol_durn))

        for pk_no in range(len(p)):
            segment = win_sig[(p[pk_no] - tol): (p[pk_no] + tol + 1)]
            temp = np.argmax(segment)
            p[pk_no] = p[pk_no] - tol + temp

        # Correct onset indices by finding highest point within tolerance either side of detected onsets
        for onset_no in range(len(t)):
            segment = win_sig[(t[onset_no] - tol): (t[onset_no] + tol + 1)]
            temp = np.argmin(segment)
            t[onset_no] = t[onset_no] - tol + temp

        # Store peaks and onsets
        win_peaks = [peak + win_starts[win_no] for peak in p]
        peaks.extend(win_peaks)
        win_onsets = [onset + win_starts[win_no] for onset in t]
        onsets.extend(win_onsets)

    # Tidy up detected peaks and onsets (by ordering them and only retaining unique ones)
    peaks = sorted(set(peaks))
    onsets = sorted(set(onsets))

    # convert to numpy arrays
    peaks = np.asarray(peaks).astype(int)
    onsets = np.asarray(onsets).astype(int)

    return peaks, onsets
