# tests/test_naming.py
import os
from core.naming import render_name, resolve_conflict


def test_render_template():
    tags = {"title": "夜曲", "artists": ["周杰伦"], "album": "十一月"}
    assert render_name("{歌手} - {标题}", tags) == "周杰伦 - 夜曲"
    assert render_name("{专辑}/{标题}", tags) == os.path.join("十一月", "夜曲")


def test_render_sanitizes_illegal_chars():
    tags = {"title": "a/b:c", "artists": ["x"], "album": ""}
    name = render_name("{标题}", tags)
    assert "/" not in os.path.basename(name)
    assert ":" not in name


def test_render_sanitizes_dotdot():
    """路径注入防护：标签含 '..' 不应生成上级目录。"""
    tags = {"title": "../../etc/passwd", "artists": [], "album": ""}
    name = render_name("{标题}", tags)
    assert ".." not in name


def test_conflict_skip(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    assert resolve_conflict(str(p), "skip") is None


def test_conflict_overwrite(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    assert resolve_conflict(str(p), "overwrite") == str(p)


def test_conflict_rename(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    out = resolve_conflict(str(p), "rename")
    assert out.endswith("song (1).flac")
