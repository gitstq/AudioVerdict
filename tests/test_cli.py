"""CLI tests."""

from __future__ import annotations

import json

import pytest

from audioverdict.cli import main

from conftest import noise, silence, tone


def _run(tmp_wav, argv):
    return main(argv)


def test_cli_analyze_text(tmp_wav, capsys):
    path = tmp_wav(tone(440.0, 1.5), name="cli.wav")
    assert main(["analyze", path, "--format", "text"]) == 0
    out = capsys.readouterr().out
    assert "AudioVerdict" in out


def test_cli_analyze_json_to_file(tmp_wav, tmp_path):
    path = tmp_wav(tone(440.0, 1.0), name="j.wav")
    out = str(tmp_path / "report.json")
    assert main(["analyze", path, "--format", "json", "--out", out]) == 0
    payload = json.load(open(out))
    assert payload["container"]["format"] == "WAV"


def test_cli_describe(tmp_wav, capsys):
    path = tmp_wav(tone(440.0, 1.0), name="d.wav")
    assert main(["describe", path]) == 0
    assert "440" in capsys.readouterr().out


def test_cli_verify(tmp_wav, capsys):
    path = tmp_wav(silence(1.0), name="v.wav")
    assert main(["verify", path]) == 0
    assert "digital" in capsys.readouterr().out.lower()


def test_cli_fingerprint(tmp_wav, capsys):
    path = tmp_wav(tone(440.0, 2.0), name="f.wav")
    assert main(["fingerprint", path]) == 0
    assert "avd-landmark-v1" in capsys.readouterr().out


def test_cli_compare(tmp_wav, capsys):
    a = tmp_wav(tone(440.0, 2.0), name="a.wav")
    b = tmp_wav(tone(440.0, 2.0), name="b.wav")
    assert main(["compare", a, b]) == 0
    assert "overlap" in capsys.readouterr().out


def test_cli_batch(tmp_wav, capsys, tmp_path):
    tmp_wav(tone(300.0, 1.0), name="x1.wav")
    tmp_wav(noise(1.0), name="x2.wav")
    assert main(["batch", str(tmp_path), "--format", "text"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) >= 3                   # header + one row per file


def test_cli_missing_file():
    assert main(["analyze", "/definitely/not/here.wav"]) == 2


def test_cli_selftest(tmp_path, capsys):
    out = str(tmp_path / "sf.wav")
    assert main(["selftest", "--out", out]) == 0
    assert "AudioVerdict" in capsys.readouterr().out
