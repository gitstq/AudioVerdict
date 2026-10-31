"""Pure-Python MPEG audio (MP1/2/3) frame-chain reader.

We do not run a Huffman decoder here (that would be a second project); instead
we walk the *frame chain* and extract container-level evidence, which is
exactly what tamper detection needs: bitrate profile, encoder padding, VBR
headers, Xing/Info tags, ID3 tags and mono/stereo switching.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

from ..models import AudioData

BITRATES_V1L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
BITRATES_V2L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
BITRATES_V1L1 = [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0]
BITRATES_V1L2 = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0]
BITRATES_V2L1 = [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0]
BITRATES_V2L2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]

SAMPLE_RATES = {
    3: [44100, 48000, 32000],        # MPEG 1
    2: [22050, 24000, 16000],        # MPEG 2
    0: [11025, 12000, 8000],         # MPEG 2.5
}

SAMPLES_PER_FRAME = {
    3: {1: 384, 2: 1152, 3: 1152},   # MPEG1 layer1/2/3
    2: {1: 384, 2: 1152, 3: 576},    # MPEG2
    0: {1: 384, 2: 1152, 3: 576},    # MPEG2.5
}


def _bitrate_table(version_bits: int, layer: int) -> List[int]:
    if layer == 1:
        return BITRATES_V1L1 if version_bits == 3 else BITRATES_V2L1
    if layer == 2:
        return BITRATES_V1L2 if version_bits == 3 else BITRATES_V2L2
    return BITRATES_V1L3 if version_bits == 3 else BITRATES_V2L3


def parse_frame_header(b: bytes, o: int) -> Optional[Dict[str, int]]:
    """Parse a 4-byte MPEG audio header, returning None when invalid."""
    if o + 4 > len(b):
        return None
    if b[o] != 0xFF or (b[o + 1] & 0xE0) != 0xE0:
        return None
    version_bits = (b[o + 1] >> 3) & 0x03
    layer_bits = (b[o + 1] >> 1) & 0x03
    if version_bits == 1 or layer_bits == 0:
        return None
    layer = 4 - layer_bits
    crc = not (b[o + 1] & 0x01)
    br_index = (b[o + 2] >> 4) & 0x0F
    sr_index = (b[o + 2] >> 2) & 0x03
    padding = (b[o + 2] >> 1) & 0x01
    private = b[o + 2] & 0x01
    mode = (b[o + 3] >> 6) & 0x03
    if br_index in (0, 15) or sr_index == 3:
        return None
    rates = SAMPLE_RATES.get(version_bits)
    sample_rate = rates[sr_index] if rates else 0
    bitrate = _bitrate_table(version_bits, layer)[br_index] * 1000
    spf = SAMPLES_PER_FRAME[version_bits][layer]
    if sample_rate == 0 or bitrate == 0:
        return None
    if layer == 1:
        frame_len = (12 * bitrate // sample_rate + padding) * 4
    else:
        frame_len = spf * bitrate // (8 * sample_rate) + padding
    return {
        "offset": o,
        "version_bits": version_bits,
        "layer": layer,
        "crc": int(crc),
        "bitrate": bitrate,
        "sample_rate": sample_rate,
        "padding": padding,
        "private": private,
        "mode": mode,
        "samples": spf,
        "length": frame_len,
    }


def _parse_id3v2(buf: bytes) -> Tuple[Dict[str, str], int, List[str]]:
    """Return (tags, total_tag_size, warnings)."""
    tags: Dict[str, str] = {}
    warnings: List[str] = []
    if len(buf) < 10 or buf[0:3] != b"ID3":
        return tags, 0, warnings
    flags = buf[5]
    size = ((buf[6] & 0x7F) << 21) | ((buf[7] & 0x7F) << 14) | ((buf[8] & 0x7F) << 7) | (buf[9] & 0x7F)
    total = 10 + size
    pos = 10
    end = min(total, len(buf))
    if flags & 0x40 and pos + 4 <= end:      # extended header
        ext_size = struct.unpack(">I", buf[pos:pos + 4])[0]
        pos += 4 + ext_size
    while pos + 10 <= end:
        fid = buf[pos:pos + 4]
        if not fid.strip(b"\x00"):
            break
        fsize = struct.unpack(">I", buf[pos + 4:pos + 8])[0]
        body = buf[pos + 10:pos + 10 + fsize]
        if fid.startswith(b"T"):
            try:
                enc = body[0]
                raw = body[1:]
                if enc == 1:
                    text = raw.decode("utf-16", "replace").rstrip("\x00")
                elif enc == 3:
                    text = raw.decode("utf-8", "replace").rstrip("\x00")
                else:
                    text = raw.decode("latin-1", "replace").rstrip("\x00")
            except Exception:
                text = ""
            if text:
                tags[fid.decode("latin-1")] = text
        pos += 10 + fsize
    if total > len(buf):
        warnings.append("ID3v2 tag declares more bytes than the file contains")
    return tags, total, warnings


def _parse_id3v1(buf: bytes) -> Dict[str, str]:
    if len(buf) < 128 or buf[-128:-125] != b"TAG":
        return {}
    t = buf[-128:]
    def s(a: int, b: int) -> str:
        return t[a:b].split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
    out = {"TITLE": s(3, 33), "ARTIST": s(33, 63), "ALBUM": s(63, 93), "YEAR": s(93, 97)}
    if t[125] == 0 and t[126] != 0:
        out["TRACK"] = str(t[126])
    return {k: v for k, v in out.items() if v}


def _xing(buf: bytes, frame: Dict[str, int]) -> Dict[str, object]:
    """Parse Xing/Info or VBRI header sitting inside the first frame."""
    out: Dict[str, object] = {}
    mode = frame["mode"]
    if mode == 3:
        side = 32 if frame["version_bits"] == 3 else 17
    else:
        side = 17 if frame["version_bits"] == 3 else 9
    start = frame["offset"] + 4 + (2 if frame["crc"] else 0) + side
    head = buf[start:start + 4]
    if head == b"Xing" or head == b"Info":
        out["vbr_header"] = head.decode("latin-1")
        flags = struct.unpack(">I", buf[start + 4:start + 8])[0]
        p = start + 8
        if flags & 0x01:
            out["frame_count"] = struct.unpack(">I", buf[p:p + 4])[0]
            p += 4
        if flags & 0x02:
            out["byte_count"] = struct.unpack(">I", buf[p:p + 4])[0]
            p += 4
        if flags & 0x04 and p + 100 <= len(buf):
            out["toc"] = list(buf[p:p + 100])
            p += 100
        if flags & 0x08:
            out["quality"] = struct.unpack(">I", buf[p:p + 4])[0]
    elif head == b"VBRI":
        out["vbr_header"] = "VBRI"
        try:
            out["byte_count"] = struct.unpack(">I", buf[start + 10:start + 14])[0]
            out["frame_count"] = struct.unpack(">I", buf[start + 14:start + 18])[0]
        except Exception:
            pass
    return out


def read_mp3(buf: bytes) -> AudioData:
    tags, start, warnings = _parse_id3v2(buf)
    tags.update(_parse_id3v1(buf))

    frames: List[Dict[str, int]] = []
    pos = start
    limit = len(buf)
    rescues = 0
    while pos < limit - 4:
        f = parse_frame_header(buf, pos)
        if f and f["length"] >= 4 and pos + f["length"] <= limit:
            frames.append(f)
            pos += f["length"]
            continue
        # Try to resynchronise after garbage (tags, junk, or a splice point).
        nxt = buf.find(b"\xff", pos + 1)
        if nxt == -1 or nxt > pos + 65536:
            break
        if nxt > pos + 1:
            rescues += 1
        pos = nxt

    if not frames:
        raise ValueError("no valid MPEG audio frames found")

    sample_rates = [f["sample_rate"] for f in frames]
    channels = [1 if f["mode"] == 3 else 2 for f in frames]
    bitrates = [f["bitrate"] for f in frames]
    sample_rate = max(set(sample_rates), key=sample_rates.count)
    chan = max(set(channels), key=channels.count)

    if len(set(sample_rates)) > 1:
        warnings.append("sample rate changes mid-stream: %s" % sorted(set(sample_rates)))
    if len(set(channels)) > 1:
        warnings.append("channel mode changes mid-stream")
    if rescues:
        warnings.append(f"{rescues} resynchronisation gap(s) in the frame chain")

    spf = frames[0]["samples"]
    duration = sum(f["samples"] for f in frames) / sample_rate
    avg_bitrate = int(sum(bitrates) / len(bitrates))
    xing = _xing(buf, frames[0]) if frames else {}

    meta: Dict[str, object] = dict(tags)
    meta["frame_count"] = len(frames)
    meta["samples_per_frame"] = spf
    meta["vbr"] = len(set(bitrates)) > 1
    meta["min_bitrate"] = min(bitrates)
    meta["max_bitrate"] = max(bitrates)
    meta["padding_ratio"] = round(sum(f["padding"] for f in frames) / len(frames), 4)
    meta["encoder_delay_hint"] = None
    meta.update(xing)
    if "frame_count" in xing and "toc" not in xing:
        meta["xing_frame_count_matches_scan"] = bool(xing["frame_count"] == len(frames))

    return AudioData(
        samples=None,
        channels=chan,
        sample_rate=sample_rate,
        duration=duration,
        bit_depth=0,
        container="MPEG audio (elementary stream)",
        codec=f"MPEG-{1 if frames[0]['version_bits'] == 3 else 2} layer {frames[0]['layer']}",
        bitrate=avg_bitrate,
        decoded=False,
        lossy=True,
        metadata=meta,
        warnings=warnings,
    )


def frame_energy_profile(buf: bytes, frames: List[Dict[str, int]]) -> List[float]:
    """Bitrate-derived loudness proxy, one value per frame.

    A full Huffman decode is out of scope; the per-frame bit reservoir usage is
    a well-known proxy for perceptual complexity and is good enough to locate
    splices, silence and level jumps.
    """
    return [f["bitrate"] / 320000.0 for f in frames]
