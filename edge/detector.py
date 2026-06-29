import math


def compute_features(samples, sample_period_ms, freefall_threshold_g=0.3):
    """samples: list of (x, y, z) in g. Returns a features dict."""
    n = len(samples)
    if n == 0:
        raise ValueError("samples must be non-empty")
    mags = [math.sqrt(x * x + y * y + z * z) for (x, y, z) in samples]
    mean_mag = sum(mags) / n
    mag_peak = max(mags)
    mag_rms = math.sqrt(sum((m - mean_mag) ** 2 for m in mags) / n)
    mean_x = sum(s[0] for s in samples) / n
    mean_y = sum(s[1] for s in samples) / n
    mean_z = sum(s[2] for s in samples) / n
    mean_vec = math.sqrt(mean_x * mean_x + mean_y * mean_y + mean_z * mean_z)
    if mean_vec == 0:
        tilt_deg = 0.0
    else:
        cos_t = max(-1.0, min(1.0, mean_z / mean_vec))
        tilt_deg = math.degrees(math.acos(cos_t))
    longest = run = 0
    for m in mags:
        if m < freefall_threshold_g:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return {
        "mag_peak": round(mag_peak, 4),
        "mag_rms": round(mag_rms, 4),
        "tilt_deg": round(tilt_deg, 2),
        "freefall_ms": longest * sample_period_ms,
        "window_ms": n * sample_period_ms,
    }
