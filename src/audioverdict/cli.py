"""Command line interface for AudioVerdict."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .analysis import analyse_file
from .analysis.notes import describe_file
from .analysis.fingerprint import compare as fp_compare
from .report import FORMATS, render

BANNER = f"""\
🎧 AudioVerdict {__version__} — zero-dependency audio evidence engine
   turn any audio file into evidence an AI agent can read
"""

EXTENSIONS = {".wav", ".wave", ".aiff", ".aif", ".aifc", ".flac",
              ".mp3", ".ogg", ".oga", ".opus", ".m4a", ".mp4"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="audioverdict",
        description="Analyse audio files offline and emit evidence an AI agent can read.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  audioverdict analyze demo.wav --format markdown\n"
               "  audioverdict analyze take3.flac --describe '低沉男声独白'\n"
               "  audioverdict verify interview.m4a --format json\n"
               "  audioverdict compare a.wav b.wav\n"
               "  audioverdict batch ./takes --format json\n",
    )
    p.add_argument("--version", action="version", version=f"AudioVerdict {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--window", type=float, default=1.0,
                        help="analysis window in seconds (default 1.0)")
        sp.add_argument("--hop", type=float, default=0.5,
                        help="hop between windows in seconds (default 0.5)")
        sp.add_argument("--max-windows", type=int, default=400,
                        help="cap on analysed windows (default 400)")
        sp.add_argument("--lang", choices=("en", "zh"), default="en",
                        help="language for notes and summaries (default en)")

    a = sub.add_parser("analyze", aliases=["analyse"], help="full analysis of one file")
    a.add_argument("path")
    a.add_argument("--format", choices=FORMATS, default="text")
    a.add_argument("--describe", default=None,
                   help="free-text description to check the audio against")
    a.add_argument("--out", default=None, help="write the report to a file")
    common(a)

    d = sub.add_parser("describe", help="one-paragraph description of a file")
    d.add_argument("path")
    common(d)

    f = sub.add_parser("fingerprint", help="content fingerprint of a file")
    f.add_argument("path")

    c = sub.add_parser("compare", help="compare two files by fingerprint")
    c.add_argument("a")
    c.add_argument("b")

    v = sub.add_parser("verify", help="forensic findings only")
    v.add_argument("path")
    v.add_argument("--format", choices=("text", "json"), default="text")
    common(v)

    b = sub.add_parser("batch", help="analyse every audio file under a directory")
    b.add_argument("directory")
    b.add_argument("--format", choices=("text", "json"), default="text")
    b.add_argument("--out", default=None)
    common(b)

    s = sub.add_parser("selftest", help="generate a synthetic clip and analyse it")
    s.add_argument("--out", default=None, help="where to write the generated WAV")
    return p


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        directory = os.path.dirname(os.path.abspath(out))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"written: {out}")
    else:
        print(text)


def _collect(directory: str) -> List[str]:
    found: List[str] = []
    for root, _dirs, files in os.walk(directory):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in EXTENSIONS:
                found.append(os.path.join(root, name))
    return found


def _selftest(out: Optional[str]) -> int:
    """Generate a deterministic clip, analyse it and print the key numbers."""
    import math

    from .decode.wav import write_wav

    path = out or "audioverdict-selftest.wav"
    rate = 22050
    samples: List[float] = []
    for i in range(rate * 3):
        t = i / rate
        # A 220 Hz tone that decays, plus a little noise: enough to exercise
        # pitch, loudness and spectral paths.
        env = 0.35 * math.exp(-t)
        tone = math.sin(2 * math.pi * 220 * t) * env
        harm = 0.12 * math.sin(2 * math.pi * 440 * t) * env
        noise = ((i * 1103515245 + 12345) % 1000 / 1000.0 - 0.5) * 0.004
        samples.append(tone + harm + noise)
    write_wav(path, samples, rate)

    result = analyse_file(path)
    print(BANNER)
    print(f"generated : {path}")
    print(f"classified: {result.classification.get('label')} "
          f"(confidence {result.classification.get('confidence')})")
    g = result.global_features
    if g:
        print(f"loudness  : {g.loudness_lufs} LUFS")
        print(f"centroid  : {g.spectral_centroid:.0f} Hz")
        print(f"pitch     : {g.pitch_hz:.1f} Hz (harmonicity {g.harmonicity:.2f})")
    print(f"score     : {result.scorecard.get('overall')}/100 "
          f"grade {result.scorecard.get('grade')}")
    print(f"findings  : {len(result.findings)}")
    print(describe_file(result, lang="en"))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return _selftest(getattr(args, "out", None))

    if args.command in ("analyze", "analyse"):
        if not os.path.exists(args.path):
            print(f"error: no such file: {args.path}", file=sys.stderr)
            return 2
        result = analyse_file(args.path, window_seconds=args.window,
                              hop_seconds=args.hop, max_windows=args.max_windows,
                              lang=args.lang, description=args.describe)
        _emit(render(result, fmt=args.format, lang=args.lang), args.out)
        return 0

    if args.command == "describe":
        result = analyse_file(args.path, lang=args.lang)
        print(describe_file(result, lang=args.lang))
        return 0

    if args.command == "fingerprint":
        result = analyse_file(args.path)
        print(json.dumps(result.fingerprints, ensure_ascii=False, indent=2))
        return 0

    if args.command == "compare":
        ra = analyse_file(args.a)
        rb = analyse_file(args.b)
        verdict = fp_compare(ra.fingerprints, rb.fingerprints)
        print(json.dumps({"a": args.a, "b": args.b, **verdict},
                         ensure_ascii=False, indent=2))
        return 0

    if args.command == "verify":
        result = analyse_file(args.path, window_seconds=args.window,
                              hop_seconds=args.hop, max_windows=args.max_windows,
                              lang=args.lang)
        if args.format == "json":
            _emit(json.dumps([f.as_dict() for f in result.findings],
                             ensure_ascii=False, indent=2), None)
        else:
            if not result.findings:
                print("no findings — nothing suspicious detected")
            for f in result.findings:
                print(f"[{f.severity}] {f.title} (confidence {f.confidence})")
                print(f"    {f.detail}")
        return 0

    if args.command == "batch":
        files = _collect(args.directory)
        if not files:
            print(f"no audio files found under {args.directory}", file=sys.stderr)
            return 1
        rows = []
        for path in files:
            try:
                r = analyse_file(path, window_seconds=args.window,
                                 hop_seconds=args.hop, max_windows=args.max_windows,
                                 lang=args.lang)
                rows.append({
                    "path": path,
                    "format": r.container.get("format"),
                    "duration": r.container.get("duration_seconds"),
                    "label": r.classification.get("label"),
                    "score": r.scorecard.get("overall"),
                    "grade": r.scorecard.get("grade"),
                    "authenticity": r.scorecard.get("authenticity", {}).get("verdict"),
                    "findings": len(r.findings),
                    "digest": (r.fingerprints[0].get("digest") if r.fingerprints else None),
                })
            except Exception as exc:                     # keep the batch alive
                rows.append({"path": path, "error": str(exc)})
        if args.format == "json":
            _emit(json.dumps(rows, ensure_ascii=False, indent=2), args.out)
        else:
            lines = [f"{'file':48s} {'fmt':7s} {'dur':>7s} {'label':10s} {'score':>6s} "
                     f"{'gr':>3s} {'findings':>8s}"]
            for r in rows:
                if "error" in r:
                    lines.append(f"{r['path'][:48]:48s} ERROR {r['error'][:40]}")
                    continue
                lines.append(f"{r['path'][:48]:48s} {str(r['format'])[:7]:7s} "
                             f"{r['duration']:7.2f} {str(r['label'])[:10]:10s} "
                             f"{r['score']:6.1f} {r['grade']:>3s} {r['findings']:8d}")
            _emit("\n".join(lines), args.out)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
