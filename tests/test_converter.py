# tests/test_converter.py
import os
from tests.conftest import build_ncm
from core.converter import convert_file


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
