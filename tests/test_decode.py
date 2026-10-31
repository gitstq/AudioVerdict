"""Decoder tests (built-in, zero dependency)."""

from __future__ import annotations

import math
import struct

import pytest

from audioverdict.decode import detect_format, read_audio
from audioverdict.decode.mp3 import parse_frame_header
from audioverdict.decode.wav import read_wav, write_wav

from conftest import noise, silence, tone


def test_write_read_roundtrip(tmp_wav):
    samples = tone(440.0, 0.5, amplitude=0.6)
    path = tmp_wav(samples)
    data = read_audio(path, allow_ffmpeg=False)
    assert data.decoded
    assert data.channels == 1
    assert data.sample_rate == 22050
    assert abs(data.duration - 0.5) < 0.01
    # 16-bit quantisation means we cannot expect bit-exact recovery.
    for a, b in zip(samples[100:-100], data.samples[100:len(samples) - 100]):
        assert abs(a - b) < 0.001


def test_detect_format(tmp_wav):
    path = tmp_wav(tone(300.0, 0.2))
    assert detect_format(open(path, "rb").read(64)) == "WAV"


def test_silence_is_detected(tmp_wav):
    path = tmp_wav(silence(0.5))
    data = read_audio(path, allow_ffmpeg=False)
    assert max(abs(s) for s in data.samples) < 1e-9


def test_wav_float32(tmp_path):
    import struct as st

    rate, n = 22050, 1000
    body = b"".join(st.pack("<f", math.sin(i / 20)) for i in range(n))
    header = b"RIFF" + st.pack("<I", 36 + len(body)) + b"WAVE"
    header += b"fmt " + st.pack("<I", 16) + st.pack("<HHIIHH", 3, 1, rate, rate * 4, 4, 32)
    header += b"data" + st.pack("<I", len(body))
    path = str(tmp_path / "f32.wav")
    with open(path, "wb") as fh:
        fh.write(header + body)
    data = read_audio(path, allow_ffmpeg=False)
    assert data.decoded and data.codec == "PCM float" and data.bit_depth == 32


def test_wav_24bit(tmp_path):
    import struct as st

    rate, n = 22050, 500
    body = bytearray()
    for i in range(n):
        raw = int(math.sin(i / 15) * 8000000) & 0xFFFFFF
        body += st.pack("<I", raw)[:3]
    header = b"RIFF" + st.pack("<I", 36 + len(body)) + b"WAVE"
    header += b"fmt " + st.pack("<I", 16) + st.pack("<HHIIHH", 1, 1, rate, rate * 3, 3, 24)
    header += b"data" + st.pack("<I", len(body))
    path = str(tmp_path / "i24.wav")
    with open(path, "wb") as fh:
        fh.write(header + bytes(body))
    data = read_audio(path, allow_ffmpeg=False)
    assert data.decoded and data.bit_depth == 24 and len(data.samples) == n


def test_mp3_frame_header():
    # A 128 kbps / 44.1 kHz MPEG-1 Layer III frame header.
    hdr = bytes([0xFF, 0xFB, 0x90, 0x00])
    f = parse_frame_header(hdr, 0)
    assert f is not None
    assert f["bitrate"] == 128000
    assert f["sample_rate"] == 44100
    assert f["layer"] == 3
    assert f["length"] == 417


def test_mp3_invalid_header():
    assert parse_frame_header(b"\x00\x00\x00\x00", 0) is None


def test_unsupported_file(tmp_path):
    path = tmp_path / "junk.bin"
    path.write_bytes(b"not an audio file at all" * 4)
    with pytest.raises(ValueError):
        read_audio(str(path), allow_ffmpeg=False)


def test_container_only_without_ffmpeg(tmp_wav, tmp_path, monkeypatch):
    """Without ffmpeg a compressed file still yields container facts."""
    monkeypatch.setattr("audioverdict.decode.ffmpeg_pcm", lambda *a, **k: None)
    # Craft a minimal MP3: two valid frames of silence.
    frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + b"\x00" * 413
    path = str(tmp_path / "mini.mp3")
    with open(path, "wb") as fh:
        fh.write(frame * 4)
    data = read_audio(path, allow_ffmpeg=False)
    assert data.container.startswith("MPEG")
    assert data.decoded is False
    assert data.sample_rate == 44100
    assert data.metadata["frame_count"] == 4
