"""Turn numeric features into words an agent (or a human) can read.

This is the piece that makes audio *evidence* rather than a waveform picture:
every sentence is derived from a measured feature, and the measurements stay
attached so the claim can be checked.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from ..models import FeatureSet, Note

STRINGS = {
    "zh": {
        "silent": "几乎无声",
        "very_quiet": "极轻",
        "quiet": "偏轻",
        "moderate": "音量适中",
        "loud": "偏响",
        "very_loud": "很响",
        "dark": "低沉",
        "warm": "温暖",
        "neutral": "中性",
        "bright": "明亮",
        "harsh": "尖锐刺耳",
        "tonal": "谐波清晰",
        "balanced": "音色平衡",
        "noisy": "噪声感明显",
        "steady": "平稳",
        "evolving": "持续变化",
        "erratic": "剧烈起伏",
        "pitched": "基频约 {hz:.0f} Hz",
        "clipped": "，存在削波",
        "silence": "，静音段",
        "summary": "这是一段 {dur:.1f} 秒的音频：{label}。整体{level}，音色{bright}，{timbre}，{activity}。",
        "seg": "{t0:.1f}-{t1:.1f}s：{level}、{bright}、{timbre}",
    },
    "en": {
        "silent": "near silence",
        "very_quiet": "very quiet",
        "quiet": "soft",
        "moderate": "moderate level",
        "loud": "loud",
        "very_loud": "very loud",
        "dark": "dark",
        "warm": "warm",
        "neutral": "neutral",
        "bright": "bright",
        "harsh": "harsh",
        "tonal": "clearly harmonic",
        "balanced": "balanced timbre",
        "noisy": "noise-dominated",
        "steady": "steady",
        "evolving": "constantly evolving",
        "erratic": "erratic",
        "pitched": "fundamental around {hz:.0f} Hz",
        "clipped": " with clipping",
        "silence": ", silent passage",
        "summary": "A {dur:.1f} s recording: {label}. Overall {level}, {bright} timbre, {timbre}, {activity}.",
        "seg": "{t0:.1f}-{t1:.1f}s: {level}, {bright}, {timbre}",
    },
}


def _level(f: FeatureSet, s: Dict[str, str]) -> str:
    if f.rms < 1e-5:
        return s["silent"]
    if f.loudness_lufs < -45:
        return s["very_quiet"]
    if f.loudness_lufs < -30:
        return s["quiet"]
    if f.loudness_lufs < -18:
        return s["moderate"]
    if f.loudness_lufs < -9:
        return s["loud"]
    return s["very_loud"]


def _brightness(f: FeatureSet, s: Dict[str, str]) -> str:
    c = f.spectral_centroid
    if c <= 0:
        return s["neutral"]
    if c < 500:
        return s["dark"]
    if c < 1500:
        return s["warm"]
    if c < 4000:
        return s["neutral"]
    if c < 8000:
        return s["bright"]
    return s["harsh"]


def _timbre(f: FeatureSet, s: Dict[str, str]) -> str:
    if f.spectral_flatness > 0.2:
        return s["noisy"]
    if f.harmonicity > 0.7:
        return s["tonal"]
    return s["balanced"]


def _activity(f: FeatureSet, mean_flux: float, s: Dict[str, str]) -> str:
    if mean_flux <= 0:
        return s["steady"]
    ratio = f.spectral_flux / mean_flux
    if ratio < 0.6:
        return s["steady"]
    if ratio < 1.8:
        return s["evolving"]
    return s["erratic"]


def describe_window(f: FeatureSet, mean_flux: float, lang: str = "en") -> str:
    s = STRINGS.get(lang, STRINGS["en"])
    parts: List[str] = []
    parts.append(_level(f, s))
    parts.append(_brightness(f, s))
    parts.append(_timbre(f, s))
    parts.append(_activity(f, mean_flux, s))
    if f.pitch_hz > 40 and f.harmonicity > 0.6:
        parts.append(s["pitched"].format(hz=f.pitch_hz))
    if f.clipping_ratio > 0.001:
        parts.append(s["clipped"].lstrip("，, "))
    text = "、".join(parts) if lang == "zh" else ", ".join(parts)
    return text


def build_notes(timeline: Sequence[FeatureSet], lang: str = "en",
                max_notes: int = 40) -> List[Note]:
    """One note per window, merging consecutive windows with identical wording."""
    if not timeline:
        return []
    s = STRINGS.get(lang, STRINGS["en"])
    mean_flux = sum(f.spectral_flux for f in timeline) / len(timeline) + 1e-12

    raw: List[Note] = []
    for f in timeline:
        text = describe_window(f, mean_flux, lang)
        tags: List[str] = []
        if f.rms < 1e-5:
            tags.append("silence")
        if f.pitch_hz > 0 and f.harmonicity > 0.6:
            tags.append("pitched")
        if f.spectral_flatness > 0.2:
            tags.append("noisy")
        if f.clipping_ratio > 0.001:
            tags.append("clipped")
        raw.append(Note(start=f.start, end=f.end, text=text, tags=tags))

    merged: List[Note] = []
    for n in raw:
        if merged and merged[-1].text == n.text:
            merged[-1].end = n.end
        else:
            merged.append(Note(start=n.start, end=n.end, text=n.text, tags=list(n.tags)))

    if len(merged) > max_notes:
        step = len(merged) / float(max_notes)
        merged = [merged[int(i * step)] for i in range(max_notes)]
    return merged


def summary(global_features: FeatureSet, classification: Dict[str, Any],
            duration: float, lang: str = "en") -> str:
    s = STRINGS.get(lang, STRINGS["en"])
    mean_flux = 0.0
    label = classification.get("label", "unknown")
    return s["summary"].format(
        dur=duration,
        label=label,
        level=_level(global_features, s),
        bright=_brightness(global_features, s),
        timbre=_timbre(global_features, s),
        activity=_activity(global_features, mean_flux + 1e-12, s),
    )


def describe_file(result: Any, lang: str = "en") -> str:
    """Long-form 'what does this file sound like' paragraph."""
    g: FeatureSet = result.global_features or FeatureSet()
    c: Dict[str, Any] = result.classification or {}
    s = STRINGS.get(lang, STRINGS["en"])
    decoded = bool((result.container or {}).get("pcm_decoded"))

    if not decoded:
        fmt = (result.container or {}).get("format", "?")
        codec = (result.container or {}).get("codec", "?")
        dur = (result.container or {}).get("duration_seconds")
        if lang == "zh":
            return (f"该文件为 {fmt} / {codec}，时长约 {dur} 秒。容器已完整解析，"
                    f"但未取得 PCM 样本（本机无可选 ffmpeg 助手），因此仅提供容器级证据："
                    f"帧链/页链一致性、编码参数与元数据，不做声学测量。")
        return (f"A {fmt} / {codec} file of about {dur} s. The container was fully parsed "
                f"but no PCM samples were available (the optional ffmpeg helper is not "
                f"installed), so this report covers container-level evidence only: "
                f"frame/page chain consistency, codec parameters and metadata.")

    if lang == "zh":
        bits = [
            f"整体音量 {g.loudness_lufs:.1f} LUFS，峰值 {g.peak_dbfs:.1f} dBFS，动态范围约 {g.dynamic_range_db:.1f} dB。",
            f"频谱质心 {g.spectral_centroid:.0f} Hz，有效带宽上限约 {g.high_cutoff_hz:.0f} Hz。",
        ]
        if g.pitch_hz:
            bits.append(f"主基频约 {g.pitch_hz:.0f} Hz（谐性 {g.harmonicity:.2f}）。")
        bits.append(f"内容判定为 {c.get('label')}（置信度 {c.get('confidence')}）。")
        synth = (result.scorecard or {}).get("authenticity") or {}
        if synth.get("verdict"):
            bits.append(f"真实性：{synth.get('verdict')}（合成概率 {synth.get('probability')}）。")
        if result.findings:
            bits.append(f"发现 {len(result.findings)} 条取证线索。")
        return "".join(bits)

    bits = [
        f"Integrated loudness {g.loudness_lufs:.1f} LUFS, peak {g.peak_dbfs:.1f} dBFS, "
        f"dynamic range about {g.dynamic_range_db:.1f} dB.",
        f"Spectral centroid {g.spectral_centroid:.0f} Hz, usable bandwidth to roughly "
        f"{g.high_cutoff_hz:.0f} Hz.",
    ]
    if g.pitch_hz:
        bits.append(f"Dominant fundamental near {g.pitch_hz:.0f} Hz "
                    f"(harmonicity {g.harmonicity:.2f}).")
    bits.append(f"Classified as {c.get('label')} with confidence {c.get('confidence')}.")
    synth = (result.scorecard or {}).get("authenticity") or {}
    if synth.get("verdict"):
        bits.append(f"Authenticity: {synth.get('verdict')} "
                    f"(synthetic probability {synth.get('probability')}).")
    if result.findings:
        bits.append(f"{len(result.findings)} forensic finding(s) recorded.")
    return " ".join(bits)
