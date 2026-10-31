"""Tempo (BPM) estimation from the energy envelope."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

MIN_BPM = 50.0
MAX_BPM = 200.0


def autocorrelation(values: Sequence[float], max_lag: int) -> List[float]:
    n = len(values)
    mean = sum(values) / n if n else 0.0
    centred = [v - mean for v in values]
    denom = sum(v * v for v in centred) or 1.0
    out: List[float] = []
    for lag in range(1, min(max_lag, n - 1)):
        acc = 0.0
        for i in range(n - lag):
            acc += centred[i] * centred[i + lag]
        out.append(acc / denom)
    return out


def estimate_bpm(envelope_values: Sequence[float], hop_seconds: float
                 ) -> Tuple[float, float]:
    """Return (bpm, confidence) using onset-envelope autocorrelation."""
    if len(envelope_values) < 16 or hop_seconds <= 0:
        return 0.0, 0.0

    # Half-wave rectified derivative: a cheap onset detector.
    onset = [max(0.0, envelope_values[i] - envelope_values[i - 1])
             for i in range(1, len(envelope_values))]
    if sum(onset) <= 0:
        return 0.0, 0.0
    peak = max(onset)
    onset = [o / peak for o in onset]

    lag_min = int(60.0 / MAX_BPM / hop_seconds)
    lag_max = int(60.0 / MIN_BPM / hop_seconds)
    lag_max = min(lag_max, len(onset) - 2)
    if lag_max <= lag_min:
        return 0.0, 0.0

    ac = autocorrelation(onset, lag_max + 1)
    window = ac[lag_min - 1:lag_max] if lag_min >= 1 else ac[0:lag_max]
    if not window:
        return 0.0, 0.0

    best = max(window)
    if best <= 0:
        return 0.0, 0.0
    idx = window.index(best) + lag_min
    bpm = 60.0 / (idx * hop_seconds)

    # Normalise BPM into a musical range.
    while bpm < MIN_BPM:
        bpm *= 2.0
    while bpm > MAX_BPM:
        bpm /= 2.0

    mean_ac = sum(window) / len(window)
    confidence = 0.0 if mean_ac <= 0 else min(1.0, (best - mean_ac) / (abs(mean_ac) + 1e-9) / 3.0)
    return round(bpm, 1), round(confidence, 3)


def beat_grid(envelope_values: Sequence[float], hop_seconds: float, bpm: float
              ) -> List[float]:
    """Return beat timestamps for a given BPM (phase taken from peak energy)."""
    if bpm <= 0 or hop_seconds <= 0 or not envelope_values:
        return []
    period = 60.0 / bpm
    n = len(envelope_values)
    # Choose the phase that maximises the mean onset strength.
    steps = max(1, int(period / hop_seconds))
    best_phase, best_score = 0, -1.0
    for phase in range(steps):
        score = sum(envelope_values[i] for i in range(phase, n, steps)) / max(1, n // steps)
        if score > best_score:
            best_phase, best_score = phase, score
    beats: List[float] = []
    t = best_phase * hop_seconds
    limit = n * hop_seconds
    while t < limit:
        beats.append(round(t, 3))
        t += period
    return beats
