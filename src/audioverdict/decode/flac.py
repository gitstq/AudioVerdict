"""Pure-Python FLAC container reader (metadata + frame chain).

FLAC's own entropy/LPC decoding is intentionally out of scope; we instead mine
the metadata blocks and the *frame chain*, which yields strong forensic
evidence: STREAMINFO (including the MD5 of the original PCM), seek table
consistency, frame-number continuity and encoder padding.
"""

from __future__ import annotations

import struct
from typing import Dict, List

from ..models import AudioData

BLOCK_TYPES = {
    0: "STREAMINFO",
    1: "PADDING",
    2: "APPLICATION",
    3: "SEEKTABLE",
    4: "VORBIS_COMMENT",
    5: "CUESHEET",
    6: "PICTURE",
}

BLOCK_SIZES = {1: 192, 2: 576 << 1, 3: 576 << 2, 4: 576 << 3, 5: 576 << 4,
               6: 0, 7: 0, 8: 256, 9: 512, 10: 1024, 11: 2048, 12: 4096,
               13: 8192, 14: 16384, 15: 32768}

SAMPLE_RATES = {0: None, 1: 88200, 2: 176400, 3: 352800, 4: 48000, 5: 96000,
                6: 192000, 7: 384000, 8: 32000, 9: 64000, 10: 128000,
                11: 256000, 12: 16000, 13: 32000, 14: 64000, 15: 128000}

SAMPLE_SIZES = {0: None, 1: 8, 2: 12, 3: None, 4: 16, 5: 20, 6: 24, 7: 32}

CHANNEL_MODES = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 2, 9: 2, 10: 2}


def _parse_vorbis_comment(body: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if len(body) < 8:
        return out
    pos = 4 + struct.unpack("<I", body[4:8])[0]
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


def _parse_streaminfo(body: bytes) -> Dict[str, object]:
    if len(body) < 34:
        return {}
    min_bs, max_bs = struct.unpack(">HH", body[0:4])
    min_fs, max_fs = struct.unpack(">I", body[4:8])[0] >> 12, struct.unpack(">I", body[7:11])[0] & 0x0FFFFF
    b = body[10:18]
    sample_rate = (b[0] << 12) | (b[1] << 4) | (b[2] >> 4)
    channels = ((b[2] >> 1) & 0x07) + 1
    bits = (((b[2] & 0x01) << 4) | (b[3] >> 4)) + 1
    total = ((b[3] & 0x0F) << 32) | struct.unpack(">I", body[14:18])[0]
    return {
        "min_block_size": min_bs,
        "max_block_size": max_bs,
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_depth": bits,
        "total_samples": total,
        "md5": body[18:34].hex(),
    }


def _frame_header(buf: bytes, o: int) -> Dict[str, object]:
    b0, b1 = buf[o], buf[o + 1]
    if b0 != 0xFF or (b1 & 0xFC) != 0xF8:
        return {}
    bs_code = b1 & 0x0F
    sr_code = buf[o + 2] & 0x0F
    ch_code = (buf[o + 3] >> 4) & 0x0F
    size_code = (buf[o + 3] >> 1) & 0x07
    blocking = "variable" if (buf[o + 2] >> 4) & 0x0F in (6, 7) else "fixed"
    if bs_code == 0 or bs_code == 6 or bs_code == 7:
        return {}
    block_size = (BLOCK_SIZES.get(bs_code) or 0)
    sample_rate = SAMPLE_RATES.get(sr_code)
    channels = CHANNEL_MODES.get(ch_code, 0)
    bits = SAMPLE_SIZES.get(size_code)
    # UTF-8 coded frame/sample number
    v = buf[o + 4]
    if v < 0x80:
        num, used = v, 1
    elif v < 0xE0:
        num, used = ((v & 0x1F) << 6) | (buf[o + 5] & 0x3F), 2
    elif v < 0xF0:
        num, used = ((v & 0x0F) << 12) | ((buf[o + 5] & 0x3F) << 6) | (buf[o + 6] & 0x3F), 3
    else:
        num, used = None, 4
    return {
        "offset": o,
        "block_size": block_size,
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_depth": bits,
        "blocking": blocking,
        "number": num,
        "header_bytes": 4 + used + 1,
    }


def read_flac(buf: bytes) -> AudioData:
    if buf[0:4] != b"fLaC":
        raise ValueError("not a FLAC stream")

    pos = 4
    meta: Dict[str, object] = {}
    blocks: List[str] = []
    warnings: List[str] = []
    info: Dict[str, object] = {}

    while pos + 4 <= len(buf):
        head = buf[pos]
        last = bool(head & 0x80)
        btype = head & 0x7F
        size = struct.unpack(">I", b"\x00" + buf[pos + 1:pos + 4])[0]
        body = buf[pos + 4:pos + 4 + size]
        name = BLOCK_TYPES.get(btype, str(btype))
        blocks.append(name)
        if btype == 0:
            info = _parse_streaminfo(body)
        elif btype == 4:
            meta.update(_parse_vorbis_comment(body))
        elif btype == 3 and size:
            meta["seek_points"] = size // 18
        elif btype == 2 and size >= 4:
            meta["application_id"] = body[0:4].decode("latin-1", "replace")
        elif btype == 1:
            meta.setdefault("padding_bytes", 0)
            meta["padding_bytes"] += size
        pos += 4 + size
        if last:
            break

    if not info:
        raise ValueError("FLAC stream without STREAMINFO")

    # Walk the frame chain.
    frames: List[Dict[str, object]] = []
    p = pos
    limit = len(buf)
    rescues = 0
    while p + 8 <= limit:
        fh = _frame_header(buf, p)
        if not fh or not fh.get("block_size"):
            nxt = buf.find(b"\xff", p + 1)
            if nxt == -1:
                break
            rescues += 1 if nxt > p + 1 else 0
            p = nxt
            continue
        frames.append(fh)
        # Skip using a conservative estimate; we only need headers for evidence.
        p += int(fh["header_bytes"]) + 8
        nxt = buf.find(b"\xff\xf8", p)
        if nxt == -1:
            nxt = buf.find(b"\xff\xfa", p)
        if nxt == -1:
            break
        p = nxt

    sample_rate = int(info.get("sample_rate") or 0)
    channels = int(info.get("channels") or 0)
    total_samples = int(info.get("total_samples") or 0)
    duration = total_samples / sample_rate if sample_rate else 0.0
    bits = int(info.get("bit_depth") or 0)

    numbers = [f["number"] for f in frames if f.get("number") is not None]
    if numbers and numbers != sorted(numbers):
        warnings.append("FLAC frame numbers are not monotonically increasing")
    if rescues:
        warnings.append(f"{rescues} gap(s) while walking the FLAC frame chain")
    if info.get("md5") == "0" * 32:
        warnings.append("STREAMINFO MD5 is all zeroes (unknown original audio)")

    avg_bitrate = int(len(buf) * 8 / duration) if duration > 0 else 0

    meta.update({
        "metadata_blocks": blocks,
        "frames_scanned": len(frames),
        "total_samples": total_samples,
        "md5_of_pcm": info.get("md5"),
        "min_block_size": info.get("min_block_size"),
        "max_block_size": info.get("max_block_size"),
    })

    return AudioData(
        samples=None,
        channels=channels,
        sample_rate=sample_rate,
        duration=duration,
        bit_depth=bits,
        container="FLAC (native)",
        codec="FLAC",
        bitrate=avg_bitrate,
        decoded=False,
        lossy=False,
        metadata=meta,
        warnings=warnings,
    )
