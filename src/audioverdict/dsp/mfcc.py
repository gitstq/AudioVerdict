"""MFCC front-end (Mel filter bank + DCT-II), pure Python."""

from __future__ import annotations

import math
from typing import List, Sequence


def hz_to_mel(f: float) -> float:
    return 2595.0 * math.log10(1.0 + f / 700.0)


def mel_to_hz(m: float) -> float:
    return 700.0 * (10 ** (m / 2595.0) - 1.0)


def mel_filterbank(num_filters: int, fft_size: int, sample_rate: int,
                   fmin: float = 20.0, fmax: float = 0.0) -> List[List[float]]:
    """Triangular Mel filters, one row per filter."""
    if fmax <= 0:
        fmax = sample_rate / 2.0
    bins = fft_size // 2 + 1
    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(min(fmax, sample_rate / 2.0))
    points = [mel_min + (mel_max - mel_min) * i / (num_filters + 1)
              for i in range(num_filters + 2)]
    hz_points = [mel_to_hz(p) for p in points]
    bin_idx = [int(round(h / (sample_rate / 2.0) * (bins - 1))) for h in hz_points]

    filters: List[List[float]] = []
    for i in range(num_filters):
        row = [0.0] * bins
        left, center, right = bin_idx[i], bin_idx[i + 1], bin_idx[i + 2]
        if center == left:
            center = left + 1
        if right <= center:
            right = center + 1
        for b in range(left, min(center, bins)):
            row[b] = (b - left) / float(center - left)
        for b in range(center, min(right, bins)):
            row[b] = (right - b) / float(right - center)
        filters.append(row)
    return filters


def mfcc(magnitudes: Sequence[float], sample_rate: int, num_filters: int = 26,
         num_ceps: int = 13, fft_size: int = 2048) -> List[float]:
    """Compute MFCCs from a magnitude spectrum."""
    try:
        from .fft import dct_ii
    except Exception:                      # pragma: no cover - defensive
        return []

    filters = mel_filterbank(num_filters, fft_size, sample_rate)
    energy: List[float] = []
    for row in filters:
        acc = 0.0
        for b, w in enumerate(row):
            if w and b < len(magnitudes):
                acc += (magnitudes[b] ** 2) * w
        energy.append(math.log(acc + 1e-10))
    cep = dct_ii(energy, num_ceps)
    return [c / max(1, num_filters) for c in cep]
