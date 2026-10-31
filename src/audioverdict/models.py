"""Core data models shared by the decoder, DSP and analysis layers.

The models are deliberately plain Python (no third-party types) so the whole
package stays zero-dependency and importable on any CPython >= 3.8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class AudioData:
    """Decoded audio, plus everything we learned about the container."""

    samples: Optional[List[float]] = None      # mono mix-down, normalised to [-1, 1]
    channels: int = 0
    sample_rate: int = 0
    duration: float = 0.0
    bit_depth: int = 0
    container: str = ""
    codec: str = ""
    bitrate: int = 0                            # bits per second, 0 when unknown
    decoded: bool = False                       # True when PCM samples are available
    lossy: bool = False                         # True when the codec is lossy
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return len(self.samples) if self.samples else 0

    def slice_seconds(self, start: float, end: float) -> List[float]:
        """Return the mono samples between ``start`` and ``end`` seconds."""
        if not self.samples or self.sample_rate <= 0:
            return []
        a = max(0, int(start * self.sample_rate))
        b = min(len(self.samples), int(end * self.sample_rate))
        return self.samples[a:b]


@dataclass
class FeatureSet:
    """Numeric fingerprint of one audio window (or of a whole file)."""

    start: float = 0.0
    end: float = 0.0
    rms: float = 0.0
    peak: float = 0.0
    crest_factor: float = 0.0
    dynamic_range_db: float = 0.0
    clipping_ratio: float = 0.0
    dc_offset: float = 0.0
    zero_crossing_rate: float = 0.0
    silence_ratio: float = 0.0
    spectral_centroid: float = 0.0
    spectral_spread: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_flatness: float = 0.0
    spectral_flux: float = 0.0
    band_energy: List[float] = field(default_factory=list)
    high_cutoff_hz: float = 0.0
    mfcc: List[float] = field(default_factory=list)
    pitch_hz: float = 0.0
    harmonicity: float = 0.0
    loudness_lufs: float = -70.0
    stereo_correlation: float = 0.0
    peak_dbfs: float = -120.0

    def as_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["band_energy"] = [round(x, 6) for x in self.band_energy]
        d["mfcc"] = [round(x, 4) for x in self.mfcc]
        for k, v in list(d.items()):
            if isinstance(v, float):
                d[k] = round(v, 6)
        return d


@dataclass
class Finding:
    """One forensic / quality observation with an evidence grade."""

    code: str
    title: str
    severity: str          # info | low | medium | high
    confidence: float      # 0.0 - 1.0
    detail: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity,
            "confidence": round(self.confidence, 3),
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass
class Note:
    """A human (and LLM) readable listening note for a time span."""

    start: float
    end: float
    text: str
    tags: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "tags": self.tags,
        }


@dataclass
class Segment:
    start: float
    end: float
    label: str
    score: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "label": self.label,
            "score": round(self.score, 4),
        }


@dataclass
class AnalysisResult:
    path: str = ""
    container: Dict[str, Any] = field(default_factory=dict)
    global_features: Optional[FeatureSet] = None
    timeline: List[FeatureSet] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    classification: Dict[str, Any] = field(default_factory=dict)
    scorecard: Dict[str, Any] = field(default_factory=dict)
    fingerprints: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        scorecard = {k: v for k, v in (self.scorecard or {}).items()
                     if not k.startswith("_")}
        return {
            "path": self.path,
            "container": self.container,
            "global_features": self.global_features.as_dict() if self.global_features else None,
            "timeline": [f.as_dict() for f in self.timeline],
            "notes": [n.as_dict() for n in self.notes],
            "segments": [s.as_dict() for s in self.segments],
            "findings": [f.as_dict() for f in self.findings],
            "classification": self.classification,
            "scorecard": scorecard,
            "fingerprints": self.fingerprints,
            "warnings": self.warnings,
        }


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def to_db(value: float, floor: float = -120.0) -> float:
    """Convert a linear amplitude ratio to dBFS."""
    if value <= 0:
        return floor
    import math

    return max(floor, 20.0 * math.log10(value))
