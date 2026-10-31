"""Pure-Python Ogg container reader (Vorbis / Opus / FLAC-in-Ogg).

Page-level evidence is what matters for forensics: granule positions, page
sequence continuity, serial numbers and the codec identification header.
"""

from __future__ import annotations

import struct
from typing import Dict, List

from ..models import AudioData


def _pages(buf: bytes) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    pos = 0
    n = len(buf)
    while True:
        o = buf.find(b"OggS", pos)
        if o == -1:
            break
        if o + 27 > n:
            break
        header_type = buf[o + 5]
        granule = struct.unpack("<q", buf[o + 6:o + 14])[0]
        serial = struct.unpack("<I", buf[o + 14:o + 18])[0]
        seq = struct.unpack("<I", buf[o + 18:o + 22])[0]
        nseg = buf[o + 26]
        if o + 27 + nseg > n:
            break
        segs = buf[o + 27:o + 27 + nseg]
        body_len = sum(segs)
        out.append({
            "offset": o,
            "header_type": header_type,
            "granule": granule,
            "serial": serial,
            "seq": seq,
            "segments": nseg,
            "body_offset": o + 27 + nseg,
            "body_length": body_len,
        })
        pos = o + 27 + nseg + body_len
    return out


def _vorbis_comment(body: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if len(body) < 11:
        return out
    pos = 7 + struct.unpack("<I", body[7:11])[0]
    if pos + 4 > len(body):
        return out
    count = struct.unpack("<I", body[pos:pos + 4])[0]
    pos += 4
    for _ in range(count):
        if pos + 4 > len(body):
            break
        ln = struct.unpack("<I", body[pos:pos + 4])[0]
        pos += 4
        raw = body[pos:pos + ln]
        pos += ln
        if b"=" in raw:
            k, v = raw.split(b"=", 1)
            try:
                out[k.decode("utf-8", "replace").upper()] = v.decode("utf-8", "replace")
            except Exception:
                pass
    return out


def read_ogg(buf: bytes) -> AudioData:
    if buf[0:4] != b"OggS":
        raise ValueError("not an Ogg stream")

    pages = _pages(buf)
    if not pages:
        raise ValueError("Ogg stream without readable pages")

    warnings: List[str] = []
    serials = {p["serial"] for p in pages}
    meta: Dict[str, object] = {"page_count": len(pages), "streams": len(serials)}

    # Sequence continuity per stream (a re-mux leaves gaps or duplicates).
    for serial in sorted(serials):
        seqs = [p["seq"] for p in pages if p["serial"] == serial]
        if seqs != list(range(seqs[0], seqs[0] + len(seqs))):
            warnings.append(f"Ogg page sequence is discontinuous on stream {serial}")
        if len(seqs) != len(set(seqs)):
            warnings.append(f"duplicate Ogg page numbers on stream {serial}")

    codec = "unknown"
    sample_rate = 0
    channels = 0
    bitrate = 0
    duration = 0.0
    lossy = True

    first = pages[0]
    body = buf[first["body_offset"]:first["body_offset"] + first["body_length"]]

    if body[1:7] == b"vorbis":
        codec = "Vorbis"
        if len(body) >= 28:
            version = struct.unpack("<I", body[7:11])[0]
            channels = body[11]
            sample_rate = struct.unpack("<I", body[12:16])[0]
            nominal = struct.unpack("<i", body[20:24])[0]
            meta["vorbis_version"] = version
            meta["nominal_bitrate"] = nominal if nominal > 0 else None
            bitrate = nominal if nominal > 0 else 0
        last_granule = max(p["granule"] for p in pages)
        duration = last_granule / sample_rate if sample_rate else 0.0
        for p in pages[1:3]:
            pb = buf[p["body_offset"]:p["body_offset"] + p["body_length"]]
            if pb[0:7] == b"\x03vorbis":
                meta.update(_vorbis_comment(pb))
    elif body[0:8] == b"OpusHead":
        codec = "Opus"
        if len(body) >= 12:
            channels = body[9]
            meta["pre_skip"] = struct.unpack("<H", body[10:12])[0]
            sample_rate = 48000
        granules = [p["granule"] for p in pages]
        span = max(granules) - min(granules)
        duration = span / 48000.0
    elif body[0:8] == b"\x7fFLAC":
        codec = "FLAC (Ogg mapping)"
        lossy = False
        if len(body) >= 40:
            sample_rate = (body[21] << 12) | (body[22] << 4) | (body[23] >> 4)
            channels = ((body[23] >> 1) & 0x07) + 1

    if duration <= 0:
        # Fall back on a byte-rate estimate.
        duration = len(buf) / max(1, bitrate / 8) if bitrate else 0.0
    if not bitrate and duration:
        bitrate = int(len(buf) * 8 / duration)

    return AudioData(
        samples=None,
        channels=channels,
        sample_rate=sample_rate,
        duration=duration,
        bit_depth=0,
        container="Ogg",
        codec=codec,
        bitrate=bitrate,
        decoded=False,
        lossy=lossy,
        metadata=meta,
        warnings=warnings,
    )
