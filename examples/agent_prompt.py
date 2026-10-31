"""Build an LLM prompt from an AudioVerdict report.

This is the integration pattern AudioVerdict is designed for: run the tool,
take the JSON, drop it into a prompt, and let the model reason over measurements
instead of guessing.

    PYTHONPATH=src python3 examples/agent_prompt.py path/to/audio
"""

from __future__ import annotations

import json
import subprocess
import sys

SYSTEM = """\
You are reviewing an audio file for a user. You have been given a measurement
report produced by AudioVerdict, a local audio analysis tool.

Rules you must follow:
1. Never invent numbers. Every loudness, bandwidth or timing figure you mention
   must come from the report. If the report does not say it, say you cannot tell.
2. Findings with severity "high" are blocking issues. Mention them first and
   explain what they mean in plain language.
3. Cite each finding's `evidence` object when you explain a problem, and give the
   time positions so the user knows where to listen.
4. Distinguish clearly between what is measured and what is your inference.
5. If `authenticity.verdict` is "inconclusive", say so — do not upgrade it to a
   conclusion in either direction.
"""

USER_TEMPLATE = """\
The user asked: "{question}"

Here is the AudioVerdict report for {path}:

```json
{report}
```

Answer the user's question using only the evidence above.
"""


def build_prompt(path: str, question: str) -> str:
    """Run the CLI and assemble a prompt the model can act on."""
    proc = subprocess.run(
        [sys.executable, "-m", "audioverdict", "analyze", path, "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    report = proc.stdout.strip()
    # Findings and per-window timelines are what matter; the huge visual payload
    # is stripped from JSON automatically, so the prompt stays reasonably small.
    return USER_TEMPLATE.format(question=question, path=path, report=report)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    question = sys.argv[2] if len(sys.argv) > 2 else "Is this file good enough to ship?"

    print("# ---- system ----")
    print(SYSTEM)
    print()
    print("# ---- user ----")
    print(build_prompt(path, question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
