"""Shared helpers: synthetic signals generated with nothing but stdlib."""

from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

RATE = 22050


def tone(freq: float = 440.0, seconds: float = 1.0, rate: int = RATE,
         amplitude: float = 0.5, harmonics: int = 0) -> list:
    out = []
    for i in range(int(seconds * rate)):
        t = i / rate
        v = math.sin(2 * math.pi * freq * t)
        for h in range(2, 2 + harmonics):
            v += math.sin(2 * math.pi * freq * h * t) / (h * 2)
        out.append(v * amplitude)
    return out


def noise(seconds: float = 1.0, rate: int = RATE, amplitude: float = 0.3,
          seed: int = 7) -> list:
    state = seed
    out = []
    for _ in range(int(seconds * rate)):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        out.append(((state / 0x7FFFFFFF) * 2 - 1) * amplitude)
    return out


def silence(seconds: float = 1.0, rate: int = RATE) -> list:
    return [0.0] * int(seconds * rate)


@pytest.fixture
def tmp_wav(tmp_path):
    """Return a factory that writes samples to a 16-bit mono WAV."""
    from audioverdict.decode.wav import write_wav

    def _make(samples, name="test.wav", rate=RATE):
        path = str(tmp_path / name)
        write_wav(path, samples, rate)
        return path
    return _make
