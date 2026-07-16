# tests/test_e2e.py
import shutil
import subprocess
import pytest
import io
from tests.conftest import build_ncm
from core.converter import convert_file
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from mutagen.flac import FLAC, Picture
from PIL import Image


def _png_cover(mode="RGBA"):
    buf = io.BytesIO()
    Image.new(mode, (16, 12), (10, 20, 30, 255) if mode == "RGBA" else (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


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


@pytest.mark.skipif(not _have_ffmpeg(), reason="需要 ffmpeg 生成 flac 测试样本")
def test_passthrough_flac_normalizes_existing_cover(tmp_path):
    src = tmp_path / "src.flac"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1", str(src)],
        check=True, capture_output=True,
    )
    flac = FLAC(src)
    flac["title"] = "T"
    flac["artist"] = "A"
    flac["album"] = "AL"
    pic = Picture()
    pic.type = 3
    pic.mime = "image/jpeg"
    pic.width = 0
    pic.height = 0
    pic.depth = 0
    pic.data = _png_cover()
    flac.add_picture(pic)
    flac.save()

    res = convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename", write_tags=True)

    assert res.status == "ok"
    out = FLAC(res.output_path)
    assert out["title"][0] == "T"
    assert out.pictures
    fixed = out.pictures[0]
    assert fixed.mime == "image/jpeg"
    assert (fixed.width, fixed.height, fixed.depth) == (16, 12, 24)
    assert Image.open(io.BytesIO(fixed.data)).format == "JPEG"


@pytest.mark.skipif(not _have_ffmpeg(), reason="需要 ffmpeg 生成 mp3 测试样本")
def test_passthrough_mp3_normalizes_existing_cover(tmp_path):
    src = tmp_path / "src.mp3"
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.1", str(src)],
        check=True, capture_output=True,
    )
    id3 = ID3(src)
    id3.add(TIT2(encoding=3, text="T"))
    id3.add(TPE1(encoding=3, text="A"))
    id3.add(TALB(encoding=3, text="AL"))
    id3.add(APIC(encoding=3, mime="image/jpg", type=3, desc="Cover", data=_png_cover("RGB")))
    id3.save(src)

    res = convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename", write_tags=True)

    assert res.status == "ok"
    out = ID3(res.output_path)
    assert out["TIT2"].text[0] == "T"
    apic = out.getall("APIC")[0]
    assert apic.mime == "image/jpeg"
    assert Image.open(io.BytesIO(apic.data)).format == "JPEG"
