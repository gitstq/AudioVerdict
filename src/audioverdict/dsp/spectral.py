"""Spectral descriptors computed on top of the hand-rolled FFT."""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from ..models import to_db
from .fft import rfft, window

# Bark-ish partition used for the band-energy vector.
BAND_EDGES = [0, 100, 250, 500, 1000, 2000, 4000, 8000, 16000, 24000]


def spectrum(samples: Sequence[float], fft_size: int = 2048,
             window_name: str = "hann") -> List[float]:
    n = max(2, fft_size)
    w = window(window_name, n)
    buf = [samples[i] * w[i] if i < len(samples) else 0.0 for i in range(n)]
    return rfft(buf, n)


def centroid(magnitudes: Sequence[float], sample_rate: int) -> float:
    total = sum(magnitudes)
    if total <= 0:
        return 0.0
    acc = 0.0
    for i, m in enumerate(magnitudes):
        acc += m * (i * sample_rate / (2 * (len(magnitudes) - 1)))
    return acc / total


def spread(magnitudes: Sequence[float], sample_rate: int) -> float:
    c = centroid(magnitudes, sample_rate)
    total = sum(magnitudes)
    if total <= 0:
        return 0.0
    acc = 0.0
    for i, m in enumerate(magnitudes):
        f = i * sample_rate / (2 * (len(magnitudes) - 1))
        acc += m * (f - c) ** 2
    return math.sqrt(acc / total)


def rolloff(magnitudes: Sequence[float], sample_rate: int, ratio: float = 0.95) -> float:
    total = sum(magnitudes)
    if total <= 0:
        return 0.0
    target = total * ratio
    acc = 0.0
    for i, m in enumerate(magnitudes):
        acc += m
        if acc >= target:
            return i * sample_rate / (2 * (len(magnitudes) - 1))
    return sample_rate / 2


def flatness(magnitudes: Sequence[float]) -> float:
    """Geometric / arithmetic mean ratio: ~0 tonal, ~1 noise-like."""
    n = len(magnitudes)
    if n == 0:
        return 0.0
    log_sum = 0.0
    arith = 0.0
    eps = 1e-12
    for m in magnitudes:
        log_sum += math.log(m + eps)
        arith += m
    if arith <= 0:
        return 0.0
    geo = math.exp(log_sum / n)
    return geo / (arith / n)


def flux(prev: Sequence[float], cur: Sequence[float]) -> float:
    """Half-wave rectified spectral difference."""
    n = min(len(prev), len(cur))
    if n == 0:
        return 0.0
    acc = 0.0
    for i in range(n):
        d = cur[i] - prev[i]
        if d > 0:
            acc += d
    return acc / n


def band_energy(magnitudes: Sequence[float], sample_rate: int,
                edges: Sequence[float] = BAND_EDGES) -> List[float]:
    """Energy share per frequency band (sums to ~1)."""
    n = len(magnitudes)
    if n == 0:
        return [0.0] * (len(edges) - 1)
    nyq = sample_rate / 2
    bins = []
    for e in edges:
        idx = int(e / nyq * (n - 1)) if nyq > 0 else 0
        bins.append(min(n - 1, max(0, idx)))
    out: List[float] = []
    total = sum(m * m for m in magnitudes) or 1.0
    for i in range(len(bins) - 1):
        a, b = bins[i], max(bins[i] + 1, bins[i + 1])
        acc = sum(magnitudes[j] ** 2 for j in range(a, min(b, n)))
        out.append(acc / total)
    return out


def high_cutoff(magnitudes: Sequence[float], sample_rate: int,
                floor_db: float = -75.0) -> float:
    """Highest frequency still carrying measurable energy.

    A codec-shaped cliff here is one of the strongest transcode artefacts.
    """
    n = len(magnitudes)
    if n == 0:
        return 0.0
    peak = max(magnitudes)
    if peak <= 0:
        return 0.0
    threshold = peak * (10 ** (floor_db / 20.0))
    last = 0.0
    nyq = sample_rate / 2
    run = 0
    for i in range(n - 1, -1, -1):
        if magnitudes[i] >= threshold:
            run += 1
            if run >= 3:                  # ignore isolated noise spikes
                last = i * nyq / (n - 1)
                break
        else:
            run = 0
    return last


#: A cliff only counts as a codec artefact when the band just below it still
#: carries real content. A pure tone's spectrum dies into the arithmetic noise
#: floor 90+ dB below its peak, and that "edge" is not a codec cliff.
CLIFF_MIN_LEVEL_DB = -70.0


def band_cliff(magnitudes: Sequence[float], sample_rate: int) -> Dict[str, float]:
    """Locate a sharp high-frequency cutoff (lossy codec fingerprint)."""
    n = len(magnitudes)
    if n < 16:
        return {"cutoff_hz": 0.0, "slope_db": 0.0, "detected": 0.0,
                "level_db": 0.0}
    cutoff = high_cutoff(magnitudes, sample_rate)
    if cutoff <= 0:
        return {"cutoff_hz": 0.0, "slope_db": 0.0, "detected": 0.0,
                "level_db": 0.0}
    nyq = sample_rate / 2
    i_cut = int(cutoff / nyq * (n - 1))
    lo = max(1, i_cut - max(4, i_cut // 8))
    hi = min(n - 1, i_cut + max(4, i_cut // 8))
    below = sum(magnitudes[max(0, lo - 8):lo]) / max(1, len(magnitudes[max(0, lo - 8):lo]))
    above = sum(magnitudes[hi:hi + 8]) / max(1, len(magnitudes[hi:hi + 8]))
    slope = to_db(above + 1e-12) - to_db(below + 1e-12)
    peak = max(magnitudes)
    level_db = to_db(below + 1e-12) - to_db(peak + 1e-12) if peak > 0 else -120.0
    detected = (1.0 if slope < -18.0 and cutoff < nyq * 0.98
                and level_db > CLIFF_MIN_LEVEL_DB else 0.0)
    return {
        "cutoff_hz": round(cutoff, 1),
        "slope_db": round(slope, 2),
        "level_db": round(level_db, 2),
        "detected": detected,
    }


def spectral_contrast(magnitudes: Sequence[float], sample_rate: int) -> float:
    """Peak-to-valley contrast of the smoothed spectrum (synthetic-audio cue)."""
    if len(magnitudes) < 32:
        return 0.0
    k = 9
    smooth: List[float] = []
    for i in range(len(magnitudes)):
        a = max(0, i - k // 2)
        b = min(len(magnitudes), i + k // 2 + 1)
        seg = magnitudes[a:b]
        smooth.append(sum(seg) / len(seg))
    hi = sorted(smooth)[int(len(smooth) * 0.95)]
    lo = sorted(smooth)[int(len(smooth) * 0.05)]
    if lo <= 0:
        return 0.0
    return to_db(hi + 1e-12) - to_db(lo + 1e-12)
