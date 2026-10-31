"""Content classification: speech / music / ambience / noise / silence / synthetic.

Everything is heuristic and explainable on purpose - an agent consuming the
output needs to know *why* a label was chosen, not just the label.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..models import AudioData, FeatureSet

LABELS = ("music", "speech", "ambience", "noise", "silence", "tone")


def classify(global_features: FeatureSet, timeline: Sequence[FeatureSet],
             audio: AudioData, extras: Dict[str, Any]) -> Dict[str, Any]:
    g = global_features
    scores = {label: 0.0 for label in LABELS}
    reasons: Dict[str, List[str]] = {label: [] for label in LABELS}

    if g.rms < 1e-4 or g.silence_ratio > 0.97:
        scores["silence"] += 1.0
        reasons["silence"].append("signal is essentially silent")

    # --- speech ---------------------------------------------------------
    voiced = [f for f in timeline if 70.0 <= f.pitch_hz <= 400.0 and f.harmonicity > 0.6]
    voiced_ratio = len(voiced) / len(timeline) if timeline else 0.0
    if 0.15 <= voiced_ratio <= 0.85:
        scores["speech"] += 0.35 + 0.3 * voiced_ratio
        reasons["speech"].append(f"{voiced_ratio:.0%} of windows carry a 70-400 Hz voiced pitch")
    # Real speech always carries broadband fricatives; an almost perfectly flat
    # spectrum (very low flatness) means a synthetic tone, not a voice.
    if 300 <= g.spectral_centroid <= 3500 and g.silence_ratio > 0.05 and g.spectral_flatness > 0.01:
        scores["speech"] += 0.2
        reasons["speech"].append(f"spectral centroid {g.spectral_centroid:.0f} Hz sits in the vocal band")
    if g.zero_crossing_rate > 0.02:
        scores["speech"] += 0.1
        reasons["speech"].append("high zero-crossing rate (fricative-rich)")
    pauses = [1 for f in timeline if f.rms < 0.01]
    if timeline and 0.05 <= len(pauses) / len(timeline) <= 0.5:
        scores["speech"] += 0.15
        reasons["speech"].append("natural pause structure between phrases")

    # --- music ----------------------------------------------------------
    pitches = [f.pitch_hz for f in timeline if f.pitch_hz > 0]
    pitch_var = extras.get("pitch_variance", 0.0) or 0.0
    stable_pitch_ratio = len(pitches) / len(timeline) if timeline else 0.0
    if stable_pitch_ratio > 0.6 and pitch_var > 0:
        scores["music"] += 0.3
        reasons["music"].append(f"{stable_pitch_ratio:.0%} of windows are pitched with melodic variation")
    if g.spectral_rolloff > 3000 and g.high_cutoff_hz > 8000:
        scores["music"] += 0.2
        reasons["music"].append("wide bandwidth with content above 8 kHz")
    if len(g.band_energy) >= 4 and g.band_energy[0] + g.band_energy[1] > 0.25:
        scores["music"] += 0.15
        reasons["music"].append(f"{g.band_energy[0] + g.band_energy[1]:.0%} of energy below 250 Hz")
    flux_values = [f.spectral_flux for f in timeline]
    if flux_values:
        mean_flux = sum(flux_values) / len(flux_values)
        bursts = sum(1 for v in flux_values if v > mean_flux * 2)
        if bursts >= 3:
            scores["music"] += 0.2
            reasons["music"].append(f"{bursts} percussive onsets detected (rhythmic structure)")

    # --- pure tone / test signal -----------------------------------------
    # A sustained single pitch with near-zero variance and strong harmonicity is
    # neither speech nor music: it is a tone (test signal, beep, drone).
    if pitches and len(pitches) >= max(3, len(timeline) // 3):
        mean_p = sum(pitches) / len(pitches)
        cv = ((extras.get("pitch_variance", 0.0) or 0.0) ** 0.5) / mean_p if mean_p else 1.0
        if cv < 0.02 and g.harmonicity > 0.8 and g.spectral_flatness < 0.05:
            scores["tone"] += 0.8 + (0.2 if g.dynamic_range_db < 8 else 0.0)
            reasons["tone"].append(
                f"single sustained pitch near {mean_p:.0f} Hz (CV {cv:.4f}, "
                f"harmonicity {g.harmonicity:.2f})")
            if g.dynamic_range_db < 8:
                reasons["tone"].append("steady amplitude with no rhythmic variation")

    # --- noise / ambience ------------------------------------------------
    if g.spectral_flatness > 0.25:
        scores["noise"] += 0.4
        reasons["noise"].append(f"spectral flatness {g.spectral_flatness:.2f} (noise-like)")
    if stable_pitch_ratio < 0.15 and g.rms > 1e-4:
        scores["ambience"] += 0.25
        reasons["ambience"].append("no consistent pitch across windows")
    if g.silence_ratio < 0.05 and g.dynamic_range_db < 12:
        scores["ambience"] += 0.25
        reasons["ambience"].append(f"continuous, low-dynamics bed ({g.dynamic_range_db:.1f} dB range)")
    if g.spectral_centroid < 800 and g.spectral_flatness > 0.1:
        scores["ambience"] += 0.15
        reasons["ambience"].append("low-centroid broadband bed (room tone / rumble)")

    total = sum(scores.values()) or 1.0
    probs = {k: round(v / total, 3) for k, v in scores.items()}
    label = max(probs, key=lambda k: probs[k])
    confidence = probs[label]

    return {
        "label": label,
        "confidence": round(confidence, 3),
        "probabilities": probs,
        "reasons": reasons[label],
        "voiced_ratio": round(voiced_ratio, 3),
    }


def synthetic_likelihood(audio: AudioData, global_features: FeatureSet,
                         timeline: Sequence[FeatureSet],
                         extras: Dict[str, Any]) -> Dict[str, Any]:
    """Score how likely the audio was generated in code (TTS / synth / render).

    Six independent cues are combined; each one is reported so the caller can
    audit the verdict instead of trusting a single number.
    """
    cues: List[Dict[str, Any]] = []
    score = 0.0

    # 1. Digital silence: real rooms never reach exactly zero.
    if timeline:
        absolute = sum(1 for f in timeline if f.rms < 1e-6)
        ratio = absolute / len(timeline)
        if ratio > 0.02:
            s = min(1.0, ratio * 4)
            score += s
            cues.append({"code": "digital_silence", "weight": round(s, 3),
                         "detail": f"{ratio:.0%} of windows are mathematically silent (no room tone)"})

    # 2. Over-smooth spectrum (typical of neural vocoders and simple synths).
    contrast = float(extras.get("spectral_contrast") or 0.0)
    if contrast > 0 and contrast < 12.0:
        s = min(1.0, (12.0 - contrast) / 8.0)
        score += s
        cues.append({"code": "smooth_spectrum", "weight": round(s, 3),
                     "detail": f"spectral contrast only {contrast:.1f} dB (unusually smooth)"})

    # 3. Missing high-frequency air.
    nyq = audio.sample_rate / 2 if audio.sample_rate else 0
    cutoff = global_features.high_cutoff_hz
    if nyq > 4000 and 0 < cutoff < nyq * 0.45 and not audio.lossy:
        s = min(1.0, (nyq * 0.45 - cutoff) / (nyq * 0.45))
        score += s
        cues.append({"code": "missing_air", "weight": round(s, 3),
                     "detail": f"energy stops at {cutoff:.0f} Hz on a lossless {int(nyq)} Hz-wide file"})

    # 4. Pitch stability beyond what a human performer produces.
    pitches = [f.pitch_hz for f in timeline if f.pitch_hz > 0]
    if len(pitches) >= 8:
        var = extras.get("pitch_variance", 0.0) or 0.0
        mean_p = sum(pitches) / len(pitches)
        cv = (var ** 0.5) / mean_p if mean_p > 0 else 0.0
        if cv < 0.01:
            s = min(1.0, (0.01 - cv) / 0.01)
            score += s
            cues.append({"code": "pitch_too_stable", "weight": round(s, 3),
                         "detail": f"pitch coefficient of variation {cv:.4f} is machine-stable"})

    # 5. Absent noise floor during quiet passages.
    quiet = [f.rms for f in timeline if f.rms > 0]
    if len(quiet) >= 4:
        floor = min(quiet)
        if floor > 0 and floor > 1e-3:
            pass
        elif floor <= 1e-5:
            score += 0.6
            cues.append({"code": "no_noise_floor", "weight": 0.6,
                         "detail": "quietest passage has no measurable noise floor"})

    # 6. Perfectly periodic envelope (looped / metronomic synthesis).
    env = extras.get("envelope") or []
    if len(env) > 64:
        half = len(env) // 2
        a, b = env[:half], env[half:2 * half]
        ma = sum(a) / len(a)
        mb = sum(b) / len(b)
        denom = (ma + mb) or 1.0
        if abs(ma - mb) / denom < 0.01 and ma > 1e-4:
            score += 0.5
            cues.append({"code": "static_level", "weight": 0.5,
                         "detail": "loudness envelope is statistically identical across halves"})

    probability = 1.0 / (1.0 + pow(2.718281828459045, -(score - 1.8) * 1.4))
    return {
        "probability": round(min(0.99, max(0.01, probability)), 3),
        "raw_score": round(score, 3),
        "verdict": "likely synthetic" if probability > 0.6 else (
            "likely recorded" if probability < 0.35 else "inconclusive"),
        "cues": cues,
    }
