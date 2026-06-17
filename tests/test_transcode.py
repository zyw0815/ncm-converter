# tests/test_transcode.py
import pytest
from core import transcode


def test_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(transcode.shutil, "which", lambda _: None)
    with pytest.raises(transcode.FfmpegNotFound):
        transcode.transcode("in.flac", "out.wav")


def test_build_command():
    cmd = transcode.build_command("in.flac", "out.wav")
    assert cmd[0] == "ffmpeg"
    assert "in.flac" in cmd and "out.wav" in cmd
    assert "-y" in cmd
