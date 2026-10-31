"""Iterative radix-2 FFT plus window functions, in pure Python.

Written from scratch so that AudioVerdict keeps its zero-dependency promise
and so the numerical behaviour is fully predictable across platforms.
"""

from __future__ import annotations

import cmath
import math
from typing import List, Sequence


def next_power_of_two(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def _bit_reverse(index: int, bits: int) -> int:
    r = 0
    for i in range(bits):
        r = (r << 1) | ((index >> i) & 1)
    return r


def fft(values: Sequence[complex]) -> List[complex]:
    """In-place-free radix-2 Cooley-Tukey FFT (input length must be 2**k)."""
    n = len(values)
    if n & (n - 1):
        raise ValueError("FFT length must be a power of two")
    bits = n.bit_length() - 1
    out = [values[_bit_reverse(i, bits)] for i in range(n)]

    size = 2
    while size <= n:
        half = size >> 1
        step = -2.0 * math.pi / size
        for i in range(0, n, size):
            for k in range(half):
                angle = step * k
                wr = math.cos(angle)
                wi = math.sin(angle)
                a = out[i + k]
                b = out[i + k + half]
                tr = b.real * wr - b.imag * wi
                ti = b.real * wi + b.imag * wr
                out[i + k] = complex(a.real + tr, a.imag + ti)
                out[i + k + half] = complex(a.real - tr, a.imag - ti)
        size <<= 1
    return out


def rfft(samples: Sequence[float], n: int) -> List[float]:
    """Real-input FFT magnitude spectrum (first n/2 + 1 bins)."""
    buf = [complex(samples[i] if i < len(samples) else 0.0, 0.0) for i in range(n)]
    spec = fft(buf)
    half = n // 2 + 1
    return [math.hypot(spec[i].real, spec[i].imag) for i in range(half)]


def hann(n: int) -> List[float]:
    if n <= 1:
        return [1.0] * max(1, n)
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


def hamming(n: int) -> List[float]:
    if n <= 1:
        return [1.0] * max(1, n)
    return [0.54 - 0.46 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


def blackman(n: int) -> List[float]:
    if n <= 1:
        return [1.0] * max(1, n)
    return [
        0.42 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1))
        + 0.08 * math.cos(4.0 * math.pi * i / (n - 1))
        for i in range(n)
    ]


def window(name: str, n: int) -> List[float]:
    key = (name or "hann").lower()
    if key == "hamming":
        return hamming(n)
    if key == "blackman":
        return blackman(n)
    return hann(n)


def dct_ii(values: Sequence[float], count: int) -> List[float]:
    """Type-II DCT, used by the MFCC front-end."""
    n = len(values)
    out: List[float] = []
    for k in range(count):
        acc = 0.0
        for i in range(n):
            acc += values[i] * math.cos(math.pi * k * (2 * i + 1) / (2 * n))
        out.append(acc)
    return out


def resample(samples: Sequence[float], src_rate: int, dst_rate: int) -> List[float]:
    """Linear-interpolation resampler (good enough for analysis down-mixing)."""
    if src_rate <= 0 or dst_rate <= 0 or src_rate == dst_rate:
        return list(samples)
    ratio = dst_rate / src_rate
    n = len(samples)
    out_len = int(n * ratio)
    out: List[float] = []
    for i in range(out_len):
        pos = i / ratio
        i0 = int(pos)
        frac = pos - i0
        a = samples[i0] if i0 < n else 0.0
        b = samples[i0 + 1] if i0 + 1 < n else a
        out.append(a + (b - a) * frac)
    return out
