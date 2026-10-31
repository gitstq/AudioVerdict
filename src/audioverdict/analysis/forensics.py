"""Tamper and provenance analysis.

Each check emits an explainable :class:`Finding`: what was measured, why it
matters and how confident the conclusion is. Nothing here claims legal-grade
certainty; the output is decision support for a human or an agent.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from ..dsp import to_db
from ..models import AudioData, FeatureSet, Finding, Segment

# Cutoff frequencies that betray a lower-rate source that was later upsampled.
UPSAMPLE_HINTS = {
    11025: "22.05 kHz",
    11050: "22.05 kHz",
    12000: "24 kHz",
    16000: "32 kHz",
    22050: "44.1 kHz",
    24000: "48 kHz",
}


def _splice_points(timeline: Sequence[FeatureSet], extras: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Windows where level and spectrum jump together.

    A genuine musical accent raises the level but keeps the spectrum roughly
    continuous; a splice changes both at the same instant.
    """
    out: List[Dict[str, Any]] = []
    if len(timeline) < 3:
        return out
    rms_seq = [f.rms for f in timeline]
    flux_seq = [f.spectral_flux for f in timeline]
    cent_seq = [f.spectral_centroid for f in timeline]

    for i in range(1, len(timeline)):
        prev_r, cur_r = rms_seq[i - 1], rms_seq[i]
        if cur_r <= 1e-9 and prev_r <= 1e-9:
            continue
        ratio = (cur_r + 1e-9) / (prev_r + 1e-9)
        jump = ratio >= 2.5 or ratio <= 0.4
        flux_spike = flux_seq[i] > 0 and flux_seq[i] > 3 * (
            sum(flux_seq) / len(flux_seq) + 1e-12)
        cent_shift = 0.0
        if cent_seq[i - 1] > 0 and cent_seq[i] > 0:
            cent_shift = abs(math.log2((cent_seq[i] + 1) / (cent_seq[i - 1] + 1)))
        if (jump and flux_spike) or (jump and cent_shift > 0.7):
            out.append({
                "time": round(timeline[i].start, 3),
                "level_ratio": round(ratio, 3),
                "level_db": round(to_db(cur_r) - to_db(prev_r), 2),
                "centroid_shift_octaves": round(cent_shift, 3),
            })
    return out


