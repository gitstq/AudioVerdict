"""Batch quality gate: sweep a directory and fail on serious findings.

Useful in CI or in a pre-delivery check — it turns a folder of takes into a
pass/fail table with an exit code.

    PYTHONPATH=src python3 examples/batch_qc.py ./takes
    PYTHONPATH=src python3 examples/batch_qc.py ./takes --fail-on high
"""

from __future__ import annotations

import argparse
import os
import sys

from audioverdict import analyse_file

AUDIO_EXT = {
    ".wav", ".wave", ".aif", ".aiff", ".aifc",
    ".flac", ".mp3", ".ogg", ".oga", ".opus", ".m4a", ".mp4",
}

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}


def collect(root: str) -> list:
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() in AUDIO_EXT:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory")
    ap.add_argument("--fail-on", default="high",
                    choices=["low", "medium", "high"],
                    help="lowest severity that makes the run fail (default high)")
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    args = ap.parse_args()

    files = collect(args.directory)
    if not files:
        print(f"no audio files under {args.directory}")
        return 2

    threshold = SEVERITY_ORDER[args.fail_on]
    failures = 0

    print(f"{'file':48} {'score':>6} {'grade':>5}  {'severity':8} findings")
    print("-" * 88)

    for path in files:
        try:
            result = analyse_file(path, lang=args.lang)
        except Exception as exc:  # never let one bad file kill the sweep
            print(f"{os.path.basename(path)[:48]:48} {'ERROR':>6} {'':>5}  {exc}")
            failures += 1
            continue

        worst = ""
        for f in result.findings:
            if not worst or SEVERITY_ORDER.get(f.severity, 0) > SEVERITY_ORDER.get(worst, 0):
                worst = f.severity

        row = (f"{os.path.basename(path)[:48]:48} "
               f"{result.scorecard.get('overall', 0):6.1f} "
               f"{str(result.scorecard.get('grade', '-')):>5}  "
               f"{worst or 'none':8} {len(result.findings)}")
        print(row)

        for f in result.findings:
            if SEVERITY_ORDER.get(f.severity, 0) >= threshold:
                print(f"    ! [{f.severity}] {f.code}: {f.detail}")
                failures += 1

        for w in result.warnings:
            print(f"    ~ warning: {w}")

    print("-" * 88)
    if failures:
        print(f"FAIL — {failures} issue(s) at or above '{args.fail_on}'")
        return 1
    print(f"PASS — {len(files)} file(s), nothing at or above '{args.fail_on}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
