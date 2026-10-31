"""Pure-Python ISO-BMFF / MP4 / M4A reader.

 Walks the atom tree to pull timing, codec configuration and iTunes-style
metadata. Also used for MP4 video files where we only care about the audio
track.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

from ..models import AudioData

# iTunes metadata atoms whose payload is: 4-byte size, 4-byte type, then data.
ILST_DATA_ATOMS = {"©nam", "©ART", "©alb", "©cmt", "©gen", "©day", "©too", "©enc"}


def _walk(buf: bytes, start: int, end: int, depth: int = 0,
          out: Optional[List[Tuple[str, int, int, int]]] = None
          ) -> List[Tuple[str, int, int, int]]:
    """Yield (type, header_start, payload_start, payload_end)."""
    if out is None:
        out = []
    pos = start
    while pos + 8 <= end:
        size = struct.unpack(">I", buf[pos:pos + 4])[0]
        typ = buf[pos + 4:pos + 8].decode("latin-1", "replace")
        head = 8
        if size == 1:
            if pos + 16 > end:
                break
            size = struct.unpack(">Q", buf[pos + 8:pos + 16])[0]
            head = 16
        elif size == 0:
            size = end - pos
        if size < head:
            break
        p_start, p_end = pos + head, min(pos + size, end)
        out.append((typ, pos, p_start, p_end))
        if typ in ("moov", "trak", "mdia", "minf", "stbl", "udta", "meta", "ilst", "edts"):
            if typ == "meta" and p_start + 4 <= p_end:
                # meta has a version/flags field before child atoms
                _walk(buf, p_start + 4, p_end, depth + 1, out)
            else:
                _walk(buf, p_start, p_end, depth + 1, out)
        pos = p_start + (size - head)
    return out


def read_mp4(buf: bytes) -> AudioData:
    if len(buf) < 12 or buf[4:8] not in (b"ftyp", b"moov", b"mdat"):
        raise ValueError("not an ISO-BMFF/MP4 file")

    atoms = _walk(buf, 0, len(buf))
    by_type: Dict[str, List[Tuple[str, int, int, int]]] = {}
    for a in atoms:
        by_type.setdefault(a[0], []).append(a)

    warnings: List[str] = []
    meta: Dict[str, object] = {}

    if "ftyp" in by_type:
        _, _, ps, pe = by_type["ftyp"][0]
        meta["brand"] = buf[ps:ps + 4].decode("latin-1", "replace")
        meta["compatible_brands"] = [
            buf[i:i + 4].decode("latin-1", "replace")
            for i in range(ps + 4, min(pe, ps + 64), 4)
            if buf[i:i + 4].strip(b"\x00")
        ]

    timescale = 0
    units = 0
    if "mvhd" in by_type:
        _, _, ps, pe = by_type["mvhd"][0]
        version = buf[ps]
        if version == 1 and pe - ps >= 32:
            timescale = struct.unpack(">I", buf[ps + 20:ps + 24])[0]
            units = struct.unpack(">Q", buf[ps + 24:ps + 32])[0]
        elif pe - ps >= 20:
            timescale = struct.unpack(">I", buf[ps + 12:ps + 16])[0]
            units = struct.unpack(">I", buf[ps + 16:ps + 20])[0]
    duration = units / timescale if timescale else 0.0

    sample_rate = 0
    channels = 0
    codec = "AAC"
    bit_depth = 0
    for _, _, ps, pe in by_type.get("mdhd", []):
        version = buf[ps]
        if version == 1 and pe - ps >= 32:
            ts = struct.unpack(">I", buf[ps + 20:ps + 24])[0]
        elif pe - ps >= 20:
            ts = struct.unpack(">I", buf[ps + 12:ps + 16])[0]
        else:
            continue
        if ts:
            meta["media_timescale"] = ts

    for _, _, ps, pe in by_type.get("stsd", []):
        # stsd layout: version(4) + entry_count(4), then each entry starts with
        # its own size(4) + format(4).
        if pe - ps >= 16 and buf[ps + 12:ps + 16] == b"mp4a":
            codec = "AAC (mp4a)"
            e = ps + 16                      # first byte after the format code
            if pe - e >= 36:
                channels = struct.unpack(">H", buf[e + 16:e + 18])[0]
                bit_depth = buf[e + 18]
                sample_rate = struct.unpack(">I", buf[e + 24:e + 28])[0] >> 16
        elif pe - ps >= 16:
            codec = buf[ps + 12:ps + 16].decode("latin-1", "replace").strip()
    if not sample_rate and "media_timescale" in meta:
        sample_rate = int(meta["media_timescale"])

    # iTunes style metadata.
    tags: Dict[str, str] = {}
    ilst_atoms = by_type.get("ilst", [])
    if ilst_atoms:
        _, ips, ipe, _ = ilst_atoms[0]
        sub = _walk(buf, ips, ipe)
        for typ, _, ps, pe in sub:
            if pe - ps >= 8 and buf[ps + 4:ps + 8] == b"data":
                try:
                    val = buf[ps + 16:pe].decode("utf-8", "replace").strip("\x00")
                except Exception:
                    val = ""
                if val:
                    tags[typ.strip("©")] = val
    if tags:
        meta.update(tags)

    if not by_type.get("moov"):
        warnings.append("moov atom missing; duration may be unreliable")
    if by_type.get("moov") and by_type.get("mdat"):
        moov_pos = by_type["moov"][0][1]
        mdat_pos = by_type["mdat"][0][1]
        meta["faststart"] = bool(moov_pos < mdat_pos)
        if moov_pos > mdat_pos:
            warnings.append("moov sits after mdat (not streamable/faststart)")

    bitrate = int(len(buf) * 8 / duration) if duration else 0

    return AudioData(
        samples=None,
        channels=channels,
        sample_rate=sample_rate,
        duration=duration,
        bit_depth=bit_depth,
        container="ISO-BMFF (MP4/M4A)",
        codec=codec,
        bitrate=bitrate,
        decoded=False,
        lossy=True,
        metadata=meta,
        warnings=warnings,
    )
