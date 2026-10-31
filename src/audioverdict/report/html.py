"""Self-contained HTML report (inline CSS + inline SVG, no external assets)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..analysis.notes import describe_file
from ..models import AnalysisResult
from .render import SEVERITY_ICON
from .waveform import spectrum_svg, timeline_svg, waveform_svg

CSS = """
:root{--avd-bg:#0f1115;--avd-card:#171a21;--avd-fg:#e6e9ef;--avd-dim:#9aa3b2;
--avd-accent:#4f8cff;--avd-accent2:#38d39f;--avd-warn:#ffb454;--avd-bad:#ff5c5c;
--avd-grid:#2a2f3a;--avd-border:#242a34;}
*{box-sizing:border-box}
body{margin:0;background:var(--avd-bg);color:var(--avd-fg);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",
"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
.wrap{max-width:1000px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:34px 0 12px;padding-left:10px;border-left:4px solid var(--avd-accent)}
.sub{color:var(--avd-dim);margin:0 0 20px}
.card{background:var(--avd-card);border:1px solid var(--avd-border);border-radius:12px;
padding:16px 18px;margin:12px 0}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--avd-border)}
th{color:var(--avd-dim);font-weight:600}
code{background:#0b0d11;padding:2px 6px;border-radius:5px;font-size:13px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;
border:1px solid var(--avd-border);margin-right:6px}
.b-A{background:#0f3d2e;color:var(--avd-accent2)}
.b-B{background:#123a2a;color:#7ee2bd}
.b-C{background:#3a3110;color:var(--avd-warn)}
.b-D,.b-F{background:#3d1518;color:var(--avd-bad)}
svg{width:100%;height:auto;border-radius:10px;display:block;margin:10px 0;
border:1px solid var(--avd-border)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--avd-card);border:1px solid var(--avd-border);border-radius:10px;
padding:12px 14px}
.kpi .k{color:var(--avd-dim);font-size:12px}
.kpi .v{font-size:20px;font-weight:600;margin-top:2px}
ul{margin:8px 0;padding-left:20px}
li{margin:3px 0}
.note{border-left:3px solid var(--avd-accent);padding:2px 0 2px 10px;margin:6px 0}
.foot{color:var(--avd-dim);font-size:12px;margin-top:40px;text-align:center}
"""


def _esc(t: Any) -> str:
    s = str(t)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def to_html(result: AnalysisResult, lang: str = "en") -> str:
    c = result.container or {}
    g = result.global_features
    sc = result.scorecard or {}
    extras = result.scorecard.get("_visuals") or {} if sc else {}

    parts: List[str] = []
    a = parts.append
    a("<!doctype html><html lang='%s'><head><meta charset='utf-8'>" % ("zh" if lang.startswith("zh") else "en"))
    a("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    a("<title>AudioVerdict · %s</title><style>%s</style></head><body><div class='wrap'>" % (
        _esc(c.get("format", "audio")), CSS))
    a("<h1>🎧 AudioVerdict</h1>")
    a("<p class='sub'>%s</p>" % _esc(describe_file(result, lang=lang)))
    a("<div class='card'><code>%s</code></div>" % _esc(result.path))

    # KPI strip
    a("<div class='grid'>")
    for k, v in (("Overall", f"{sc.get('overall', '-')}/100"),
                 ("Grade", sc.get('grade', '-')),
                 ("Content", (result.classification or {}).get('label', '-')),
                 ("Authenticity", sc.get('authenticity', {}).get('verdict', '-')),
                 ("Duration", f"{c.get('duration_seconds')} s"),
                 ("Rate", f"{c.get('sample_rate')} Hz")):
        a("<div class='kpi'><div class='k'>%s</div><div class='v'>%s</div></div>" % (
            _esc(k), _esc(v)))
    a("</div>")

    # Visuals
    envelope = extras.get("envelope") or []
    spectrum = extras.get("average_spectrum") or []
    if envelope:
        a("<h2>🌊 Waveform</h2>")
        a(waveform_svg(envelope))
    if spectrum and c.get("sample_rate"):
        a("<h2>📈 Average spectrum</h2>")
        a(spectrum_svg(spectrum, int(c["sample_rate"])))
    if result.timeline:
        a("<h2>🕒 Feature timeline</h2>")
        a(timeline_svg(result.timeline))

    a("<h2>📦 Container</h2><table>")
    for k, label in (("format", "Format"), ("codec", "Codec"),
                     ("duration_seconds", "Duration (s)"), ("sample_rate", "Sample rate"),
                     ("channels", "Channels"), ("bit_depth", "Bit depth"),
                     ("bitrate_bps", "Bitrate"), ("pcm_decoded", "PCM decoded"),
                     ("lossy", "Lossy")):
        a("<tr><th>%s</th><td><code>%s</code></td></tr>" % (_esc(label), _esc(c.get(k))))
    a("</table>")

    if g:
        a("<h2>📊 Core features</h2><table>")
        for label, v in (("Integrated loudness", f"{g.loudness_lufs} LUFS"),
                         ("Peak", f"{g.peak_dbfs} dBFS"),
                         ("Dynamic range", f"{g.dynamic_range_db:.1f} dB"),
                         ("Spectral centroid", f"{g.spectral_centroid:.0f} Hz"),
                         ("Usable bandwidth", f"{g.high_cutoff_hz:.0f} Hz"),
                         ("Spectral flatness", f"{g.spectral_flatness:.3f}"),
                         ("Zero-crossing rate", f"{g.zero_crossing_rate:.4f}"),
                         ("Clipping ratio", f"{g.clipping_ratio:.6f}"),
                         ("DC offset", f"{g.dc_offset:+.6f}")):
            a("<tr><th>%s</th><td>%s</td></tr>" % (_esc(label), _esc(v)))
        if g.pitch_hz:
            a("<tr><th>Fundamental</th><td>%.1f Hz (harmonicity %.2f)</td></tr>" % (
                g.pitch_hz, g.harmonicity))
        a("</table>")

    cl = result.classification or {}
    if cl:
        a("<h2>🏷️ Classification</h2><div class='card'>")
        a("<span class='badge'>%s</span> <span class='badge'>confidence %s</span>" % (
            _esc(cl.get("label")), _esc(cl.get("confidence"))))
        probs = cl.get("probabilities", {})
        if probs:
            a("<table><tr><th>Class</th><th>Probability</th></tr>")
            for k, v in sorted(probs.items(), key=lambda x: -x[1]):
                if v:
                    a("<tr><td>%s</td><td>%.1f%%</td></tr>" % (_esc(k), v * 100))
            a("</table>")
        if cl.get("reasons"):
            a("<ul>")
            for r in cl["reasons"]:
                a("<li>%s</li>" % _esc(r))
            a("</ul>")
        a("</div>")

    if sc:
        a("<h2>🧮 Scorecard</h2><table>")
        a("<tr><th>Overall</th><td><b>%s/100</b> <span class='badge b-%s'>%s</span></td></tr>"
          % (_esc(sc.get("overall")), _esc(sc.get("grade")), _esc(sc.get("grade"))))
        a("<tr><th>Technical quality</th><td>%s</td></tr>" % _esc(sc.get("quality", {}).get("score")))
        a("<tr><th>Authenticity</th><td>%s</td></tr>" % _esc(sc.get("authenticity", {}).get("score")))
        a("<tr><th>Usability</th><td>%s</td></tr>" % _esc(sc.get("usability", {}).get("score")))
        t = sc.get("tempo") or {}
        if t.get("bpm"):
            a("<tr><th>Tempo</th><td>%s BPM (confidence %s)</td></tr>" % (
                _esc(t["bpm"]), _esc(t.get("confidence"))))
        a("</table>")
        auth = sc.get("authenticity", {})
        if auth.get("cues"):
            a("<div class='card'><b>%s</b> (p=%s)<ul>" % (
                _esc(auth.get("verdict")), _esc(auth.get("probability"))))
            for cue in auth["cues"]:
                a("<li><code>%s</code> · %s — %s</li>" % (
                    _esc(cue.get("code")), _esc(cue.get("weight")), _esc(cue.get("detail"))))
            a("</ul></div>")
        dm = sc.get("description_match")
        if dm:
            a("<div class='card'><b>Description match: %s</b> (%s)<ul>" % (
                _esc(dm.get("verdict")), _esc(dm.get("score"))))
            for chk in dm.get("checks", []):
                mark = "✅" if chk["matched"] else "❌"
                a("<li>%s <code>%s</code> — expected %s, measured %s</li>" % (
                    mark, _esc(chk["term"]), _esc(chk["expected"]), _esc(chk["actual"])))
            a("</ul></div>")

    if result.findings:
        a("<h2>🔍 Forensic findings</h2><table>")
        a("<tr><th></th><th>Finding</th><th>Confidence</th><th>Detail</th></tr>")
        for f in result.findings:
            a("<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                SEVERITY_ICON.get(f.severity, "•"), _esc(f.severity),
                _esc(f.title), _esc(f.confidence), _esc(f.detail)))
        a("</table>")

    if result.segments:
        a("<h2>⭐ Highlights</h2><ul>")
        for s in result.segments:
            a("<li><code>%.2fs – %.2fs</code> · score %.2f</li>" % (s.start, s.end, s.score))
        a("</ul>")

    if result.notes:
        a("<h2>📝 Listening notes</h2>")
        for n in result.notes:
            tags = " ".join("<span class='badge'>%s</span>" % _esc(t) for t in n.tags)
            a("<div class='note'><b>%.2f–%.2fs</b> %s<br>%s</div>" % (
                n.start, n.end, tags, _esc(n.text)))

    if result.fingerprints:
        fp = result.fingerprints[0]
        a("<h2>🔑 Fingerprint</h2><div class='card'>")
        a("algorithm <code>%s</code> · digest <code>%s</code> · %s landmark hashes" % (
            _esc(fp.get("algorithm")), _esc(fp.get("digest")), _esc(fp.get("hash_count"))))
        a("</div>")

    if result.warnings:
        a("<h2>⚠️ Warnings</h2><ul>")
        for w in result.warnings:
            a("<li>%s</li>" % _esc(w))
        a("</ul>")

    a("<p class='foot'>Generated by AudioVerdict · zero-dependency audio evidence engine</p>")
    a("</div></body></html>")
    return "".join(parts)
