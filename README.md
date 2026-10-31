<div align="center">

# 🎧 AudioVerdict

**Turn any audio file into evidence an AI agent can read.**

Zero dependencies · Fully offline · Pure Python standard library

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#-quick-start)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-53%20passing-brightgreen.svg)](#-contributing)

🌐 **Language / 语言**: **English** · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

</div>

---

## 🎉 1. Project Introduction

An AI coding agent can read your source, your logs and your stack traces — but give it an audio file and it is blind. It sees `interview_take3.m4a`, 4.2 MB, and nothing else. It cannot tell whether the file is clipped, whether someone spliced two takes together, whether it really was recorded in a quiet room as the brief claims, or whether that "48 kHz lossless master" is actually a 128 kbps MP3 someone re-wrapped.

**AudioVerdict closes that gap.** It reads an audio file locally and emits a structured, explainable evidence packet: measured acoustic features, plain-English listening notes, tamper findings with severity and confidence, and a scorecard — all as JSON, Markdown, plain text or a self-contained HTML page.

> **The key idea:** AudioVerdict does not *judge* audio for a human listener. It *describes* audio in the vocabulary an AI agent can reason with — numbers, severities, time ranges and evidence strings — so the agent can make the call itself.

Everything runs on the CPU, in-process, with **no third-party packages at all**. No NumPy, no SciPy, no librosa, no model download, no network call, no API key. `pip install` it and it works on a locked-down machine with no internet access.

### Where it came from

