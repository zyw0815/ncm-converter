# tests/test_transcode.py
import pytest
from core import transcode


def test_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(transcode.shutil, "which", lambda _: None)
    monkeypatch.setattr(transcode, "_COMMON_DIRS", [])
    with pytest.raises(transcode.FfmpegNotFound):
        transcode.transcode("in.flac", "out.wav")


def test_build_command():
    cmd = transcode.build_command("/usr/bin/ffmpeg", "in.flac", "out.wav")
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "in.flac" in cmd and "out.wav" in cmd
    assert "-y" in cmd


def test_find_ffmpeg_in_common_dir(monkeypatch, tmp_path):
    # PATH 里找不到时，应能在常见安装目录中兜底找到（模拟 Finder 启动场景）
    monkeypatch.setattr(transcode.shutil, "which", lambda _: None)
    fake = tmp_path / "ffmpeg"
    fake.write_text("")
    fake.chmod(0o755)
    monkeypatch.setattr(transcode, "_COMMON_DIRS", [str(tmp_path)])
    assert transcode.find_ffmpeg() == str(fake)
