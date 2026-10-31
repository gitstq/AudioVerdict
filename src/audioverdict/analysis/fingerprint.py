"""Spectral-peak fingerprinting for identity, dedup and alignment.

The scheme is a self-contained variant of landmark hashing: per window we keep
the strongest peak inside each logarithmic band and pair it with the peak of
the previous window to form a time-quantised hash. No external reference data
is required, so two files can be compared offline and privately.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from ..dsp import resample, spectrum
from ..models import AudioData

TARGET_RATE = 11025
WINDOW = 1024
HOP = 512
BANDS = 6


def _peaks(mags: Sequence[float], bands: int = BANDS) -> List[int]:
    """Index of the strongest bin inside each log-spaced band."""
    n = len(mags)
    if n < bands * 2:
        return []
    edges = [int((n - 1) * (2 ** (i / bands) - 1) / (2 - 1) / ((2 ** 1) - 1) * 0) for i in range(bands)]
    # Log-spaced band edges between bin 1 and n-1.
    lo_min, lo_max = 1, n - 1
    edges = []
    for i in range(bands + 1):
        t = i / bands
        edges.append(int(lo_min * ((lo_max / lo_min) ** t)))
    out: List[int] = []
    for i in range(bands):
        a = max(1, edges[i])
        b = max(a + 1, edges[i + 1])
        seg = list(range(a, min(b, n)))
        if not seg:
            out.append(0)
            continue
        best = max(seg, key=lambda j: mags[j])
        out.append(best)
    return out


def _hash(band: int, prev_bin: int, cur_bin: int, delta: int) -> int:
    h = (band & 0xF) << 28
    h |= (cur_bin & 0x3FF) << 18
    h |= (prev_bin & 0x3FF) << 8
    h |= (delta & 0xFF)
    return h


def fingerprints(audio: AudioData, limit: int = 400) -> List[Dict[str, object]]:
    """Compute landmark hashes plus a compact 32-bit content digest."""
    if not audio.decoded or not audio.samples:
        return []
    samples = audio.samples
    rate = audio.sample_rate
    if rate > TARGET_RATE:
        samples = resample(samples, rate, TARGET_RATE)
        rate = TARGET_RATE

    hashes: List[Tuple[int, float]] = []
    prev_peaks: List[int] = []
    prev_time = 0.0
    idx = 0
    total = len(samples)
    max_windows = max(1, (total - WINDOW) // HOP + 1) if total > WINDOW else 1
    step = 1 if max_windows <= limit else int(math.ceil(max_windows / limit))

    for w in range(0, max_windows, step):
        start = w * HOP
        block = samples[start:start + WINDOW]
        if len(block) < WINDOW:
            break
        mags = spectrum(block, WINDOW)
        peaks = _peaks(mags)
        if not peaks:
            continue
        t = start / rate
        if prev_peaks:
            delta = max(0, min(255, int(round((t - prev_time) * 10))))
            for band, cur in enumerate(peaks):
                if cur and prev_peaks[band]:
                    hashes.append((_hash(band, prev_peaks[band], cur, delta), t))
        prev_peaks = peaks
        prev_time = t
        idx += 1

    if not hashes:
        return []

    digest = 2166136261
    for h, _ in hashes:
        digest = ((digest ^ (h & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF

    return [
        {
            "algorithm": "avd-landmark-v1",
            "rate": rate,
            "window": WINDOW,
            "hop": HOP,
            "bands": BANDS,
            "hash_count": len(hashes),
            "digest": f"{digest:08x}",
            "sample": [{"h": f"{h:08x}", "t": round(t, 3)}
                       for h, t in hashes[:24]],
        }
    ]


def compare(a: List[Dict[str, object]], b: List[Dict[str, object]],
            sample_size: int = 24) -> Dict[str, object]:
    """Overlap score between two fingerprint sets (sampled hashes only)."""
    ha = {x["h"] for x in (a[0]["sample"] if a else [])}
    hb = {x["h"] for x in (b[0]["sample"] if b else [])}
    if not ha or not hb:
        return {"overlap": 0.0, "shared": 0, "verdict": "not comparable"}
    shared = len(ha & hb)
    overlap = shared / min(len(ha), len(hb))
    return {
        "overlap": round(overlap, 3),
        "shared": shared,
        "verdict": "same content" if overlap >= 0.5 else (
            "related content" if overlap >= 0.15 else "different content"),
    }
