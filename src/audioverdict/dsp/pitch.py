"""Pitch tracking: normalised autocorrelation with a YIN-style difference function."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

MIN_HZ = 50.0
MAX_HZ = 2000.0


def _difference(samples: Sequence[float], tau: int, n: int) -> float:
    acc = 0.0
    for i in range(n):
        d = samples[i] - samples[i + tau]
        acc += d * d
    return acc


def yin_pitch(samples: Sequence[float], sample_rate: int,
              threshold: float = 0.12) -> Tuple[float, float]:
    """Return (pitch_hz, harmonicity). harmonicity is 1 - normalised dip.

    ``harmonicity`` near 1 means a strong, stable periodicity; near 0 means the
    window is noise-like.
    """
    n = len(samples)
    if sample_rate <= 0 or n < 256:
        return 0.0, 0.0

    tau_max = min(int(sample_rate / MIN_HZ), n // 2)
    tau_min = max(2, int(sample_rate / MAX_HZ))
    if tau_max <= tau_min:
        return 0.0, 0.0

    win = min(n - tau_max, 1024)
    if win < 64:
        return 0.0, 0.0

    diff = [0.0] * (tau_max + 1)
    running = 0.0
    cmnd = [1.0] * (tau_max + 1)
    for tau in range(1, tau_max + 1):
        diff[tau] = _difference(samples, tau, win)
        running += diff[tau]
        cmnd[tau] = diff[tau] * tau / running if running > 0 else 1.0

    best_tau, best_val = 0, 1.0
    for tau in range(tau_min, tau_max):
        if cmnd[tau] < threshold and cmnd[tau] < best_val:
            best_tau, best_val = tau, cmnd[tau]
        if cmnd[tau] < threshold and cmnd[tau + 1] > cmnd[tau] and best_tau:
            break

    if best_tau == 0:
        # Fall back to the global minimum, but report weak harmonicity.
        best_val = min(cmnd[tau_min:tau_max + 1] or [1.0])
        if best_val >= 0.6:
            return 0.0, 0.0
        best_tau = tau_min + max(0, min(
            range(tau_max + 1 - tau_min), key=lambda i: cmnd[tau_min + i]))

    # Parabolic interpolation around the chosen lag.
    if 0 < best_tau < tau_max:
        a, b, c = cmnd[best_tau - 1], cmnd[best_tau], cmnd[best_tau + 1]
        denom = a - 2 * b + c
        shift = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
        best_tau_f = best_tau + (shift if abs(shift) < 1 else 0.0)
    else:
        best_tau_f = float(best_tau)

    pitch = sample_rate / best_tau_f if best_tau_f else 0.0
    harmonicity = 1.0 - min(1.0, max(0.0, best_val))
    return pitch, harmonicity


def pitch_track(samples: Sequence[float], sample_rate: int,
                hop_seconds: float = 0.05) -> List[Tuple[float, float, float]]:
    """Return (time, pitch_hz, harmonicity) tuples across the signal."""
    out: List[Tuple[float, float, float]] = []
    if sample_rate <= 0 or not samples:
        return out
    win = min(len(samples), int(sample_rate * 0.06))
    hop = max(1, int(sample_rate * hop_seconds))
    if win < 256:
        return out
    for start in range(0, len(samples) - win, hop):
        p, h = yin_pitch(samples[start:start + win], sample_rate)
        out.append((round(start / sample_rate, 3), round(p, 2), round(h, 3)))
    return out
