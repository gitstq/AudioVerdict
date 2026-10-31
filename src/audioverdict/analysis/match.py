"""Check an audio file against a free-text description.

This answers the question an agent actually has: *"does this file match what
the user asked for?"* Each recognised term becomes an explicit expectation with
a measured value, so a mismatch can be explained instead of just reported.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import AnalysisResult, FeatureSet

# term -> (kind, expected, weight)
LEXICON: Dict[str, tuple] = {
    # brightness
    "低沉": ("centroid_max", 800, 1.0), "低音": ("centroid_max", 800, 1.0),
    "深沉": ("centroid_max", 800, 1.0), "dark": ("centroid_max", 800, 1.0),
    "deep": ("centroid_max", 800, 1.0), "bass": ("band_low_min", 0.25, 1.0),
    "温暖": ("centroid_range", (300, 2000), 0.8), "warm": ("centroid_range", (300, 2000), 0.8),
    "明亮": ("centroid_min", 3000, 1.0), "bright": ("centroid_min", 3000, 1.0),
    "尖锐": ("centroid_min", 6000, 1.0), "harsh": ("centroid_min", 6000, 1.0),
    # voice
    "男声": ("pitch_range", (70, 180), 1.2), "male": ("pitch_range", (70, 180), 1.2),
    "女声": ("pitch_range", (160, 300), 1.2), "female": ("pitch_range", (160, 300), 1.2),
    "儿童": ("pitch_range", (250, 500), 1.0), "child": ("pitch_range", (250, 500), 1.0),
    # content
    "语音": ("label", "speech", 1.2), "说话": ("label", "speech", 1.2),
    "speech": ("label", "speech", 1.2), "voice": ("label", "speech", 1.0),
    "独白": ("label", "speech", 1.0), "monologue": ("label", "speech", 1.0),
    "音乐": ("label", "music", 1.2), "music": ("label", "music", 1.2),
    "歌曲": ("label", "music", 1.2), "song": ("label", "music", 1.2),
    "环境": ("label", "ambience", 1.0), "ambient": ("label", "ambience", 1.0),
    "ambience": ("label", "ambience", 1.0),
    "噪声": ("flatness_min", 0.2, 1.0), "嘈杂": ("flatness_min", 0.2, 1.0),
    "noisy": ("flatness_min", 0.2, 1.0), "noise": ("flatness_min", 0.2, 1.0),
    "干净": ("clean", True, 1.0), "clean": ("clean", True, 1.0),
    "清晰": ("clean", True, 0.8),
    # level
    "安静": ("lufs_max", -30, 1.0), "quiet": ("lufs_max", -30, 1.0),
    "轻声": ("lufs_max", -30, 1.0),
    "响亮": ("lufs_min", -18, 1.0), "loud": ("lufs_min", -18, 1.0),
    "大声": ("lufs_min", -18, 1.0),
    # tempo
    "快": ("bpm_min", 120, 0.8), "fast": ("bpm_min", 120, 0.8),
    "慢": ("bpm_max", 90, 0.8), "slow": ("bpm_max", 90, 0.8),
    # channels
    "立体声": ("channels", 2, 1.0), "stereo": ("channels", 2, 1.0),
    "单声道": ("channels", 1, 1.0), "mono": ("channels", 1, 1.0),
    # provenance
    "真实录音": ("authentic", True, 1.0), "recording": ("authentic", True, 0.8),
    "现场": ("authentic", True, 0.8), "live": ("authentic", True, 0.8),
    "合成": ("synthetic", True, 1.0), "synthetic": ("synthetic", True, 1.0),
    "tts": ("synthetic", True, 1.0), "ai生成": ("synthetic", True, 1.0),
}


def match(result: AnalysisResult, description: str) -> Dict[str, Any]:
    g: FeatureSet = result.global_features or FeatureSet()
    text = (description or "").lower()
    checks: List[Dict[str, Any]] = []
    hit_weight = 0.0
    total_weight = 0.0

    for term, (kind, expected, weight) in LEXICON.items():
        key = term.lower()
        if key not in text and term not in description:
            continue
        total_weight += weight
        ok = False
        actual: Any = None

        if kind == "centroid_max":
            actual = round(g.spectral_centroid, 1)
            ok = g.spectral_centroid <= expected
        elif kind == "centroid_min":
            actual = round(g.spectral_centroid, 1)
            ok = g.spectral_centroid >= expected
        elif kind == "centroid_range":
            actual = round(g.spectral_centroid, 1)
            ok = expected[0] <= g.spectral_centroid <= expected[1]
        elif kind == "band_low_min":
            actual = round(sum(g.band_energy[:2]), 3) if g.band_energy else 0.0
            ok = actual >= expected
        elif kind == "pitch_range":
            actual = round(g.pitch_hz, 1)
            ok = expected[0] <= g.pitch_hz <= expected[1]
        elif kind == "label":
            actual = result.classification.get("label")
            ok = actual == expected
        elif kind == "flatness_min":
            actual = round(g.spectral_flatness, 4)
            ok = g.spectral_flatness >= expected
        elif kind == "clean":
            actual = round(g.clipping_ratio, 6)
            ok = g.clipping_ratio < 1e-4 and abs(g.dc_offset) < 0.005
        elif kind == "lufs_max":
            actual = round(g.loudness_lufs, 2)
            ok = g.loudness_lufs <= expected
        elif kind == "lufs_min":
            actual = round(g.loudness_lufs, 2)
            ok = g.loudness_lufs >= expected
        elif kind == "bpm_min":
            actual = (result.scorecard or {}).get("tempo", {}).get("bpm", 0)
            ok = actual >= expected
        elif kind == "bpm_max":
            actual = (result.scorecard or {}).get("tempo", {}).get("bpm", 0)
            ok = 0 < actual <= expected
        elif kind == "channels":
            actual = result.container.get("channels")
            ok = actual == expected
        elif kind == "authentic":
            prob = (result.scorecard or {}).get("authenticity", {}).get("probability", 0.5)
            actual = prob
            ok = prob < 0.4
        elif kind == "synthetic":
            prob = (result.scorecard or {}).get("authenticity", {}).get("probability", 0.5)
            actual = prob
            ok = prob > 0.6

        if ok:
            hit_weight += weight
        checks.append({"term": term, "expectation": kind, "expected": expected,
                       "actual": actual, "matched": ok, "weight": weight})

    score = round(hit_weight / total_weight, 3) if total_weight else 0.0
    recognised = bool(checks)
    return {
        "description": description,
        "score": score,
        "verdict": ("match" if score >= 0.75 else
                    "partial" if score >= 0.4 else "mismatch") if recognised else "no_terms",
        "checks": checks,
        "recognised_terms": len(checks),
        "note": ("none of the description terms were recognised" if not recognised else ""),
    }
