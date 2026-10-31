"""AudioVerdict — zero-dependency, offline-first audio evidence engine.

It turns any audio file into evidence an AI agent can read: measured features,
natural-language listening notes, tamper findings and a scorecard, all produced
locally with nothing but the Python standard library.
"""

from __future__ import annotations

from .analysis import analyse, analyse_file
from .decode import SUPPORTED, detect_format, read_audio
from .models import AnalysisResult, AudioData, FeatureSet, Finding, Note

__version__ = "1.0.0"
__all__ = [
    "__version__",
    "analyse", "analyse_file",
    "read_audio", "detect_format", "SUPPORTED",
    "AnalysisResult", "AudioData", "FeatureSet", "Finding", "Note",
]
