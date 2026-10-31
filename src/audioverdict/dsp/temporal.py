"""Time-domain measurements."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..models import to_db


def rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    acc = 0.0
    for v in samples:
        acc += v * v
    return math.sqrt(acc / len(samples))


def peak(samples: Sequence[float]) -> float:
    return max((abs(v) for v in samples), default=0.0)


def crest_factor(samples: Sequence[float]) -> float:
    r = rms(samples)
    if r <= 1e-12:
        return 0.0
    return peak(samples) / r


def dc_offset(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return sum(samples) / len(samples)


def zero_crossing_rate(samples: Sequence[float]) -> float:
    if len(samples) < 2:
        return 0.0
    crossings = 0
    prev = samples[0]
    for v in samples[1:]:
        if (prev < 0 <= v) or (v < 0 <= prev):
            crossings += 1
        prev = v
    return crossings / (len(samples) - 1)


def clipping_ratio(samples: Sequence[float], threshold: float = 0.999) -> float:
    """Fraction of samples pinned at (or above) full scale."""
    if not samples:
        return 0.0
    hits = sum(1 for v in samples if abs(v) >= threshold)
    return hits / len(samples)


def envelope(samples: Sequence[float], block: int = 256) -> List[float]:
    """RMS energy envelope at block resolution."""
    return [rms(samples[i:i + block]) for i in range(0, len(samples), block)]


def dynamic_range_db(samples: Sequence[float], block: int = 256) -> float:
    """Difference between a robust loud floor and a robust peak (dB)."""
    env = [e for e in envelope(samples, block) if e > 0]
    if not env:
        return 0.0
    env.sort()
    low = env[max(0, int(len(env) * 0.05))]
    high = env[min(len(env) - 1, int(len(env) * 0.95))]
    if low <= 0:
        return 0.0
    return to_db(high) - to_db(low)


def silence_ratio(envelope_values: Sequence[float], floor: float = 1e-4) -> float:
    if not envelope_values:
        return 1.0
    quiet = sum(1 for e in envelope_values if e < floor)
    return quiet / len(envelope_values)


def detect_silence(samples: Sequence[float], sample_rate: int,
                   floor_db: float = -60.0, min_seconds: float = 0.15
                   ) -> List[Tuple[float, float]]:
    """Return (start, end) spans of silence longer than ``min_seconds``."""
    if not samples or sample_rate <= 0:
        return []
    block = max(32, sample_rate // 100)          # ~10 ms
    env = envelope(samples, block)
    threshold = 10 ** (floor_db / 20.0)
    spans: List[Tuple[float, float]] = []
    start = None
    for i, e in enumerate(env):
        if e < threshold:
            if start is None:
                start = i
        elif start is not None:
            t0 = start * block / sample_rate
            t1 = i * block / sample_rate
            if t1 - t0 >= min_seconds:
                spans.append((round(t0, 3), round(t1, 3)))
            start = None
    if start is not None:
        t0 = start * block / sample_rate
        t1 = len(samples) / sample_rate
        if t1 - t0 >= min_seconds:
            spans.append((round(t0, 3), round(t1, 3)))
    return spans


def energy_jumps(envelope_values: Sequence[float], factor: float = 3.0
                 ) -> List[int]:
    """Indices where the envelope jumps by ``factor`` or more (splice hints)."""
    jumps: List[int] = []
    for i in range(1, len(envelope_values)):
        a, b = envelope_values[i - 1], envelope_values[i]
        if a <= 1e-9 and b > 1e-6:
            jumps.append(i)
        elif a > 1e-9 and (b / a >= factor or a / b >= factor):
            jumps.append(i)
    return jumps
