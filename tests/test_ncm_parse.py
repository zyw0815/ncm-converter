# tests/test_ncm_parse.py
import pytest
from tests.conftest import build_ncm
from core.ncm import parse_ncm, NotNcmError


def test_build_ncm_smoke():
    data = build_ncm(b"AUDIO", {"musicName": "t"}, cover=b"IMG")
    assert data[:8] == b"CTENFDAM"
    assert len(data) > 50


def test_parse_roundtrip():
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1]], "album": "十一月的萧邦", "format": "flac"}
    data = build_ncm(b"RAW-AUDIO-BYTES", meta, cover=b"JPEGDATA", rc4_key=b"keykeykeykeykey1")
    result = parse_ncm(data)
    assert result.metadata["musicName"] == "夜曲"
    assert result.metadata["artist"][0][0] == "周杰伦"
    assert result.cover == b"JPEGDATA"
    assert result.audio == b"RAW-AUDIO-BYTES"


def test_parse_skip_audio():
    data = build_ncm(b"RAW", {"musicName": "t", "format": "flac"}, cover=b"IMG")
    r = parse_ncm(data, decode_audio=False)
    assert r.audio == b""
    assert r.metadata["musicName"] == "t"
    assert r.cover == b"IMG"


def test_parse_rejects_non_ncm():
    with pytest.raises(Exception):
        parse_ncm(b"this is not an ncm file at all")


def test_parse_rejects_empty_file():
    with pytest.raises(Exception):
        parse_ncm(b"")