def analyse(audio: AudioData, global_features: FeatureSet,
            timeline: Sequence[FeatureSet], extras: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    g = global_features

    # --- splice / cut points -------------------------------------------
    splices = _splice_points(timeline, extras)
    if splices:
        strongest = max(splices, key=lambda s: abs(s["level_db"]))
        findings.append(Finding(
            code="splice_candidates",
            title="Possible edit points (splices)",
            severity="high" if len(splices) >= 3 else "medium",
            confidence=min(0.9, 0.4 + 0.1 * len(splices)),
            detail=(f"{len(splices)} position(s) where level and spectrum jump together; "
                    f"strongest at {strongest['time']}s ({strongest['level_db']:+.1f} dB)"),
            evidence={"count": len(splices), "points": splices[:12]},
        ))

    # --- digital silence -------------------------------------------------
    if timeline:
        dead = [f for f in timeline if f.rms < 1e-6]
        if dead:
            ratio = len(dead) / len(timeline)
            findings.append(Finding(
                code="digital_silence",
                title="Digital (absolute-zero) silence",
                severity="medium" if ratio < 0.5 else "high",
                confidence=min(0.95, 0.5 + ratio),
                detail=(f"{len(dead)} window(s) ({ratio:.0%}) are exactly zero. Real recordings "
                        "always carry a noise floor, so this indicates a generated or "
                        "edited-in mute"),
                evidence={"windows": len(dead), "ratio": round(ratio, 4),
                          "times": [f.start for f in dead[:12]]},
            ))

    # --- clipping ---------------------------------------------------------
    if g.clipping_ratio > 0.0001:
        findings.append(Finding(
            code="clipping",
            title="Clipping / hard limiting",
            severity="high" if g.clipping_ratio > 0.01 else "medium",
            confidence=0.95,
            detail=(f"{g.clipping_ratio:.4%} of samples sit at full scale. "
                    f"Peak {g.peak_dbfs:.1f} dBFS with a crest factor of {g.crest_factor:.2f}"),
            evidence={"clipping_ratio": round(g.clipping_ratio, 6),
                      "peak_dbfs": round(g.peak_dbfs, 2),
                      "crest_factor": round(g.crest_factor, 3)},
        ))
    elif (g.crest_factor and g.crest_factor < 3.0 and g.rms > 0.01
          # A pure sine wave has a crest factor of sqrt(2) = 1.414 by
          # definition, so low crest is only meaningful for dense material.
          and g.harmonicity < 0.8):
        findings.append(Finding(
            code="over_compressed",
            title="Heavy dynamic compression",
            severity="low",
            confidence=0.7,
            detail=(f"Crest factor {g.crest_factor:.2f} (below 3.0) indicates aggressive "
                    "limiting or loudness normalisation"),
            evidence={"crest_factor": round(g.crest_factor, 3),
                      "dynamic_range_db": round(g.dynamic_range_db, 2)},
        ))

    # --- upsampling / transcode -------------------------------------------
    nyq = audio.sample_rate / 2 if audio.sample_rate else 0
    cutoff = g.high_cutoff_hz
    cliff = extras.get("band_cliff") or {}
    # A gentle high-frequency roll-off is normal for real material; only a
    # steep cliff is evidence of resampling or lossy encoding.
    steep = bool(cliff.get("detected")) and float(cliff.get("slope_db") or 0) < -20.0
    if nyq > 4000 and cutoff > 0:
        # Which known source rate would produce this cutoff?
        match = None
        for hint, label in UPSAMPLE_HINTS.items():
            if abs(cutoff - hint) / hint < 0.05:
                match = (hint, label)
                break
        if match and cutoff < nyq * 0.75 and steep:
            findings.append(Finding(
                code="upsampled_source",
                title="Upsampled from a lower sample rate",
                severity="medium",
                confidence=0.75,
                detail=(f"Energy stops around {cutoff:.0f} Hz while the file claims "
                        f"{audio.sample_rate} Hz; consistent with a {match[1]} source that was "
                        "resampled upward"),
                evidence={"high_cutoff_hz": round(cutoff, 1),
                          "declared_sample_rate": audio.sample_rate,
                          "implied_source": match[1],
                          "slope_db": cliff.get("slope_db")},
            ))
        elif cutoff >= 2000 and cutoff < nyq * 0.5 and not audio.lossy and steep:
            # Below 2 kHz the "missing bandwidth" is simply the content itself
            # (bass-heavy material), not an artefact.
            findings.append(Finding(
                code="bandwidth_shortfall",
                title="Bandwidth far below the declared sample rate",
                severity="medium",
                confidence=0.65,
                detail=(f"A lossless {audio.sample_rate} Hz file should reach ~{nyq:.0f} Hz, but "
                        f"content stops at {cutoff:.0f} Hz"),
                evidence={"high_cutoff_hz": round(cutoff, 1), "nyquist_hz": round(nyq, 1)},
            ))

    # --- lossy artefact inside a lossless container ------------------------
    if not audio.lossy and audio.decoded:
        cliff = extras.get("band_cliff") or {}
        # Real codec cliffs sit well above 4 kHz; a low cutoff just means the
        # material itself has no high-frequency content.
        if cliff.get("detected") and (cliff.get("cutoff_hz") or 0) >= 4000:
            findings.append(Finding(
                code="transcode_into_lossless",
                title="Lossy codec artefacts inside a lossless container",
                severity="high",
                confidence=0.85,
                detail=(f"A {abs(cliff.get('slope_db', 0)):.0f} dB cliff at {cliff.get('cutoff_hz'):.0f} Hz "
                        f"in a {audio.container} file means the audio was lossy-encoded "
                        "before being saved as lossless"),
                evidence={"cutoff_hz": cliff.get("cutoff_hz"),
                          "slope_db": cliff.get("slope_db")},
            ))

    # --- DC offset ----------------------------------------------------------
    if abs(g.dc_offset) > 0.001:
        findings.append(Finding(
            code="dc_offset",
            title="DC offset present",
            severity="low" if abs(g.dc_offset) < 0.01 else "medium",
            confidence=0.9,
            detail=f"Mean sample value is {g.dc_offset:+.5f} instead of ~0 (capture chain defect)",
            evidence={"dc_offset": round(g.dc_offset, 6)},
        ))

    # --- inconsistent noise floor (multi-source assembly) -------------------
    if len(timeline) >= 8:
        quiet = sorted(f.rms for f in timeline if f.rms > 1e-7)
        if len(quiet) >= 8:
            floor_low = quiet[len(quiet) // 10]
            floor_high = quiet[-max(1, len(quiet) // 10)]
            if floor_low > 0 and floor_high / floor_low > 20:
                findings.append(Finding(
                    code="noise_floor_shift",
                    title="Noise floor changes across the file",
                    severity="medium",
                    confidence=0.6,
                    detail=(f"Quietest passages sit {to_db(floor_high) - to_db(floor_low):.0f} dB below the "
                            "loudest quiet passages - typical of material assembled from "
                            "several sources"),
                    evidence={"floor_low": round(floor_low, 8),
                              "floor_high": round(floor_high, 8)},
                ))

    # --- container / stream consistency -------------------------------------
    for w in audio.warnings:
        # Some structural warnings already have a dedicated, better-named
        # finding below. Reporting them twice just adds noise.
        if "faststart" in w.lower():
            continue
        # Informational notes about how the file was read are not evidence of
        # tampering and must not drag the authenticity score down.
        informational = "optional ffmpeg" in w.lower()
        findings.append(Finding(
            code="decode_note" if informational else "container_anomaly",
            title="Decoding note" if informational else "Container level anomaly",
            severity="info" if informational else "medium",
            confidence=0.8,
            detail=w,
            evidence={"container": audio.container},
        ))

    meta = audio.metadata or {}
    if meta.get("vbr_header") and meta.get("xing_frame_count_matches_scan") is False:
        findings.append(Finding(
            code="xing_mismatch",
            title="VBR header disagrees with the frame chain",
            severity="medium",
            confidence=0.8,
            detail=("The Xing/Info header declares a different frame count than the actual "
                    "stream - a sign the file was re-tagged or re-muxed"),
            evidence={"declared": meta.get("frame_count"), "scanned": meta.get("frame_count")},
        ))
    if meta.get("md5_of_pcm") == "0" * 32:
        findings.append(Finding(
            code="unknown_source_md5",
            title="FLAC STREAMINFO MD5 is zeroed",
            severity="low",
            confidence=0.9,
            detail="The encoder did not know the original audio hash, so provenance is weaker",
            evidence={},
        ))
    if meta.get("faststart") is False:
        findings.append(Finding(
            code="no_faststart",
            title="MP4 moov atom placed after mdat",
            severity="info",
            confidence=0.9,
            detail="Not streamable; often produced by a re-mux rather than the original encoder",
            evidence={},
        ))

    return findings


def highlight_segments(timeline: Sequence[FeatureSet], count: int = 3) -> List[Segment]:
    """Pick the most informative moments of a recording.

    Score = loudness x spectral novelty, which reliably lands on hooks,
    transients and other "worth listening to" moments.
    """
    if not timeline:
        return []
    flux_mean = sum(f.spectral_flux for f in timeline) / len(timeline) + 1e-12
    scored: List[Segment] = []
    for f in timeline:
        novelty = f.spectral_flux / flux_mean
        loudness = max(0.0, (f.loudness_lufs + 60.0) / 60.0)
        score = novelty * (0.4 + 0.6 * loudness)
        scored.append(Segment(start=f.start, end=f.end, label="highlight", score=score))
    scored.sort(key=lambda s: s.score, reverse=True)

    picked: List[Segment] = []
    for s in scored:
        if all(abs(s.start - p.start) > 1.0 for p in picked):
            picked.append(s)
        if len(picked) >= count:
            break
    return picked
