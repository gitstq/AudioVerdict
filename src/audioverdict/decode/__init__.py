"""Format detection and dispatch for the zero-dependency decoders."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
from typing import Dict, Optional, Tuple

from ..models import AudioData
from . import aiff, flac, mp3, mp4, ogg, wav

__all__ = ["read_audio", "detect_format", "SUPPORTED", "ffmpeg_pcm"]

SUPPORTED = ["WAV", "AIFF", "FLAC", "MP3", "OGG", "MP4/M4A"]

_MAX_BYTES = 512 * 1024 * 1024          # refuse to read absurd files into RAM

# Formats whose audio data we cannot decode with the standard library alone.
_CONTAINER_ONLY = ("FLAC", "MP3", "OGG", "MP4/M4A")


def ffmpeg_pcm(path: str, target_rate: int = 44100) -> Optional[Tuple[list, int]]:
    """Optional helper: decode to mono PCM with ffmpeg if it is installed.

    The library never requires ffmpeg - it is a convenience that unlocks full
    feature analysis for compressed formats when present.
    """
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    cmd = [exe, "-v", "quiet", "-nostdin", "-i", path,
           "-f", "s16le", "-ac", "1", "-ar", str(target_rate), "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    raw = proc.stdout
    count = len(raw) // 2
    values = struct.unpack("<%dh" % count, raw[:count * 2])
    return [v / 32768.0 for v in values], target_rate


def detect_format(buf: bytes) -> str:
    if buf[0:4] == b"RIFF" and buf[8:12] == b"WAVE":
        return "WAV"
    if buf[0:4] == b"FORM" and buf[8:12] in (b"AIFF", b"AIFC"):
        return "AIFF"
    if buf[0:4] == b"fLaC":
        return "FLAC"
    if buf[0:4] == b"OggS":
        return "OGG"
    if buf[0:3] == b"ID3":
        return "MP3"
    if buf[4:8] in (b"ftyp", b"moov", b"mdat"):
        return "MP4/M4A"
    if buf[0:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2"):
        return "MP3"
    return "UNKNOWN"


def read_audio(path: str, max_bytes: int = _MAX_BYTES,
               allow_ffmpeg: bool = True) -> AudioData:
    """Read any supported audio file into an :class:`AudioData`.

    With ``allow_ffmpeg`` the compressed formats (FLAC/MP3/OGG/M4A) are also
    decoded to PCM when ffmpeg happens to be installed. Without it they are
    still parsed - just at container level.
    """
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file too large ({size} bytes); raise max_bytes to continue")
    with open(path, "rb") as fh:
        buf = fh.read(max_bytes)

    kind = detect_format(buf)
    try:
        if kind == "WAV":
            data = wav.read_wav(buf)
        elif kind == "AIFF":
            data = aiff.read_aiff(buf)
        elif kind == "FLAC":
            data = flac.read_flac(buf)
        elif kind == "MP3":
            data = mp3.read_mp3(buf)
        elif kind == "OGG":
            data = ogg.read_ogg(buf)
        elif kind == "MP4/M4A":
            data = mp4.read_mp4(buf)
        else:
            raise ValueError(f"unsupported or unrecognised audio format: {kind}")
    except Exception as exc:
        raise ValueError(f"{kind or 'file'} could not be parsed: {exc}") from exc

    data.metadata.setdefault("file_size", size)
    data.metadata["detected_format"] = kind
    data.metadata["path"] = os.path.abspath(path)

    if data.decoded:
        data.metadata["decode_path"] = "built-in decoder"
    else:
        data.metadata["decode_path"] = "container only"
        if allow_ffmpeg:
            try:
                pcm = ffmpeg_pcm(path)
            except Exception:
                pcm = None
            if pcm:
                samples, rate = pcm
                data.samples = samples
                data.decoded = True
                data.metadata["decode_path"] = "ffmpeg (optional helper)"
                if not data.sample_rate:
                    data.sample_rate = rate
                if not data.duration:
                    data.duration = len(samples) / float(rate or 44100)
                data.warnings.append(
                    "PCM obtained via the optional ffmpeg helper; container was still "
                    "verified by the built-in parser")
    return data


def container_summary(data: AudioData) -> Dict[str, object]:
    """Compact container description used by every report."""
    return {
        "format": data.metadata.get("detected_format", "?"),
        "container": data.container,
        "codec": data.codec,
        "channels": data.channels,
        "sample_rate": data.sample_rate,
        "bit_depth": data.bit_depth,
        "bitrate_bps": data.bitrate,
        "duration_seconds": round(data.duration, 3),
        "pcm_decoded": data.decoded,
        "lossy": data.lossy,
        "file_size": data.metadata.get("file_size"),
        "metadata": {k: v for k, v in data.metadata.items()
                     if k not in ("toc", "path", "detected_format", "file_size")},
    }
