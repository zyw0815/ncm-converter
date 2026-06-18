# tests/test_metadata.py
from core.metadata import extract_tags, image_info


def test_image_info_jpeg():
    data = (b"\xff\xd8" + b"\xff\xc0\x00\x11\x08"
            + (480).to_bytes(2, "big") + (640).to_bytes(2, "big")
            + b"\x03" + b"\x00" * 20)
    mime, w, h, depth = image_info(data)
    assert mime == "image/jpeg"
    assert (w, h) == (640, 480)
    assert depth == 24  # 8-bit * 3 components


def test_image_info_png():
    data = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
            + (300).to_bytes(4, "big") + (200).to_bytes(4, "big")
            + bytes([8]) + bytes([6]) + b"\x00" * 10)
    mime, w, h, depth = image_info(data)
    assert mime == "image/png"
    assert (w, h) == (300, 200)
    assert depth == 32  # 8-bit * RGBA(4)


def test_image_info_unknown():
    assert image_info(b"not an image") == ("image/jpeg", 0, 0, 0)


def test_extract_full():
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1], ["方文山", 2]], "album": "十一月的萧邦"}
    tags = extract_tags(meta)
    assert tags["title"] == "夜曲"
    assert tags["artists"] == ["周杰伦", "方文山"]
    assert tags["album"] == "十一月的萧邦"


def test_extract_missing_fields():
    tags = extract_tags({})
    assert tags == {"title": "", "artists": [], "album": ""}
