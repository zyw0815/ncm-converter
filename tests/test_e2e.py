# tests/test_e2e.py
import shutil
import subprocess
import pytest
from tests.conftest import build_ncm
from core.converter import convert_file
from mutagen.id3 import ID3
from mutagen.flac import FLAC


def test_e2e_mp3_metadata_and_cover(tmp_path):
    """完整流水线（MP3 路径）：合成 NCM → 转换 → 读回标签与封面，无需 ffmpeg。"""
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1], ["方文山", 2]],
            "album": "十一月的萧邦", "format": "mp3"}
    audio = b"\xff\xfb\x90\x00" + b"\x00" * 4096          # MP3 帧同步头，detect_format -> mp3
    cover = b"\xff\xd8\xff\xe0" + b"COVER" + b"\x00" * 32  # 任意封面字节
    src = tmp_path / "song.ncm"
    src.write_bytes(build_ncm(audio, meta, cover=cover))

    res = convert_file(str(src), str(tmp_path / "out"),
                       template="{歌手} - {标题}", conflict="rename", write_tags=True)

    assert res.status == "ok"
    assert res.fmt == "mp3"
    assert res.output_path.endswith("周杰伦, 方文山 - 夜曲.mp3")

    id3 = ID3(res.output_path)
    assert id3["TIT2"].text[0] == "夜曲"
    assert id3["TPE1"].text[0] == "周杰伦/方文山"
    assert id3["TALB"].text[0] == "十一月的萧邦"
    apic = id3.getall("APIC")
    assert apic and apic[0].data == cover


def _have_ffmpeg():
    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _have_ffmpeg(), reason="需要 ffmpeg 生成 flac 测试样本")
def test_e2e_flac_metadata_and_cover(tmp_path):
    """完整流水线（FLAC 路径）：用 ffmpeg 生成真实 flac 样本，验证无损标签写回。"""
    flac_src = tmp_path / "src.flac"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1", str(flac_src)],
        check=True, capture_output=True,
    )
    audio = flac_src.read_bytes()
    meta = {"musicName": "T", "artist": [["A", 1]], "album": "AL", "format": "flac"}
    cover = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    src = tmp_path / "s.ncm"
    src.write_bytes(build_ncm(audio, meta, cover=cover))

    res = convert_file(str(src), str(tmp_path / "out"),
                       template="{标题}", conflict="rename", write_tags=True)

    assert res.status == "ok"
    assert res.fmt == "flac"
    f = FLAC(res.output_path)
    assert f["title"][0] == "T"
    assert f["artist"][0] == "A"
    assert f["album"][0] == "AL"
    assert f.pictures and f.pictures[0].data == cover
