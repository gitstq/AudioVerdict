"""JSON / plain-text / Markdown renderers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..analysis.notes import describe_file, summary
from ..models import AnalysisResult
from .waveform import spectrum_svg, timeline_svg, waveform_svg

SEVERITY_ICON = {"info": "ℹ️", "low": "🟡", "medium": "🟠", "high": "🔴"}


def to_json(result: AnalysisResult, pretty: bool = True) -> str:
    payload = result.as_dict()
    payload["summary"] = describe_file(result, lang="en")
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def to_text(result: AnalysisResult, lang: str = "en") -> str:
    zh = lang.startswith("zh")
    c = result.container or {}
    g = result.global_features
    sc = result.scorecard or {}
    lines: List[str] = []

    lines.append("=" * 68)
    lines.append(f"AudioVerdict · {c.get('format')} · {c.get('codec')}")
    lines.append("=" * 68)
    lines.append(f"  duration      : {c.get('duration_seconds')} s")
    lines.append(f"  sample rate   : {c.get('sample_rate')} Hz")
    lines.append(f"  channels      : {c.get('channels')}")
    lines.append(f"  bitrate       : {c.get('bitrate_bps')} bps")
    lines.append(f"  PCM decoded   : {c.get('pcm_decoded')}")
    if g:
        lines.append("-" * 68)
        lines.append(f"  loudness      : {g.loudness_lufs} LUFS (peak {g.peak_dbfs} dBFS)")
        lines.append(f"  centroid      : {g.spectral_centroid:.0f} Hz")
        lines.append(f"  bandwidth     : up to {g.high_cutoff_hz:.0f} Hz")
        lines.append(f"  flatness      : {g.spectral_flatness:.3f}")
        if g.pitch_hz:
            lines.append(f"  pitch         : {g.pitch_hz:.1f} Hz (harmonicity {g.harmonicity:.2f})")
    if result.classification:
        cl = result.classification
        lines.append("-" * 68)
        lines.append(f"  content       : {cl.get('label')} (confidence {cl.get('confidence')})")
        for r in cl.get("reasons", []):
            lines.append(f"                  · {r}")
    if sc:
        lines.append("-" * 68)
        lines.append(f"  score         : {sc.get('overall')}/100  grade {sc.get('grade')}")
        lines.append(f"  authenticity  : {sc.get('authenticity', {}).get('verdict')} "
                     f"(p={sc.get('authenticity', {}).get('probability')})")
        if sc.get("tempo", {}).get("bpm"):
            lines.append(f"  tempo         : {sc['tempo']['bpm']} BPM "
                         f"(confidence {sc['tempo'].get('confidence')})")
    if result.findings:
        lines.append("-" * 68)
        lines.append(f"  findings ({len(result.findings)})")
        for f in result.findings:
            icon = SEVERITY_ICON.get(f.severity, "•")
            lines.append(f"    {icon} [{f.severity}] {f.title}: {f.detail}")
    if result.notes:
        lines.append("-" * 68)
        lines.append("  listening notes")
        for n in result.notes[:12]:
            lines.append(f"    {n.start:6.2f}-{n.end:6.2f}s  {n.text}")
    lines.append("=" * 68)
    lines.append(describe_file(result, lang="en") if not zh else describe_file(result, lang="zh"))
    return "\n".join(lines)


def to_markdown(result: AnalysisResult, lang: str = "en",
                embed_svg: bool = False) -> str:
    zh = lang.startswith("zh")
    T = _T(zh)
    c = result.container or {}
    g = result.global_features
    sc = result.scorecard or {}
    out: List[str] = []

    out.append("# 🎧 AudioVerdict Report")
    out.append("")
    out.append(f"> {describe_file(result, lang='zh' if zh else 'en')}")
    out.append("")
    out.append(f"**{T['path']}**: `{result.path}`")
    out.append("")
    out.append("## 📦 " + T["container"])
    out.append("")
    out.append(f"| {T['field']} | {T['value']} |")
    out.append("|---|---|")
    for k, label in (("format", T["format"]), ("codec", T["codec"]),
                     ("duration_seconds", T["duration"]), ("sample_rate", T["rate"]),
                     ("channels", T["channels"]), ("bitrate_bps", T["bitrate"]),
                     ("pcm_decoded", T["decoded"]), ("lossy", T["lossy"])):
        out.append(f"| {label} | `{c.get(k)}` |")
    out.append("")

    if g:
        out.append("## 📊 " + T["features"])
        out.append("")
        out.append(f"| {T['field']} | {T['value']} |")
        out.append("|---|---|")
        out.append(f"| {T['loudness']} | {g.loudness_lufs} LUFS |")
        out.append(f"| {T['peak']} | {g.peak_dbfs} dBFS |")
        out.append(f"| {T['range']} | {g.dynamic_range_db:.1f} dB |")
        out.append(f"| {T['centroid']} | {g.spectral_centroid:.0f} Hz |")
        out.append(f"| {T['bandwidth']} | {g.high_cutoff_hz:.0f} Hz |")
        out.append(f"| {T['flatness']} | {g.spectral_flatness:.3f} |")
        out.append(f"| {T['zcr']} | {g.zero_crossing_rate:.4f} |")
        if g.pitch_hz:
            out.append(f"| {T['pitch']} | {g.pitch_hz:.1f} Hz ({T['harmonicity']} {g.harmonicity:.2f}) |")
        out.append("")

    if embed_svg:
        extras_wave = ((result.scorecard or {}).get("_visuals") or {}).get("envelope")
        if extras_wave:
            out.append("### " + T["waveform"])
            out.append("")
            out.append(waveform_svg(extras_wave))
            out.append("")

    if result.classification:
        cl = result.classification
        out.append("## 🏷️ " + T["classification"])
        out.append("")
        out.append(f"- **{T['label']}**: `{cl.get('label')}` ({T['confidence']} {cl.get('confidence')})")
        probs = cl.get("probabilities", {})
        if probs:
            out.append(f"- **{T['distribution']}**: " + ", ".join(
                f"{k} {v:.0%}" for k, v in sorted(probs.items(), key=lambda x: -x[1]) if v))
        for r in cl.get("reasons", []):
            out.append(f"- {r}")
        out.append("")

    if sc:
        out.append("## 🧮 " + T["scorecard"])
        out.append("")
        out.append(f"| {T['dimension']} | {T['score']} |")
        out.append("|---|---|")
        out.append(f"| {T['overall']} | **{sc.get('overall')}/100 ({sc.get('grade')})** |")
        out.append(f"| {T['quality']} | {sc.get('quality', {}).get('score')} |")
        out.append(f"| {T['authenticity']} | {sc.get('authenticity', {}).get('score')} |")
        out.append(f"| {T['usability']} | {sc.get('usability', {}).get('score')} |")
        auth = sc.get("authenticity", {})
        out.append("")
        out.append(f"- {T['verdict']}: **{auth.get('verdict')}** "
                   f"({T['probability']} {auth.get('probability')})")
        for cue in auth.get("cues", []):
            out.append(f"  - `{cue['code']}` ({cue['weight']}): {cue['detail']}")
        if sc.get("tempo", {}).get("bpm"):
            out.append(f"- {T['tempo']}: **{sc['tempo']['bpm']} BPM** "
                       f"({T['confidence']} {sc['tempo'].get('confidence')})")
        dm = sc.get("description_match")
        if dm:
            out.append(f"- {T['match']}: **{dm.get('verdict')}** ({dm.get('score')})")
            for chk in dm.get("checks", []):
                mark = "✅" if chk["matched"] else "❌"
                out.append(f"  - {mark} `{chk['term']}` — {T['expected']} {chk['expected']}, "
                           f"{T['actual']} {chk['actual']}")
        out.append("")

    if result.findings:
        out.append("## 🔍 " + T["findings"])
        out.append("")
        out.append(f"| {T['severity']} | {T['title']} | {T['confidence']} | {T['detail']} |")
        out.append("|---|---|---|---|")
        for f in result.findings:
            icon = SEVERITY_ICON.get(f.severity, "•")
            out.append(f"| {icon} {f.severity} | {f.title} | {f.confidence} | {f.detail} |")
        out.append("")

    if result.segments:
        out.append("## ⭐ " + T["highlights"])
        out.append("")
        for s in result.segments:
            out.append(f"- `{s.start:.2f}s – {s.end:.2f}s` — {T['score']} {s.score:.2f}")
        out.append("")

    if result.notes:
        out.append("## 📝 " + T["notes"])
        out.append("")
        for n in result.notes:
            tags = " ".join(f"`{t}`" for t in n.tags) if n.tags else ""
            out.append(f"- **{n.start:.2f}–{n.end:.2f}s** {tags} — {n.text}")
        out.append("")

    if result.fingerprints:
        fp = result.fingerprints[0]
        out.append("## 🔑 " + T["fingerprint"])
        out.append("")
        out.append(f"- {T['algorithm']}: `{fp.get('algorithm')}`")
        out.append(f"- {T['digest']}: `{fp.get('digest')}`")
        out.append(f"- {T['hashes']}: {fp.get('hash_count')}")
        out.append("")

    if result.warnings:
        out.append("## ⚠️ " + T["warnings"])
        out.append("")
        for w in result.warnings:
            out.append(f"- {w}")
        out.append("")

    out.append("---")
    out.append("")
    out.append(f"_{T['footer']}_")
    return "\n".join(out)


def _T(zh: bool) -> Dict[str, str]:
    if zh:
        return {
            "path": "文件", "container": "容器信息", "field": "字段", "value": "值",
            "format": "格式", "codec": "编码", "duration": "时长(秒)", "rate": "采样率(Hz)",
            "channels": "声道", "bitrate": "比特率(bps)", "decoded": "已解码PCM",
            "lossy": "有损", "features": "核心特征", "loudness": "综合响度",
            "peak": "峰值", "range": "动态范围", "centroid": "频谱质心",
            "bandwidth": "有效带宽", "flatness": "频谱平坦度", "zcr": "过零率",
            "pitch": "基频", "harmonicity": "谐性", "classification": "内容分类",
            "label": "类别", "confidence": "置信度", "distribution": "概率分布",
            "scorecard": "评分卡", "dimension": "维度", "score": "得分",
            "overall": "综合", "quality": "技术质量", "authenticity": "真实性",
            "usability": "可用性", "verdict": "判定", "probability": "概率",
            "tempo": "速度", "match": "描述匹配", "expected": "期望", "actual": "实测",
            "findings": "取证发现", "severity": "等级", "title": "项目", "detail": "说明",
            "highlights": "高光片段", "notes": "听觉笔记", "fingerprint": "音频指纹",
            "algorithm": "算法", "digest": "摘要", "hashes": "哈希数",
            "warnings": "警告", "footer": "由 AudioVerdict 零依赖音频证据引擎生成",
            "waveform": "波形",
        }
    return {
        "path": "File", "container": "Container", "field": "Field", "value": "Value",
        "format": "Format", "codec": "Codec", "duration": "Duration (s)",
        "rate": "Sample rate (Hz)", "channels": "Channels", "bitrate": "Bitrate (bps)",
        "decoded": "PCM decoded", "lossy": "Lossy", "features": "Core features",
        "loudness": "Integrated loudness", "peak": "Peak", "range": "Dynamic range",
        "centroid": "Spectral centroid", "bandwidth": "Usable bandwidth",
        "flatness": "Spectral flatness", "zcr": "Zero-crossing rate",
        "pitch": "Fundamental", "harmonicity": "harmonicity",
        "classification": "Content classification", "label": "Label",
        "confidence": "confidence", "distribution": "Distribution",
        "scorecard": "Scorecard", "dimension": "Dimension", "score": "Score",
        "overall": "Overall", "quality": "Technical quality",
        "authenticity": "Authenticity", "usability": "Usability",
        "verdict": "Verdict", "probability": "probability", "tempo": "Tempo",
        "match": "Description match", "expected": "expected", "actual": "actual",
        "findings": "Forensic findings", "severity": "Severity", "title": "Finding",
        "detail": "Detail", "highlights": "Highlights", "notes": "Listening notes",
        "fingerprint": "Fingerprint", "algorithm": "Algorithm", "digest": "Digest",
        "hashes": "Hashes", "warnings": "Warnings",
        "footer": "Generated by AudioVerdict, the zero-dependency audio evidence engine",
        "waveform": "Waveform",
    }
