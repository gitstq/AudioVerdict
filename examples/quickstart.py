"""AudioVerdict quick start — the smallest useful library example.

Run it from the repository root:

    PYTHONPATH=src python3 examples/quickstart.py [path/to/audio]

With no argument it synthesises a clip first, so it always works.
"""

from __future__ import annotations

import math
import os
import struct
import sys
import wave

from audioverdict import analyse_file
from audioverdict.analysis.notes import describe_file


def make_demo_clip(path: str, seconds: float = 3.0, rate: int = 22050) -> str:
    """Write a short 220 Hz tone with a fade, so we have something to analyse."""
    frames = []
    total = int(seconds * rate)
    for i in range(total):
        t = i / rate
        # 20 ms fades: long enough to avoid a click, short enough not to look
        # like a level jump to the splice detector.
        env = min(1.0, t * 50.0, (seconds - t) * 50.0)
        # Gentle tremolo so the clip has real dynamics instead of a flat block.
        tremolo = 1.0 + 0.18 * math.sin(2 * math.pi * 1.3 * t)
        value = 0.18 * env * tremolo * (math.sin(2 * math.pi * 220 * t)
                                        + 0.25 * math.sin(2 * math.pi * 440 * t))
        frames.append(struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(frames))
    return path


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else make_demo_clip("demo.wav")

    result = analyse_file(path)

    print("file        :", path)
    print("container   :", result.container.get("format"),
          result.container.get("codec"),
          f'{result.container.get("sample_rate")} Hz',
          f'{result.container.get("channels")} ch')
    print("duration    :", round(result.container.get("duration_seconds") or 0, 2), "s")
    print()

    g = result.global_features
    print("loudness    :", round(g.loudness_lufs, 2), "LUFS")
    print("peak        :", round(g.peak_dbfs, 2), "dBFS")
    print("crest       :", round(g.crest_factor, 2))
    print("dynamic rng :", round(g.dynamic_range_db, 1), "dB")
    print("centroid    :", round(g.spectral_centroid), "Hz")
    print("bandwidth   :", round(g.high_cutoff_hz or 0), "Hz")
    print("flatness    :", round(g.spectral_flatness, 4))
    print("pitch       :", round(g.pitch_hz or 0, 1), "Hz",
          f"(harmonicity {g.harmonicity:.2f})")
    print("tempo       :", round(result.scorecard.get("tempo", {}).get("bpm") or 0, 1), "BPM")
    print()

    c = result.classification
    print("classified  :", c.get("label"),
          f'(confidence {c.get("confidence", 0):.2f})')
    auth = result.scorecard.get("authenticity", {})
    print("authenticity:", auth.get("verdict"),
          f'(synthetic p={auth.get("probability")})')
    print("score       :", round(result.scorecard.get("overall", 0), 1),
          "grade", result.scorecard.get("grade"))
    print()

    print("findings    :", len(result.findings))
    for f in result.findings:
        print(f"  [{f.severity}] {f.code} (confidence {f.confidence:.2f})")
        print(f"      {f.detail}")
        if f.evidence:
            print(f"      evidence: {f.evidence}")
    print()

    print("summary     :", describe_file(result, lang="en"))

    if len(sys.argv) == 1 and os.path.exists("demo.wav"):
        os.remove("demo.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
