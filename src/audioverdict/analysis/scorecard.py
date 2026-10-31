"""Composite scorecard: technical quality, authenticity, usability."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..dsp import beat_grid, estimate_bpm
from ..models import AnalysisResult, AudioData, FeatureSet, Finding

SEVERITY_PENALTY = {"info": 0.0, "low": 2.0, "medium": 6.0, "high": 14.0}


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def build(audio: AudioData, global_features: FeatureSet,
          timeline: Sequence[FeatureSet], findings: Sequence[Finding],
          classification: Dict[str, Any], synthetic: Dict[str, Any],
          extras: Dict[str, Any]) -> Dict[str, Any]:
    g = global_features

    # --- technical quality ------------------------------------------------
    tech = 100.0
    notes: List[str] = []
    if -23.0 <= g.loudness_lufs <= -14.0:
        pass                                    # broadcast-friendly window
    elif g.loudness_lufs < -40:
        tech -= 15
        notes.append(f"very quiet ({g.loudness_lufs:.1f} LUFS)")
    elif g.loudness_lufs > -6:
        tech -= 12
        notes.append(f"very hot ({g.loudness_lufs:.1f} LUFS)")
    else:
        tech -= 4
        notes.append(f"loudness {g.loudness_lufs:.1f} LUFS sits outside -23..-14 LUFS")
    if g.clipping_ratio > 0.0001:
        tech -= min(25, g.clipping_ratio * 2000)
        notes.append("clipping detected")
    if abs(g.dc_offset) > 0.001:
        tech -= 6
        notes.append("DC offset present")
    if g.dynamic_range_db < 6 and g.rms > 0.01:
        tech -= 12
        notes.append(f"dynamic range only {g.dynamic_range_db:.1f} dB")
    if audio.sample_rate and audio.sample_rate < 16000:
        tech -= 8
        notes.append(f"low sample rate ({audio.sample_rate} Hz)")

    # --- authenticity -----------------------------------------------------
    auth = 100.0 - 45.0 * float(synthetic.get("probability", 0.0))
    for f in findings:
        auth -= SEVERITY_PENALTY.get(f.severity, 0.0) * f.confidence
    auth = max(0.0, min(100.0, auth))

    # --- usability ---------------------------------------------------------
    use = 100.0
    if audio.duration <= 0:
        use -= 40
    elif audio.duration < 0.5:
        use -= 15
        notes.append("shorter than 0.5 s")
    if not audio.decoded:
        use -= 25
        notes.append("container parsed but PCM not decoded (limited analysis)")
    if audio.channels == 0:
        use -= 10
    if audio.lossy:
        use -= 8
        notes.append("lossy source")

    overall = round(0.40 * max(0.0, tech) + 0.35 * auth + 0.25 * max(0.0, use), 1)

    # --- tempo -------------------------------------------------------------
    env = extras.get("envelope") or []
    hop = float(extras.get("envelope_hop_seconds") or 0.01)
    bpm, bpm_conf = estimate_bpm(env, hop) if len(env) > 16 else (0.0, 0.0)
    beats = beat_grid(env, hop, bpm)[:32] if bpm else []

    return {
        "overall": overall,
        "grade": _grade(overall),
        "quality": {"score": round(max(0.0, tech), 1), "notes": notes},
        "authenticity": {
            "score": round(auth, 1),
            "probability": synthetic.get("probability"),
            "verdict": synthetic.get("verdict"),
            "cues": synthetic.get("cues", []),
        },
        "usability": {"score": round(max(0.0, use), 1),
                      "decoded": audio.decoded,
                      "duration": round(audio.duration, 3)},
        "tempo": {"bpm": bpm, "confidence": bpm_conf, "beats": beats},
        "content": classification,
    }


def apply_to(result: AnalysisResult) -> None:
    """Attach a human-readable one-liner to the result."""
    sc = result.scorecard or {}
    result.scorecard = dict(sc)
    result.scorecard["headline"] = (
        f"{sc.get('grade', '?')} ({sc.get('overall', 0)}/100) - "
        f"{(result.classification or {}).get('label', 'unknown')}, "
        f"{sc.get('authenticity', {}).get('verdict', 'unknown')}"
    )
