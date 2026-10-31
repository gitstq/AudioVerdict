"""Hand-built SVG charts (no plotting library involved)."""

from __future__ import annotations

import math
from typing import List, Sequence

WIDTH = 900
HEIGHT = 200


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def waveform_svg(envelope_values: Sequence[float], width: int = WIDTH,
                 height: int = HEIGHT, title: str = "Loudness envelope") -> str:
    """Symmetric bar-style waveform from an RMS envelope."""
    if not envelope_values:
        return ""
    peak = max(envelope_values) or 1.0
    n = len(envelope_values)
    mid = height / 2
    step = width / max(1, n)
    bars: List[str] = []
    for i, v in enumerate(envelope_values):
        h = (v / peak) * (mid - 6)
        x = i * step
        w = max(0.6, step * 0.8)
        bars.append(
            f'<rect x="{x:.2f}" y="{mid - h:.2f}" width="{w:.2f}" height="{2 * h:.2f}" '
            f'fill="var(--avd-accent, #4f8cff)" opacity="0.85"/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{_esc(title)}" class="avd-wave">'
        f'<rect width="{width}" height="{height}" fill="var(--avd-bg, #0f1115)"/>'
        f'<line x1="0" y1="{mid}" x2="{width}" y2="{mid}" stroke="var(--avd-grid, #2a2f3a)"/>'
        + "".join(bars) +
        "</svg>"
    )


def spectrum_svg(spectrum_values: Sequence[float], sample_rate: int,
                 width: int = WIDTH, height: int = HEIGHT) -> str:
    """Log-frequency magnitude curve."""
    n = len(spectrum_values)
    if n < 4 or not sample_rate:
        return ""
    peak = max(spectrum_values) or 1.0
    nyq = sample_rate / 2
    pts: List[str] = []
    steps = min(n - 1, 400)
    for i in range(1, steps + 1):
        idx = int((i / steps) ** 2.0 * (n - 1))
        idx = max(1, min(n - 1, idx))
        f = idx * nyq / (n - 1)
        x = math.log10(max(20.0, f)) / math.log10(max(25.0, nyq)) * width
        db = 20 * math.log10((spectrum_values[idx] + 1e-12) / peak)
        y = height - (max(-80.0, db) + 80.0) / 80.0 * height
        pts.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(pts)

    ticks = ""
    for f in (100, 1000, 10000):
        if f >= nyq:
            continue
        x = math.log10(f) / math.log10(max(25.0, nyq)) * width
        ticks += (f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" '
                  f'stroke="var(--avd-grid, #2a2f3a)" stroke-dasharray="3 3"/>'
                  f'<text x="{x + 3:.1f}" y="{height - 5}" fill="var(--avd-dim, #7a8290)" '
                  f'font-size="11">{f}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Average spectrum" class="avd-spec">'
        f'<rect width="{width}" height="{height}" fill="var(--avd-bg, #0f1115)"/>'
        + ticks +
        f'<polyline points="{polyline}" fill="none" stroke="var(--avd-accent2, #38d39f)" '
        f'stroke-width="1.6"/></svg>'
    )


def timeline_svg(timeline: Sequence[object], width: int = WIDTH,
                 height: int = HEIGHT) -> str:
    """Two overlaid curves: loudness (filled) and brightness (line)."""
    if not timeline:
        return ""
    n = len(timeline)
    lufs = [t.loudness_lufs for t in timeline]          # type: ignore[attr-defined]
    cent = [t.spectral_centroid for t in timeline]      # type: ignore[attr-defined]
    lo, hi = -60.0, 0.0
    max_c = max(cent) or 1.0
    step = width / max(1, n - 1)

    pts_l: List[str] = []
    pts_c: List[str] = []
    for i, (l, c) in enumerate(zip(lufs, cent)):
        x = i * step
        y = height - (max(lo, min(hi, l)) - lo) / (hi - lo) * height
        pts_l.append(f"{x:.1f},{y:.1f}")
        y2 = height - (c / max_c) * (height - 10) - 5
        pts_c.append(f"{x:.1f},{y2:.1f}")

    area = f"0,{height} " + " ".join(pts_l) + f" {width},{height}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Feature timeline" class="avd-time">'
        f'<rect width="{width}" height="{height}" fill="var(--avd-bg, #0f1115)"/>'
        f'<polygon points="{area}" fill="var(--avd-accent, #4f8cff)" opacity="0.25"/>'
        f'<polyline points="{" ".join(pts_l)}" fill="none" '
        f'stroke="var(--avd-accent, #4f8cff)" stroke-width="1.8"/>'
        f'<polyline points="{" ".join(pts_c)}" fill="none" '
        f'stroke="var(--avd-warn, #ffb454)" stroke-width="1.4" stroke-dasharray="4 3"/>'
        "</svg>"
    )
