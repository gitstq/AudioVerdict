"""Pure-Python AIFF / AIFF-C reader (big-endian PCM)."""

from __future__ import annotations

import struct
from typing import Dict, List

from ..models import AudioData


def _extended80(buf: bytes, o: int) -> float:
    """Decode an 80-bit SANE extended float (used by AIFF sample rates)."""
    if o + 10 > len(buf):
        return 0.0
    sign = -1.0 if buf[o] & 0x80 else 1.0
    exponent = ((buf[o] & 0x7F) << 8) | buf[o + 1]
    mantissa = struct.unpack(">Q", buf[o + 2:o + 10])[0]
    if exponent == 0 and mantissa == 0:
        return 0.0
    return sign * mantissa * (2.0 ** (exponent - 16383 - 63))


def read_aiff(buf: bytes) -> AudioData:
    if buf[0:4] != b"FORM" or buf[8:12] not in (b"AIFF", b"AIFC"):
        raise ValueError("not an AIFF/AIFF-C file")

    form = buf[8:12].decode("latin-1")
    pos = 12
    comm: Dict[str, object] = {}
    data = b""
    meta: Dict[str, object] = {}
    warnings: List[str] = []

    while pos + 8 <= len(buf):
        cid = buf[pos:pos + 4]
        size = struct.unpack(">I", buf[pos + 4:pos + 8])[0]
        body = buf[pos + 8:pos + 8 + size]
        if cid == b"COMM" and size >= 18:
            channels = struct.unpack(">h", body[0:2])[0]
            frames = struct.unpack(">I", body[2:6])[0]
            bits = struct.unpack(">h", body[6:8])[0]
            rate = _extended80(body, 8)
            comm = {"channels": channels, "frames": frames, "bits": bits, "rate": rate}
            if size >= 22:
                compression = body[18:22]
                comm["compression"] = compression.decode("latin-1", "replace")
                meta["compression"] = comm["compression"]
                meta["compression_name"] = (
                    body[22:].split(b"\x00", 1)[0].decode("latin-1", "replace")
                    if size > 22 else ""
                )
        elif cid == b"SSND":
            if size >= 8:
                body = body[8:]          # offset + blockSize
            data = body
        elif cid == b"NAME" and size:
            meta["NAME"] = body.split(b"\x00", 1)[0].decode("latin-1", "replace")
        elif cid == b"ANNO" and size:
            meta["ANNO"] = body.split(b"\x00", 1)[0].decode("latin-1", "replace")
        pos += 8 + size + (size & 1)

    if not comm:
        raise ValueError("AIFF file without COMM chunk")

    channels = max(1, int(comm["channels"]))
    bits = int(comm["bits"])
    rate = int(round(float(comm["rate"]))) or 44100
    compression = str(comm.get("compression", ""))

    samples: List[float] = []
    decoded = False
    lossy = False
    codec = "PCM (big-endian)"

    if compression in ("", "NONE", "raw "):
        bytes_per = bits // 8
        frame = bytes_per * channels
        n = len(data) // frame
        for i in range(n):
            acc = 0.0
            for c in range(channels):
                o = i * frame + c * bytes_per
                if bits == 8:
                    v = struct.unpack_from(">b", data, o)[0] / 128.0
                elif bits == 16:
                    v = struct.unpack_from(">h", data, o)[0] / 32768.0
                elif bits == 24:
                    raw = (data[o] << 16) | (data[o + 1] << 8) | data[o + 2]
                    if raw & 0x800000:
                        raw -= 1 << 24
                    v = raw / 8388608.0
                elif bits == 32:
                    v = struct.unpack_from(">i", data, o)[0] / 2147483648.0
                else:
                    v = 0.0
                acc += v
            samples.append(acc / channels)
        decoded = True
    elif compression in ("ulaw", "µlaw"):
        codec, lossy = "mu-law", True
    elif compression in ("alaw",):
        codec, lossy = "A-law", True
    elif compression.lower() in ("fl32", "fl64"):
        codec = "PCM float"
    else:
        codec = compression.strip() or "unknown"
        warnings.append(f"AIFF-C compression '{compression}' is not decoded")

    declared = int(comm["frames"])
    duration = (declared / rate) if declared else (len(samples) / rate if rate else 0.0)
    if declared and samples and abs(declared - len(samples)) > max(2, declared // 100):
        warnings.append("COMM declares %d frames but %d were decoded" % (declared, len(samples)))

    meta["declared_frames"] = declared
    meta["form"] = form

    return AudioData(
        samples=samples if decoded else None,
        channels=channels,
        sample_rate=rate,
        duration=duration,
        bit_depth=bits,
        container=form,
        codec=codec,
        bitrate=rate * channels * (bits // 8 or 1) * 8,
        decoded=decoded,
        lossy=lossy,
        metadata=meta,
        warnings=warnings,
    )
