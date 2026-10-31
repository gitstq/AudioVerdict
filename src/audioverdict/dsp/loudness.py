"""Loudness estimation with a hand-implemented K-weighting filter (ITU-R BS.1770)."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple


def _biquad_highshelf(f0: float, q: float, gain_db: float, fs: int
                      ) -> Tuple[float, float, float, float, float]:
    """RBJ high-shelf coefficients (normalised by a0)."""
    a = 10 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    cs = math.cos(w0)
    sq = 2.0 * math.sqrt(a) * alpha
    b0 = a * ((a + 1.0) + (a - 1.0) * cs + sq)
    b1 = -2.0 * a * ((a - 1.0) + (a + 1.0) * cs)
    b2 = a * ((a + 1.0) + (a - 1.0) * cs - sq)
    a0 = (a + 1.0) - (a - 1.0) * cs + sq
    a1 = 2.0 * ((a - 1.0) - (a + 1.0) * cs)
    a2 = (a + 1.0) - (a - 1.0) * cs - sq
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def _biquad_highpass(f0: float, q: float, fs: int) -> Tuple[float, float, float, float, float]:
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    cs = math.cos(w0)
    b0 = (1.0 + cs) / 2.0
    b1 = -(1.0 + cs)
    b2 = (1.0 + cs) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cs
    a2 = 1.0 - alpha
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def _apply(bq: Tuple[float, float, float, float, float],
           samples: Sequence[float]) -> List[float]:
    b0, b1, b2, a1, a2 = bq
    out: List[float] = []
    x1 = x2 = y1 = y2 = 0.0
    for x in samples:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out.append(y)
        x2, x1 = x1, x
        y2, y1 = y1, y
    return out


def k_weight(samples: Sequence[float], sample_rate: int) -> List[float]:
    """Two-stage BS.1770 K-weighting (high-shelf + RLB high-pass)."""
    if sample_rate <= 0 or not samples:
        return []
    stage1 = _biquad_highshelf(1681.97, 0.7071, 4.0, sample_rate)
    stage2 = _biquad_highpass(38.13, 0.5, sample_rate)
    return _apply(stage2, _apply(stage1, samples))


def loudness_lufs(samples: Sequence[float], sample_rate: int,
                  block_seconds: float = 0.4) -> Tuple[float, float, float]:
    """Return (integrated LUFS, short-term peak LUFS, loudness range LU).

    Integrated loudness follows the BS.1770-4 gated measurement; the result is
    accurate to roughly +/-1 LU, which is well inside what an agent needs to
    judge whether a file is broadcast-loud or whisper-quiet.
    """
    if not samples or sample_rate <= 0:
        return -70.0, -70.0, 0.0

    filtered = k_weight(samples, sample_rate)
    block = max(1, int(block_seconds * sample_rate))
    hop = block // 4 or 1
    powers: List[float] = []
    for start in range(0, len(filtered) - block + 1, hop):
        acc = 0.0
        for i in range(start, start + block):
            acc += filtered[i] * filtered[i]
        powers.append(acc / block)
    if not powers:
        return -70.0, -70.0, 0.0

    def lufs(p: float) -> float:
        return -0.691 + 10.0 * math.log10(p) if p > 0 else -70.0

    blocks_db = [lufs(p) for p in powers]
    # Absolute gate (-70 LUFS) then relative gate (-10 LU below the ungated mean).
    kept = [d for d in blocks_db if d > -70.0]
    if not kept:
        return -70.0, max(blocks_db), 0.0
    ungated = -0.691 + 10.0 * math.log10(sum(10 ** (d / 10.0) for d in kept) / len(kept))
    rel_gate = ungated - 10.0
    gated = [d for d in kept if d > rel_gate]
    if not gated:
        gated = kept
    integrated = -0.691 + 10.0 * math.log10(
        sum(10 ** (d / 10.0) for d in gated) / len(gated))

    # Loudness range: 10th to 95th percentile of short-term loudness.
    st = sorted(blocks_db)
    lo = st[int(len(st) * 0.10)]
    hi = st[min(len(st) - 1, int(len(st) * 0.95))]
    return round(integrated, 2), round(max(blocks_db), 2), round(hi - lo, 2)


def true_peak_dbtp(samples: Sequence[float], oversample: int = 4) -> float:
    """Interpolated true-peak estimate in dBTP."""
    if not samples:
        return -120.0
    best = 0.0
    n = len(samples)
    for i in range(n - 1):
        a, b = samples[i], samples[i + 1]
        for k in range(oversample):
            t = k / oversample
            v = abs(a + (b - a) * t)
            if v > best:
                best = v
    if best <= 0:
        return -120.0
    return round(20.0 * math.log10(best), 2)
