"""Feature extraction: one :class:`FeatureSet` per analysis window."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from ..dsp import (band_cliff, band_energy, centroid, clipping_ratio,
                   crest_factor, dc_offset, envelope, flatness, flux,
                   high_cutoff, loudness_lufs, mfcc, resample, rolloff,
                   rms, spectral_contrast, spectrum, spread,
                   zero_crossing_rate, yin_pitch, peak, to_db)
from ..models import AudioData, FeatureSet

# Analysis runs at the file's own rate up to 44.1 kHz. Keeping the full
# bandwidth matters: a 128 kbps MP3 cuts off near 16 kHz, and that cliff is
# invisible if we resample down to 11 kHz first. Only higher rates are folded
# down, which also keeps the (pure Python) resampler cheap.
ANALYSIS_RATE = 44100
FFT_SIZE = 2048


def _prepare(samples: Sequence[float], sample_rate: int) -> Tuple[List[float], int]:
    if sample_rate > ANALYSIS_RATE:
        return resample(samples, sample_rate, ANALYSIS_RATE), ANALYSIS_RATE
    return list(samples), sample_rate


def window_features(block: Sequence[float], rate: int, start: float, end: float,
                    prev_spectrum: Optional[List[float]] = None,
                    fft_size: int = FFT_SIZE) -> Tuple[FeatureSet, List[float]]:
    mags = spectrum(block, fft_size)
    prev = prev_spectrum or [0.0] * len(mags)

    f = FeatureSet()
    f.start = round(start, 3)
    f.end = round(end, 3)
    f.rms = rms(block)
    f.peak = peak(block)
    f.peak_dbfs = to_db(f.peak)
    f.crest_factor = crest_factor(block)
    f.clipping_ratio = clipping_ratio(block)
    f.dc_offset = dc_offset(block)
    f.zero_crossing_rate = zero_crossing_rate(block)
    f.spectral_centroid = centroid(mags, rate)
    f.spectral_spread = spread(mags, rate)
    f.spectral_rolloff = rolloff(mags, rate)
    f.spectral_flatness = flatness(mags)
    f.spectral_flux = flux(prev, mags)
    f.band_energy = band_energy(mags, rate)
    f.high_cutoff_hz = high_cutoff(mags, rate)
    f.mfcc = mfcc(mags, rate, fft_size=fft_size)
    pitch, harm = yin_pitch(block, rate)
    f.pitch_hz = pitch
    f.harmonicity = harm
    f.loudness_lufs, _, _ = loudness_lufs(block, rate, block_seconds=0.4)
    return f, mags


def extract(audio: AudioData, window_seconds: float = 1.0,
            hop_seconds: float = 0.5, max_windows: int = 400,
            fft_size: int = FFT_SIZE) -> Tuple[FeatureSet, List[FeatureSet], Dict[str, object]]:
    """Return (global features, per-window timeline, extras)."""
    if not audio.decoded or not audio.samples:
        return FeatureSet(), [], {"analysable": False}

    samples, rate = _prepare(audio.samples, audio.sample_rate)
    if len(samples) < fft_size:
        # Very short clip: analyse it as a single padded window.
        padded = list(samples) + [0.0] * (fft_size - len(samples))
        f, mags = window_features(padded, rate, 0.0, len(samples) / rate, fft_size=fft_size)
        extras = {
            "analysable": True,
            "analysis_rate": rate,
            "windows": 1,
            "average_spectrum": mags,
            "band_cliff": band_cliff(mags, rate),
            "spectral_contrast": spectral_contrast(mags, rate),
        }
        f.silence_ratio = 1.0 if f.rms < 1e-4 else 0.0
        return f, [f], extras

    win = int(window_seconds * rate)
    hop = max(1, int(hop_seconds * rate))
    starts = list(range(0, max(1, len(samples) - win + 1), hop))
    if not starts:
        starts = [0]

    # Keep the run time bounded for long recordings.
    if len(starts) > max_windows:
        step = len(starts) / float(max_windows)
        starts = [starts[int(i * step)] for i in range(max_windows)]

    timeline: List[FeatureSet] = []
    prev: Optional[List[float]] = None
    spec_acc: Optional[List[float]] = None
    for s in starts:
        block = samples[s:s + win]
        if len(block) < win:
            block = block + [0.0] * (win - len(block))
        # Use the first fft_size samples of the window for spectral work.
        spec_block = block[:fft_size]
        f, mags = window_features(spec_block, rate, s / rate, (s + len(block)) / rate,
                                  prev, fft_size)
        prev = mags
        if spec_acc is None:
            spec_acc = list(mags)
        else:
            for i, m in enumerate(mags):
                spec_acc[i] += m
        timeline.append(f)

    if spec_acc and timeline:
        avg = [m / len(timeline) for m in spec_acc]
    else:
        avg = []

    # Global features: aggregate the timeline, and measure the whole signal once.
    g = FeatureSet(start=0.0, end=round(len(samples) / rate, 3))
    env = envelope(samples, max(32, rate // 100))
    g.rms = rms(samples)
    g.peak = peak(samples)
    g.peak_dbfs = to_db(g.peak)
    g.crest_factor = crest_factor(samples)
    g.dynamic_range_db = (lambda e: (max(e) and to_db(max(e)) - to_db(
        sorted(x for x in e if x > 0)[max(0, len([x for x in e if x > 0]) // 20)])))(env) if env else 0.0
    g.clipping_ratio = clipping_ratio(samples)
    g.dc_offset = dc_offset(samples)
    g.zero_crossing_rate = zero_crossing_rate(samples)
    g.silence_ratio = sum(1 for e in env if e < 1e-4) / len(env) if env else 1.0
    if avg:
        g.spectral_centroid = centroid(avg, rate)
        g.spectral_spread = spread(avg, rate)
        g.spectral_rolloff = rolloff(avg, rate)
        g.spectral_flatness = flatness(avg)
        g.band_energy = band_energy(avg, rate)
        g.high_cutoff_hz = high_cutoff(avg, rate)
        g.mfcc = mfcc(avg, rate, fft_size=fft_size)
    g.spectral_flux = sum(f.spectral_flux for f in timeline) / len(timeline) if timeline else 0.0
    pitches = [f.pitch_hz for f in timeline if f.pitch_hz > 0]
    harms = [f.harmonicity for f in timeline]
    g.pitch_hz = (sorted(pitches)[len(pitches) // 2]) if pitches else 0.0
    g.harmonicity = sum(harms) / len(harms) if harms else 0.0
    g.loudness_lufs, _, _ = loudness_lufs(samples, rate)

    extras: Dict[str, object] = {
        "analysable": True,
        "analysis_rate": rate,
        "windows": len(timeline),
        "average_spectrum": [round(m, 8) for m in avg],
        "band_cliff": band_cliff(avg, rate) if avg else {},
        "spectral_contrast": spectral_contrast(avg, rate) if avg else 0.0,
        "envelope": [round(e, 6) for e in env],
        "envelope_hop_seconds": round(max(32, rate // 100) / rate, 4),
        "pitch_variance": round(_variance(pitches), 4) if len(pitches) > 1 else 0.0,
    }
    return g, timeline, extras


def _variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def band_labels() -> List[str]:
    return ["sub-bass", "bass", "low-mid", "mid", "high-mid",
            "presence", "brilliance", "air", "ultrasonic"]
