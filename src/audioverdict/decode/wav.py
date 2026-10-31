"""Pure-Python RIFF/WAVE reader.

Supports PCM (8/16/24/32-bit integer), 32/64-bit IEEE float, mu-law and A-law,
plus the usual metadata chunks (LIST/INFO, bext, fmt extensions).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from ..models import AudioData

# Format codes we understand.
WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_FLOAT = 0x0003
WAVE_FORMAT_ALAW = 0x0006
WAVE_FORMAT_MULAW = 0x0007
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def _decode_mulaw(byte: int) -> float:
    byte = ~byte & 0xFF
    sign = byte & 0x80
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    magnitude = ((mantissa << 1) | 0x21) << exponent
    magnitude -= 0x21
    value = magnitude / 32768.0
    return -value if sign else value


def _decode_alaw(byte: int) -> float:
    byte ^= 0x55
    sign = byte & 0x80
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    if exponent == 0:
        magnitude = (mantissa << 1) | 1
    else:
        magnitude = ((mantissa << 1) | 0x21) << (exponent - 1)
    value = magnitude / 32768.0
    return -value if sign else value


def _read_pcm(data: bytes, bits: int, channels: int, is_float: bool) -> Tuple[List[List[float]], int]:
    """Return per-channel sample lists and the frame count."""
    bytes_per_sample = bits // 8
    frame_size = bytes_per_sample * channels
    frames = len(data) // frame_size
    chans: List[List[float]] = [[] for _ in range(channels)]

    if bits == 8:
        # 8-bit WAVE is unsigned, centred on 128.
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                chans[c].append((data[base + c] - 128) / 128.0)
    elif bits == 16:
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                v = struct.unpack_from("<h", data, base + c * 2)[0]
                chans[c].append(v / 32768.0)
    elif bits == 24:
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                o = base + c * 3
                raw = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
                if raw & 0x800000:
                    raw -= 1 << 24
                chans[c].append(raw / 8388608.0)
    elif bits == 32 and is_float:
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                chans[c].append(struct.unpack_from("<f", data, base + c * 4)[0])
    elif bits == 32:
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                v = struct.unpack_from("<i", data, base + c * 4)[0]
                chans[c].append(v / 2147483648.0)
    elif bits == 64 and is_float:
        for i in range(frames):
            base = i * frame_size
            for c in range(channels):
                chans[c].append(struct.unpack_from("<d", data, base + c * 8)[0])
    else:
        raise ValueError(f"unsupported PCM bit depth: {bits}")

    return chans, frames


def _read_companded(data: bytes, channels: int, alaw: bool) -> Tuple[List[List[float]], int]:
    frames = len(data) // channels
    chans: List[List[float]] = [[] for _ in range(channels)]
    fn = _decode_alaw if alaw else _decode_mulaw
    for i in range(frames):
        base = i * channels
        for c in range(channels):
            chans[c].append(fn(data[base + c]))
    return chans, frames


def _parse_info(data: bytes) -> Dict[str, str]:
    """Parse a LIST/INFO block into key/value strings."""
    out: Dict[str, str] = {}
    if len(data) < 4:
        return out
    pos = 4  # skip the "INFO" list type
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = _u32(data, pos + 4)
        body = data[pos + 8:pos + 8 + size]
        try:
            text = body.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
        except Exception:
            text = ""
        if text:
            out[cid.decode("latin-1").strip()] = text
        pos += 8 + size + (size & 1)
    return out


def read_wav(buf: bytes) -> AudioData:
    if len(buf) < 12 or buf[0:4] != b"RIFF" or buf[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")

    fmt: Dict[str, int] = {}
    data = b""
    info: Dict[str, str] = {}
    bext: Dict[str, str] = {}
    warnings: List[str] = []
    data_truncated = False

    pos = 12
    size_limit = len(buf)
    while pos + 8 <= size_limit:
        cid = buf[pos:pos + 4]
        size = _u32(buf, pos + 4)
        body_start = pos + 8
        body_end = min(body_start + size, size_limit)
        if body_end - body_start < size:
            data_truncated = True
        body = buf[body_start:body_end]

        if cid == b"fmt " and size >= 16:
            fmt = {
                "format": _u16(body, 0),
                "channels": _u16(body, 2),
                "sample_rate": _u32(body, 4),
                "byte_rate": _u32(body, 8),
                "block_align": _u16(body, 12),
                "bits": _u16(body, 14),
            }
            if fmt["format"] == WAVE_FORMAT_EXTENSIBLE and size >= 40:
                fmt["format"] = _u16(body, 24)
                fmt["bits"] = _u16(body, 34)
        elif cid == b"data":
            data = body
        elif cid == b"LIST" and body[0:4] == b"INFO":
            info = _parse_info(body)
        elif cid == b"bext" and size >= 602:
            bext = {
                "description": body[0:256].split(b"\x00", 1)[0].decode("utf-8", "replace").strip(),
                "originator": body[256:288].split(b"\x00", 1)[0].decode("utf-8", "replace").strip(),
                "origination_date": body[320:330].decode("latin-1", "replace").strip(),
                "origination_time": body[330:338].decode("latin-1", "replace").strip(),
            }

        pos = body_end + (size & 1)
        if cid == b"data" and data_truncated and len(data) >= size:
            data_truncated = False

    if not fmt:
        raise ValueError("WAVE file without fmt chunk")
    if data_truncated:
        warnings.append("data chunk is truncated; analysis covers the available bytes")

    channels = max(1, fmt["channels"])
    sample_rate = max(1, fmt["sample_rate"])
    bits = fmt["bits"]
    is_float = fmt["format"] == WAVE_FORMAT_FLOAT

    if fmt["format"] in (WAVE_FORMAT_PCM, WAVE_FORMAT_FLOAT):
        chans, frames = _read_pcm(data, bits, channels, is_float)
        codec = "PCM float" if is_float else "PCM"
        lossy = False
        bit_depth = bits
    elif fmt["format"] == WAVE_FORMAT_MULAW:
        chans, frames = _read_companded(data, channels, alaw=False)
        codec, lossy, bit_depth = "mu-law", True, 8
    elif fmt["format"] == WAVE_FORMAT_ALAW:
        chans, frames = _read_companded(data, channels, alaw=True)
        codec, lossy, bit_depth = "A-law", True, 8
    else:
        raise ValueError(f"unsupported WAVE format code 0x{fmt['format']:04X}")

    duration = frames / sample_rate if sample_rate else 0.0
    mono: List[float] = []
    if frames:
        for i in range(frames):
            acc = 0.0
            for c in range(channels):
                acc += chans[c][i]
            mono.append(acc / channels)

    bitrate = int(fmt.get("byte_rate", 0) * 8) or int(
        sample_rate * channels * (bits // 8 or 1) * 8
    )

    meta: Dict[str, object] = dict(info)
    meta["wave_format_code"] = fmt["format"]
    meta["block_align"] = fmt.get("block_align", 0)
    if bext:
        meta["bext"] = bext

    return AudioData(
        samples=mono,
        channels=channels,
        sample_rate=sample_rate,
        duration=duration,
        bit_depth=bit_depth,
        container="WAV (RIFF)",
        codec=codec,
        bitrate=bitrate,
        decoded=True,
        lossy=lossy,
        metadata=meta,
        warnings=warnings,
    )


def write_wav(path: str, samples: List[float], sample_rate: int = 44100) -> None:
    """Minimal 16-bit mono WAV writer (used by tests and examples)."""
    import struct as _s

    frames = len(samples)
    body = bytearray()
    for v in samples:
        iv = int(max(-1.0, min(1.0, v)) * 32767)
        body += _s.pack("<h", iv)
    header = bytearray()
    header += b"RIFF" + _s.pack("<I", 36 + len(body)) + b"WAVE"
    header += b"fmt " + _s.pack("<I", 16) + _s.pack(
        "<HHIIHH", WAVE_FORMAT_PCM, 1, sample_rate, sample_rate * 2, 2, 16
    )
    header += b"data" + _s.pack("<I", len(body))
    with open(path, "wb") as fh:
        fh.write(bytes(header) + bytes(body))
