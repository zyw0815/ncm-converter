# tests/test_converter.py
import os
import core.converter as conv
from tests.conftest import build_ncm
from core.converter import convert_file


def test_convert_partial_on_tag_failure(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("nope")
    monkeypatch.setattr(conv, "write_flac_tags", boom)
    meta = {"musicName": "x", "artist": [["a", 1]], "album": "b", "format": "flac"}
    src = tmp_path / "s.ncm"
    src.write_bytes(build_ncm(b"fLaC" + b"\x00" * 64, meta))
    res = convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename", write_tags=True)
    assert res.status == "partial"          # 不是「完成」
    assert "标签写入失败" in res.reason
    assert os.path.exists(res.output_path)  # 音频仍已导出


def test_convert_mp3_passthrough_copies(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 200)  # mp3-ish bytes, no tags
    out = tmp_path / "out"
    res = convert_file(str(src), str(out), template="{歌手} - {标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "ok"
    assert res.passthrough is True
    assert res.fmt == "mp3"
    assert "未转换" in res.reason
    assert res.output_path.endswith(".mp3")
    assert os.path.exists(res.output_path)
    assert os.path.exists(str(src))            # 复制：源文件保留
    # 无可读标签时回落到原文件名
    assert os.path.basename(res.output_path) == "song.mp3"


def test_convert_mp3_passthrough_conflict_skip(tmp_path):
    src = tmp_path / "song.mp3"
    src.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 50)
    out = tmp_path / "out"
    convert_file(str(src), str(out), "{标题}", "rename", write_tags=False)
    res = convert_file(str(src), str(out), "{标题}", "skip", write_tags=False)
    assert res.status == "skipped"


def test_convert_flac_outputs_file(tmp_path):
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1]], "album": "十一月", "format": "flac"}
    audio = b"fLaC" + b"\x00" * 64
    src = tmp_path / "a.ncm"
    src.write_bytes(build_ncm(audio, meta))
    res = convert_file(str(src), str(tmp_path / "out"), template="{歌手} - {标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "ok"
    assert res.title == "夜曲"
    assert res.fmt == "flac"
    assert res.output_path.endswith("周杰伦 - 夜曲.flac")
    assert os.path.exists(res.output_path)
    with open(res.output_path, "rb") as f:
        assert f.read() == audio


def test_convert_non_ncm_skipped(tmp_path):
    src = tmp_path / "x.ncm"
    src.write_bytes(b"not an ncm")
    res = convert_file(str(src), str(tmp_path / "out"), template="{标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "skipped"
    assert "NCM" in res.reason


def test_convert_special_format_exported_as_is(tmp_path):
    meta = {"musicName": "atmos", "artist": [], "album": "", "format": ""}
    audio = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32
    src = tmp_path / "s.ncm"
    src.write_bytes(build_ncm(audio, meta))
    res = convert_file(str(src), str(tmp_path / "out"), template="{标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "ok"
    assert res.fmt == "m4a"
    assert res.special is True
    assert res.output_path.endswith(".m4a")