The open-source project [`earshot`](https://github.com/Leonxlnx/earshot) (3.3k+ stars) popularised the framing *"ears for coding agents"*. AudioVerdict takes that same direction but builds a completely different instrument:

| | `earshot` and friends | **AudioVerdict** |
|---|---|---|
| Output shape | Conversation-oriented summaries for a coding session | A typed evidence object: features + findings + scorecard + timeline |
| Focus | *Helping an agent hear what is happening now* | *Helping an agent audit what is inside the file* |
| Forensics | Not a focus | First-class: splice points, transcode chains, upsampling, container anomalies |
| Stack | External audio libraries | Zero dependencies — the DSP is written from scratch |
| Determinism | Varies | Same file → same fingerprint, every run, every machine |

AudioVerdict is an independent, self-developed implementation. No code was copied from any existing project; only the general product direction was observed.

---

## ✨ 2. Core Features

### 🔬 Full signal analysis — written from scratch
- **Radix-2 Cooley–Tukey FFT**, real-input FFT, Hann / Hamming / Blackman windows, DCT-II and arbitrary resampling — all hand-written, no NumPy.
- **Loudness**: BS.1770-4 K-weighting (high-shelf + high-pass biquads), gated integrated LUFS, loudness range.
- **True peak (dBTP)** via 4× oversampled interpolation, the metric that actually predicts inter-sample clipping.
- **Spectral descriptors**: centroid, spread, rolloff, flatness, flux, 9-band energy distribution, spectral contrast, high-frequency cutoff with cliff detection.
- **MFCC**: 26 Mel filters → 13 cepstra, Mel scale conversion included.
- **Pitch**: YIN algorithm (cumulative mean normalised difference + parabolic interpolation) with harmonicity and voiced-ratio estimation.
- **Tempo**: autocorrelation-based BPM estimation with beat-grid generation.

### 🕵️ Forensic findings with evidence
Findings carry `code`, `severity`, `confidence`, an optional time range and a human-readable `detail` string — so an agent can filter, sort and act on them:

| Code | What it catches |
|---|---|
| `splice_candidates` | Level or spectrum discontinuities that suggest two takes joined together |
| `digital_silence` | Perfect-zero runs — the signature of an edit, not a room |
| `clipping` | Samples pinned at full scale |
| `over_compressed` | Crest factor too low for the content type |
| `upsampled_source` | A steep high-frequency cliff far below Nyquist — a low-rate source re-saved at a high rate |
| `bandwidth_shortfall` | Steep cutoff inconsistent with the declared sample rate |
| `transcode_into_lossless` | Lossy codec artefacts inside a "lossless" container (e.g. MP3 → WAV) |
| `noise_floor_shift` | Noise floor moves between sections — different room, different take |
| `container_anomaly` | Broken frame chains, wrong Xing/VBRI headers, non-monotonic FLAC frame numbers, out-of-order Ogg pages |
| `xing_mismatch` | Declared MP3 frame count disagrees with the actual chain |
| `unknown_source_md5` | FLAC stores an MD5 of the original PCM — mismatch means the audio was altered after encoding |
| `dc_offset` | DC bias, the classic cheap-microphone artefact |
| `no_faststart` | MP4 `moov` atom after `mdat` — breaks progressive streaming |

### 📦 Container forensics — six formats, no decoder required
AudioVerdict parses the container directly, so a **100 MB file is inspected by reading a few kilobytes**:

| Format | What is verified |
|---|---|
| **WAV** (RIFF) | PCM 8/16/24/32-bit, float32/64, µ-law/A-law, `LIST`/`INFO`, broadcast `bext` |
| **AIFF / AIFF-C** | 80-bit extended float sample rate, `COMM`/`SSND` layout |
| **FLAC** | `STREAMINFO`, original-PCM MD5, Vorbis comments, full frame-chain walk |
| **MP3** | Frame-chain walk, Xing / Info / VBRI headers, VBR and padding statistics, ID3v1/v2 |
| **Ogg** | Vorbis / Opus / Ogg-FLAC identification, granule positions, serial numbers, page-sequence continuity |
| **MP4 / M4A** | Full atom-tree walk, `mvhd`/`mdhd`/`stsd`/`mp4a`, iTunes `ilst` tags, faststart check |

### 🔑 Content fingerprinting
A landmark-hash fingerprint (`AVD-landmark-v1`): log-band spectral peaks are paired into landmarks and digested with FNV-1a. Two files can be compared for near-duplicate content **without** decoding either one fully — ideal for "is this the same take that I already reviewed?".

### 🎼 Content classification & description matching
- Classifies content as `speech` / `music` / `ambience` / `tone` / `noise` / `silence` with a probability distribution and the reasons behind the decision.
- Estimates a **synthetic-likelihood** score from six independent cues (digital silence, over-smooth spectrum, missing air band, unnaturally stable pitch, missing noise floor, static level).
- **`--describe`** checks the file against a free-text brief — "低沉男声独白", "warm female voiceover, quiet room" — and reports which claims the measurements contradict. Lexicon covers Chinese and English.

### 📝 Natural-language output
Hand-built listening notes (EN / 中文) covering loudness, dynamics, timbre, bandwidth, pitch, rhythm, noise and artefacts. Plus rendered **waveform, log-frequency spectrum and feature-timeline SVGs** — drawn by hand, no plotting library, embedded inline in the HTML report.

### 🖥️ Four report formats
`json` (agent-friendly) · `markdown` (PR/review friendly) · `text` (terminal) · `html` (self-contained, no external assets).

---

## 🚀 3. Quick Start

### Requirements

| Item | Requirement |
|---|---|
| Python | **3.8 or newer** (tested on 3.8 – 3.13) |
| Runtime dependencies | **None** |
| Operating system | Windows, macOS, Linux — pure Python, no native extension |
| Optional | `ffmpeg` on `PATH` — *only* needed to decode PCM from compressed formats (MP3/OGG/M4A). Without it you still get full container forensics and loudness-free structural analysis. |

### Install

```bash
# From a clone
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
pip install -e .

# Verify
audioverdict --version
```

Or without installing anything:

```bash
PYTHONPATH=src python3 -m audioverdict --help
```

> `pip install -e .` needs no network beyond fetching `setuptools`; there are **no third-party runtime packages** to download.

### First run in 30 seconds

```bash
# Generate a synthetic clip and analyse it end to end
audioverdict selftest

# Analyse a real file
audioverdict analyze interview.m4a

# Ask it a question in Markdown, and check the file against a brief
audioverdict analyze take3.flac --format markdown \
  --describe '低沉男声独白，安静室内录制' --out report.md

# Forensic findings only, as JSON
audioverdict verify evidence.wav --format json

# Are these two files the same content?
audioverdict compare a.wav b.wav

# Sweep a whole directory
audioverdict batch ./takes --format json --out takes.json
```

### As a library

```python
from audioverdict import analyse_file
from audioverdict.report import render

result = analyse_file("interview.m4a")

print(result.classification["label"])             # 'speech'
print(result.scorecard["overall"])                # 82.4
print(result.global_features.loudness_lufs)       # -18.7

for f in result.findings:
    if f.severity == "high":
        print(f.code, f.confidence, f.detail, f.evidence)

print(render(result, fmt="text", lang="en"))      # one-screen brief
print(result.as_dict())                           # the JSON payload as a dict
```

One call returns an `AnalysisResult` holding `container`, `global_features`, `timeline`, `notes`, `segments`, `findings`, `classification`, `scorecard`, `fingerprints` and `warnings`. `result.as_dict()` gives you the JSON shape directly; `render(result, fmt=...)` turns it into `json`, `text`, `markdown` or `html`.

---

## 📖 4. Detailed Usage Guide

### 4.1 CLI reference

```
audioverdict <command> [options] <path>
```

| Command | Purpose |
|---|---|
| `analyze` (alias `analyse`) | Full analysis of one file |
| `describe` | One-paragraph natural-language description |
| `fingerprint` | Content fingerprint only (fast, no full decode) |
| `compare` | Compare two files by fingerprint |
| `verify` | Forensic findings only |
| `batch` | Analyse every audio file under a directory |
| `selftest` | Generate a synthetic clip and analyse it — proves the install works |

Common options for `analyze` / `verify` / `describe`:

| Option | Default | Meaning |
|---|---|---|
| `--format` | `text` | `json`, `text`, `markdown`, `html` |
| `--describe TEXT` | – | Free-text brief to check the audio against (EN or 中文) |
| `--out PATH` | stdout | Write the report to a file |
| `--window SEC` | `1.0` | Analysis window length |
| `--hop SEC` | `0.5` | Hop between windows |
| `--max-windows N` | `400` | Cap on analysed windows (bounds runtime on long files) |
| `--lang` | `en` | `en` or `zh` — language of notes and summary |

### 4.2 Choosing output format

```bash
# For an LLM / agent pipeline — stable, typed, complete
audioverdict analyze take.wav --format json --out take.json

# For a code review, a PR comment or a ticket
audioverdict analyze take.wav --format markdown --out take.md

# For a human to open in a browser — self-contained, inline SVG, offline
audioverdict analyze take.wav --format html --out take.html

# For a terminal / CI log
audioverdict analyze take.wav
```

### 4.3 Reading the JSON

```jsonc
{
  "path": "take.wav",
  "container": { "format": "WAV", "codec": "PCM", "sample_rate": 44100,
                 "channels": 1, "lossy": false, "pcm_decoded": true },
  "global_features": { "loudness_lufs": -18.7, "peak_dbfs": -1.2,
                       "spectral_centroid": 1840.2, "clipping_ratio": 0.0 },
  "timeline": [ /* per-window features with start/end */ ],
  "notes":    [ /* human-readable listening notes */ ],
  "segments": [ /* highlighted regions worth replaying */ ],
  "findings": [
    { "code": "clipping", "severity": "high", "confidence": 0.93,
      "title": "Clipping detected",
      "detail": "2.68% of samples sit at full scale. Peak -0.1 dBFS …",
      "evidence": { "clipping_ratio": 0.0268, "crest_factor": 1.93,
                    "windows": [12.0, 12.5, 13.0, 13.5, 14.0, 14.5] } }
  ],
  "classification": { "label": "speech", "confidence": 0.81,
                      "probabilities": { "speech": 0.81, "music": 0.12 },
                      "reasons": ["…"], "voiced_ratio": 0.74 },
  "scorecard": {
    "overall": 82.4, "grade": "B",
    "quality":       { "score": 71.0, "notes": [] },
    "authenticity":  { "score": 90.5, "probability": 0.08,
                       "verdict": "likely recorded", "cues": [] },
    "usability":     { "score": 88.0, "decoded": true, "duration": 62.5 },
    "tempo":         { "bpm": 96.0, "confidence": 0.62, "beats": [0.02, …] },
    "content":       { "label": "speech", "confidence": 0.81, "…": "…" },
    "headline": "B (82.4/100) - speech, likely recorded"
  },
  "fingerprints": [ { "algo": "AVD-landmark-v1", "value": "…" } ],
  "warnings": [],
  "summary": "Integrated loudness -18.7 LUFS …"
}
```

Severity levels are `info` < `low` < `medium` < `high`. Filter on `severity` first, then on `confidence`. Time positions live inside each finding's `evidence` object (for example `points` for splices, `times` for digital silence, `windows` for clipping) rather than at the top level.

### 4.4 Library API

```python
from audioverdict import analyse_file, read_audio, detect_format, SUPPORTED

# --- Cheap structural pass: no full decode ---
fmt = detect_format("huge_concert.flac")          # 'flac'
audio = read_audio("huge_concert.flac", max_bytes=2_000_000)
print(audio.sample_rate, audio.channels, audio.duration_seconds)

# --- Full analysis ---
r = analyse_file("huge_concert.flac", window=2.0, hop=1.0, lang="zh")

# --- Fingerprints / near-duplicate detection ---
from audioverdict.analysis.fingerprint import fingerprints, compare
a = fingerprints("take_a.wav")
b = fingerprints("take_b.wav")
print(compare(a, b))   # {"similarity": 0.87, ...}

# --- Render any result to a string ---
from audioverdict.report import render
md = render(r, fmt="markdown", lang="en")
```

### 4.5 Feeding it to an agent

AudioVerdict is designed to be dropped straight into a prompt. The pattern that works best:

```python
import json, subprocess

report = subprocess.run(
    ["audioverdict", "analyze", path, "--format", "json"],
    capture_output=True, text=True, check=True).stdout

prompt = f"""
Here is a measurement report for the audio file the user just handed us.
Treat every finding with severity "high" as a blocking issue and mention those
first. Use `global_features` numbers when you talk about loudness or bandwidth,
never guess. Cite each finding's `evidence` object when you explain a problem.

{report}

Answer the user's question about this audio.
"""
```

Because the report is deterministic, the same file always produces the same evidence — which makes agent behaviour reproducible and testable.

### 4.6 Supported formats at a glance

| Container | Extensions | PCM decode without ffmpeg | Container forensics |
|---|---|---|---|
| WAV / RIFF | `.wav`, `.wave` | ✅ | ✅ |
| AIFF / AIFF-C | `.aif`, `.aiff`, `.aifc` | ✅ | ✅ |
| FLAC | `.flac` | ❌ (needs ffmpeg) | ✅ |
| MP3 | `.mp3` | ❌ (needs ffmpeg) | ✅ |
| Ogg | `.ogg`, `.oga`, `.opus` | ❌ (needs ffmpeg) | ✅ |
| MP4 / M4A | `.m4a`, `.mp4` | ❌ (needs ffmpeg) | ✅ |

When PCM is unavailable, AudioVerdict silently falls back to a **container-only** report: format, codec, duration, bitrate, structural anomalies and integrity checks still come through, and a `warnings` entry explains what was skipped. It never crashes on a format it cannot decode.

### 4.7 Performance notes

- Analysis resamples to **44.1 kHz** internally. A 128 kbps MP3 cuts off near 16 kHz, and that cliff is evidence — it must not be resampled away first.
- `--max-windows` (default 400) caps work on long recordings: roughly the first 200 s at default window/hop. Raise it for full-length interviews, lower it for fast CI checks.
- Container parsing is lazy and bounded: `read_audio(..., max_bytes=...)` reads only the head of the file.
- Pure-Python FFT on a 2048-point window is fast enough for interactive use; for hour-long files prefer `verify` (findings only) or raise `--hop`.

---

## 💡 5. Design Philosophy & Roadmap

### 5.1 Decisions worth explaining

**Why zero dependencies?**
An audio tool that needs a 200 MB scientific stack cannot run inside a CI container, a locked-down corporate laptop, or an agent sandbox. Every algorithm here — FFT, K-weighting, YIN, Mel filters, fingerprinting — is implemented directly. The cost is a few thousand lines of DSP; the benefit is that `pip install` never fails and the output is byte-identical everywhere.

**Why evidence instead of opinion?**
"Sounds muddy" is useless to an agent. `spectral_centroid 1180 Hz, high-frequency cutoff 6.2 kHz, findings: bandwidth_shortfall (high)` is actionable. AudioVerdict always reports the measurement, the confidence and the reasoning, and lets the caller decide.

**Why parse containers instead of decoding them?**
Forensics mostly lives in the container. A FLAC stores the MD5 of the original PCM — if it does not match the decoded audio, the file was altered. An MP3 declares its frame count in a Xing header — if the chain disagrees, the stream was cut or stitched. None of that requires decoding gigabytes of samples.

**Why an internal 44.1 kHz analysis rate?**
Because transcode detection depends on seeing the codec's high-frequency cliff, and that cliff disappears if you downsample first. This one change is the difference between "cannot tell" and "this 48 kHz WAV is really a 128 kbps MP3".

**Why hand-written SVG?**
So the HTML report is a single file with zero external requests — openable offline, emailable, archivable, and safe to render in a sandboxed preview.

### 5.2 Roadmap

| Version | Theme | Planned |
|---|---|---|
| **v1.1** | Deeper forensics | ENF (electrical network frequency) analysis, codec-family identification from artefact fingerprints, resampler detection |
| **v1.2** | More formats | Opus in raw OBS frames, WavPack, Monkey's Audio, ADTS AAC, Matroska audio |
| **v1.3** | Speed | Optional NumPy fast path that activates only if NumPy is present, with identical numerical output; multi-process batch mode |
| **v1.4** | Agent ergonomics | An MCP server so agents can call `analyse_audio` as a tool; a `.wav`-diff mode for before/after mastering |
| **v2.0** | Diarisation-lite | Speaker-turn segmentation and per-speaker loudness, still fully offline |
| **Later** | Packaging | Single-file executable builds for Windows / macOS / Linux |

Ideas and pull requests are welcome — see [🤝 Contributing](#-7-contributing).

---

## 📦 6. Packaging & Deployment

AudioVerdict is a **Python library + command-line tool**. It is not a desktop application, so there is no installer to download and no platform binary to publish — you install it from source in the environment where it runs.

### 6.1 Install into a project

```bash
pip install -e .            # editable, for development
pip install .               # regular install
```

Both provide two console scripts: `audioverdict` and the short alias `avd`.

### 6.2 Isolated environments

```bash
# venv (recommended)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# or uv
uv venv && uv pip install -e .

# or conda
conda create -n avd python=3.11 && conda activate avd && pip install -e .
```

### 6.3 Build a distributable wheel / sdist

```bash
pip install --upgrade build
python -m build            # -> dist/audioverdict-1.0.0-py3-none-any.whl
```

The wheel is `py3-none-any`: pure Python, no ABI tag, works on every platform and every interpreter ≥ 3.8. Install it anywhere with:

```bash
pip install dist/audioverdict-1.0.0-py3-none-any.whl
```

### 6.4 Docker / CI

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
# Optional, only if you need to decode MP3/OGG/FLAC/M4A to PCM:
# RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["audioverdict"]
```

```bash
docker build -t audioverdict .
docker run --rm -v "$PWD:/data" audioverdict analyze /data/take.wav --format json
```

### 6.5 Ship it inside your own tool

Because there are no runtime dependencies, AudioVerdict can be vendored: copy the `src/audioverdict/` package directory into your project and import it directly. No `requirements.txt` change, no dependency-conflict risk.

```python
# your_package/audio.py
from audioverdict import analyse_file
```

### 6.6 Optional: standalone executable

Not published as a release artefact (this is a library/CLI project, not a desktop app), but you can build one yourself if you need a no-Python machine to run it:

```bash
pip install pyinstaller
pyinstaller --onefile --name audioverdict src/audioverdict/__main__.py
# -> dist/audioverdict
```

### 6.7 Environment variable

None are required. AudioVerdict reads no configuration, writes nothing outside the paths you pass, and makes no network requests.

---

## 🤝 7. Contributing

Contributions are genuinely welcome, especially new container formats and new forensic checks.

### 7.1 Get set up

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # pytest only
```

### 7.2 Run the tests

```bash
pytest                      # 53 tests
pytest -q                   # quiet
pytest tests/test_dsp.py -v # one module
```

All 53 tests pass on a clean checkout. The suite generates its own synthetic signals (tones, noise, silence, splices, clipped audio), so **you do not need any sample audio files** to run it.

### 7.3 Before you open a pull request

```bash
pytest                                  # must be green
python -m audioverdict selftest         # must complete cleanly
```

### 7.4 Commit conventions

This project follows the [Angular / Conventional Commits](https://www.conventionalcommits.org/) style:

| Prefix | Use for |
|---|---|
| `feat:` | A new capability |
| `fix:` | A bug fix |
| `docs:` | Documentation only |
| `refactor:` | Restructuring with no behaviour change |
| `test:` | Tests only |
| `chore:` | Tooling, packaging, CI |

Examples: `feat: add WavPack container parser`, `fix: correct stsd sample-rate offset in MP4 reader`, `docs: add Chinese README`.

### 7.5 Where to help

- **New formats** — WavPack, APE, ADTS AAC, Matroska audio. Implement a `read_<fmt>()` in `src/audioverdict/decode/`, register it in `decode/__init__.py`, add tests.
- **New forensic checks** — add to `src/audioverdict/analysis/forensics.py`. Every finding needs `code`, `severity`, `confidence` and a `detail` string that cites the numbers it used.
- **False positives** — the most valuable bug report there is. If AudioVerdict flags a clean file, open an issue with the file (or a synthetic reproduction) and the expected verdict.
- **Translations** — notes and summaries live in `src/audioverdict/analysis/notes.py`; the lexicon in `analysis/match.py` covers 中文 and English. More languages are welcome.

### 7.6 Ground rules

- **Keep it dependency-free.** A pull request that adds a runtime dependency will not be merged unless it is optional and clearly justified.
- **Keep it deterministic.** Same input → same output, always.
- **Never crash on a bad file.** Degrade to container-only and record a warning.

---

## 📄 8. License

Released under the **MIT License** — see [LICENSE](LICENSE).

```
Copyright (c) 2026 gitstq

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Notes on responsible use**

- AudioVerdict measures signal properties. It is **not** a lie detector and not legal proof of tampering — findings are probabilistic evidence that deserves human review.
- Everything runs locally. Your audio never leaves your machine, because there is no network code in this project at all.
- Synthetic-likelihood scoring can produce false positives on heavily processed but honest material (podcast chains, restoration work). Treat it as a prompt to listen, not as a verdict.

---

<div align="center">

**AudioVerdict** — give your agent ears that can show their work.

🌐 [English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

</div>
