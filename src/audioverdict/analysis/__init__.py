"""High-level analysis pipeline."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..decode import container_summary, read_audio
from ..models import AnalysisResult, AudioData
from . import classify as classify_mod
from . import fingerprint as fp_mod
from . import forensics as forensics_mod
from . import match as match_mod
from . import scorecard as scorecard_mod
from .features import extract

__all__ = ["analyse", "analyse_file"]


def analyse(audio: AudioData, window_seconds: float = 1.0, hop_seconds: float = 0.5,
            max_windows: int = 400, lang: str = "en",
            description: Optional[str] = None) -> AnalysisResult:
    result = AnalysisResult(path=str(audio.metadata.get("path", "")))
    result.container = container_summary(audio)
    result.warnings = list(audio.warnings)

    g, timeline, extras = extract(audio, window_seconds=window_seconds,
                                  hop_seconds=hop_seconds, max_windows=max_windows)
    result.global_features = g
    result.timeline = timeline

    classification: Dict[str, Any] = {}
    synthetic: Dict[str, Any] = {}
    if extras.get("analysable"):
        classification = classify_mod.classify(g, timeline, audio, extras)
        synthetic = classify_mod.synthetic_likelihood(audio, g, timeline, extras)
    result.classification = classification

    result.findings = forensics_mod.analyse(audio, g, timeline, extras)
    result.segments = forensics_mod.highlight_segments(timeline)
    result.fingerprints = fp_mod.fingerprints(audio)
    result.scorecard = scorecard_mod.build(audio, g, timeline, result.findings,
                                           classification, synthetic, extras)
    # Visual payload stays out of the JSON export (it is huge); the HTML and
    # Markdown renderers read it from here.
    result.scorecard["_visuals"] = {
        "envelope": extras.get("envelope") or [],
        "average_spectrum": extras.get("average_spectrum") or [],
    }
    scorecard_mod.apply_to(result)

    from .notes import build_notes
    result.notes = build_notes(timeline, lang=lang)

    if description:
        result.scorecard["description_match"] = match_mod.match(result, description)

    return result


def analyse_file(path: str, **kwargs: Any) -> AnalysisResult:
    audio = read_audio(path)
    return analyse(audio, **kwargs)
