"""Signal-processing primitives (all pure Python, no NumPy)."""

from ..models import to_db
from .fft import (blackman, dct_ii, fft, hamming, hann, next_power_of_two,
                  resample, rfft, window)
from .loudness import k_weight, loudness_lufs, true_peak_dbtp
from .mfcc import hz_to_mel, mel_filterbank, mel_to_hz, mfcc
from .pitch import pitch_track, yin_pitch
from .spectral import (band_cliff, band_energy, centroid, flatness, flux,
                       high_cutoff, rolloff, spectral_contrast, spectrum, spread)
from .tempo import autocorrelation, beat_grid, estimate_bpm
from .temporal import (clipping_ratio, crest_factor, dc_offset, detect_silence,
                       dynamic_range_db, energy_jumps, envelope,
                       silence_ratio, zero_crossing_rate, rms, peak)

__all__ = [
    "fft", "rfft", "hann", "hamming", "blackman", "window", "dct_ii",
    "next_power_of_two", "resample",
    "rms", "peak", "crest_factor", "dc_offset", "zero_crossing_rate",
    "clipping_ratio", "envelope", "dynamic_range_db", "silence_ratio",
    "detect_silence", "energy_jumps",
    "spectrum", "centroid", "spread", "rolloff", "flatness", "flux",
    "band_energy", "band_cliff", "high_cutoff", "spectral_contrast",
    "mfcc", "mel_filterbank", "hz_to_mel", "mel_to_hz",
    "yin_pitch", "pitch_track", "estimate_bpm", "beat_grid", "autocorrelation",
    "loudness_lufs", "k_weight", "true_peak_dbtp", "to_db",
]
