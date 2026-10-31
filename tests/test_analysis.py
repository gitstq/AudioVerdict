"""End-to-end analysis tests."""

from __future__ import annotations

import json

import pytest

from audioverdict import analyse_file
from audioverdict.analysis import match as match_mod
from audioverdict.report import to_html, to_json, to_markdown, to_text

from conftest import RATE, noise, silence, tone


def test_analyse_tone(tmp_wav):
    path = tmp_wav(tone(220.0, 2.0, amplitude=0.5))
    r = analyse_file(path)
    assert r.container["pcm_decoded"] is True
    assert r.classification["label"] in ("tone", "music")
    g = r.global_features
    assert abs(g.pitch_hz - 220.0) < 5
    assert g.loudness_lufs > -70
    assert r.scorecard["overall"] > 0


def test_analyse_silence(tmp_wav):
    path = tmp_wav(silence(1.0))
    r = analyse_file(path)
    assert r.global_features.rms < 1e-6
    codes = {f.code for f in r.findings}
    assert "digital_silence" in codes


def test_analyse_noise(tmp_wav):
    path = tmp_wav(noise(2.0, amplitude=0.4))
    r = analyse_file(path)
    assert r.global_features.spectral_flatness > 0.05


def test_note_generation(tmp_wav):
    path = tmp_wav(tone(330.0, 3.0, amplitude=0.5))
    r = analyse_file(path, lang="en")
    assert len(r.notes) >= 1
    assert all(n.end > n.start for n in r.notes)


def test_chinese_notes(tmp_wav):
    path = tmp_wav(tone(330.0, 2.0, amplitude=0.5))
    r = analyse_file(path, lang="zh")
    assert r.notes


def test_description_match(tmp_wav):
    path = tmp_wav(tone(150.0, 2.0, amplitude=0.5))
    r = analyse_file(path, description="低沉 male 安静")
    m = r.scorecard["description_match"]
    assert m["recognised_terms"] >= 2
    assert isinstance(m["score"], float)


def test_fingerprint_present(tmp_wav):
    path = tmp_wav(tone(440.0, 2.0, amplitude=0.5))
    r = analyse_file(path)
    assert r.fingerprints
    assert len(r.fingerprints[0]["digest"]) == 8


def test_fingerprint_stable(tmp_wav):
    a = analyse_file(tmp_wav(tone(440.0, 2.0), name="a.wav"))
    b = analyse_file(tmp_wav(tone(440.0, 2.0), name="b.wav"))
    assert a.fingerprints[0]["digest"] == b.fingerprints[0]["digest"]


def test_render_json(tmp_wav):
    r = analyse_file(tmp_wav(tone(440.0, 1.0), name="j.wav"))
    payload = json.loads(to_json(r))
    assert payload["container"]["format"] == "WAV"
    assert "_visuals" not in payload["scorecard"]


def test_render_text_and_markdown(tmp_wav):
    r = analyse_file(tmp_wav(tone(440.0, 1.0), name="t.wav"))
    text = to_text(r)
    md = to_markdown(r)
    assert "AudioVerdict" in text
    assert "AudioVerdict" in md
    assert "## " in md


def test_render_html(tmp_wav):
    r = analyse_file(tmp_wav(tone(440.0, 1.5), name="h.wav"))
    html = to_html(r)
    assert html.startswith("<!doctype html>")
    assert "AudioVerdict" in html
    assert html.rstrip().endswith("</html>")


def test_render_markdown_chinese(tmp_wav):
    r = analyse_file(tmp_wav(tone(440.0, 1.0), name="z.wav"))
    md = to_markdown(r, lang="zh")
    assert "容器信息" in md


def test_match_no_terms(tmp_wav):
    r = analyse_file(tmp_wav(tone(440.0, 1.0), name="m.wav"))
    m = match_mod.match(r, "zzzz nothing recognisable")
    assert m["verdict"] == "no_terms"


def test_batch_like_multiple_files(tmp_wav):
    for i in range(3):
        analyse_file(tmp_wav(tone(200.0 + i * 100, 1.0), name=f"b{i}.wav"))
    # Simply reaching here proves repeated analysis is stable.


def _clipped_tone(freq=300.0, seconds=2.0, rate=RATE, drive=1.8):
    """A hard-clipped sine: lots of harmonics, but no codec-shaped cliff."""
    import math

    return [max(-1.0, min(1.0, drive * math.sin(2 * math.pi * freq * (i / rate))))
            for i in range(int(seconds * rate))]


def test_clipped_tone_is_not_a_false_transcode(tmp_wav):
    """A pure tone's spectrum dies into the noise floor — that is not a codec cliff."""
    r = analyse_file(tmp_wav(_clipped_tone(), name="clip.wav"))
    codes = {f.code for f in r.findings}
    assert "clipping" in codes                      # the real problem
    assert "transcode_into_lossless" not in codes   # not the invented one
    assert "upsampled_source" not in codes
    assert "bandwidth_shortfall" not in codes


def test_band_cliff_reports_its_level():
    """`band_cliff` must expose the band level so callers can sanity-check it."""
    from audioverdict.dsp.spectral import band_cliff, spectrum

    sig = _clipped_tone(rate=22050)
    mags = spectrum(sig[:2048], 2048)
    cliff = band_cliff(mags, 22050)
    assert "level_db" in cliff
    assert cliff["detected"] == 0.0
