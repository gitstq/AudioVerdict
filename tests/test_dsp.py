"""DSP primitive tests."""

from __future__ import annotations

import math

import pytest

from audioverdict.dsp import (band_energy, centroid, clipping_ratio,
                              crest_factor, dct_ii, envelope, fft, flatness,
                              high_cutoff, loudness_lufs, mfcc, rfft,
                              resample, rolloff, rms, spectral_contrast,
                              spectrum, yin_pitch, zero_crossing_rate)

from conftest import RATE, noise, silence, tone


def test_fft_matches_dft_on_small_input():
    signal = [math.sin(2 * math.pi * 3 * i / 16) for i in range(16)]
    got = fft([complex(v, 0.0) for v in signal])
    # Brute-force DFT reference for bin 3.
    n = 16
    ref = sum(signal[i] * complex(math.cos(-2 * math.pi * 3 * i / n),
                                  math.sin(-2 * math.pi * 3 * i / n)) for i in range(n))
    assert abs(abs(got[3]) - abs(ref)) < 1e-9


def test_rfft_finds_single_tone():
    n = 1024
    freq = 440.0
    rate = 22050
    sig = [math.sin(2 * math.pi * freq * i / rate) for i in range(n)]
    mags = rfft(sig, n)
    peak_bin = max(range(len(mags)), key=lambda i: mags[i])
    assert abs(peak_bin * rate / n - freq) < rate / n * 2


def test_centroid_of_low_tone_is_low():
    sig = tone(150.0, 0.5)
    mags = spectrum(sig, 2048)
    assert centroid(mags, RATE) < 800


def test_flatness_tone_vs_noise():
    tone_mags = spectrum(tone(440.0, 0.5), 2048)
    noise_mags = spectrum(noise(0.5), 2048)
    assert flatness(tone_mags) < flatness(noise_mags)


def test_rms_and_crest_factor():
    sig = [math.sin(2 * math.pi * 440 * i / RATE) for i in range(RATE)]
    assert abs(rms(sig) - (0.5 ** 0.5)) < 0.01
    assert abs(crest_factor(sig) - math.sqrt(2)) < 0.05


def test_clipping_detection():
    clean = tone(440.0, 0.2, amplitude=0.5)
    clipped = [1.0 if abs(v) > 0.9 else v for v in tone(440.0, 0.2, amplitude=1.0)]
    assert clipping_ratio(clean) == 0.0
    assert clipping_ratio(clipped) > 0.0


def test_zero_crossing_rate():
    assert zero_crossing_rate(silence(0.1)) == 0.0
    assert zero_crossing_rate(tone(440.0, 0.5)) > 0.0


def test_yin_pitch():
    for freq in (110.0, 220.0, 440.0):
        sig = tone(freq, 0.5, amplitude=0.6)
        pitch, harm = yin_pitch(sig, RATE)
        assert pitch > 0, f"no pitch for {freq}"
        assert abs(pitch - freq) < max(2.0, freq * 0.02), f"{pitch} != {freq}"
        assert harm > 0.5


def test_yin_on_noise_has_low_harmonicity():
    pitch, harm = yin_pitch(noise(0.6), RATE)
    assert harm < 0.9


def test_loudness_monotonic_with_amplitude():
    quiet = tone(440.0, 1.0, amplitude=0.05)
    loud = tone(440.0, 1.0, amplitude=0.5)
    lq, _, _ = loudness_lufs(quiet, RATE)
    ll, _, _ = loudness_lufs(loud, RATE)
    assert lq < ll
    assert -70 <= lq <= 0 and -70 <= ll <= 0


def test_loudness_silence_is_floor():
    l, _, _ = loudness_lufs(silence(1.0), RATE)
    assert l <= -60


def test_resample_keeps_length_ratio():
    src = tone(440.0, 1.0, rate=44100)
    out = resample(src, 44100, 22050)
    assert abs(len(out) - len(src) / 2) <= 2


def test_band_energy_sums_to_one():
    mags = spectrum(noise(0.5), 2048)
    bands = band_energy(mags, RATE)
    assert len(bands) == 9
    assert abs(sum(bands) - 1.0) < 0.02


def test_high_cutoff_of_full_band_noise():
    mags = spectrum(noise(1.0), 2048)
    assert high_cutoff(mags, RATE) > 8000


def test_dct_ii_known_values():
    out = dct_ii([1.0, 1.0, 1.0, 1.0], 2)
    assert abs(out[0] - 4.0) < 1e-9
    assert abs(out[1]) < 1e-9


def test_mfcc_shape_and_determinism():
    mags = spectrum(tone(440.0, 0.5), 2048)
    a = mfcc(mags, RATE, fft_size=2048)
    b = mfcc(mags, RATE, fft_size=2048)
    assert len(a) == 13
    assert a == b


def test_envelope_length():
    env = envelope(tone(440.0, 1.0), 256)
    assert len(env) == len(tone(440.0, 1.0)) // 256 + 1


def test_rolloff_within_nyquist():
    mags = spectrum(noise(0.5), 2048)
    r = rolloff(mags, RATE)
    assert 0 < r <= RATE / 2


def test_spectral_contrast_positive_for_tone():
    mags = spectrum(tone(440.0, 0.5), 2048)
    assert spectral_contrast(mags, RATE) > 0
