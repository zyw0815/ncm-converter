# tests/test_formats.py
from core.formats import detect_format


def test_detect_flac():
    assert detect_format(b"fLaC\x00\x00\x00", "mp3") == "flac"


def test_detect_mp3_id3():
    assert detect_format(b"ID3\x04\x00", "") == "mp3"


def test_detect_mp3_frame_sync():
    assert detect_format(b"\xff\xfb\x90\x00", "") == "mp3"


def test_detect_m4a():
    assert detect_format(b"\x00\x00\x00\x20ftypM4A ", "") == "m4a"


def test_fallback_to_declared():
    assert detect_format(b"\x01\x02\x03\x04abcd", "flac") == "flac"


def test_fallback_unknown():
    assert detect_format(b"\x01\x02\x03\x04abcd", "") == "bin"
