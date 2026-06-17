# tests/test_ncm_parse.py
from tests.conftest import build_ncm
from core.ncm import parse_ncm


def test_parse_roundtrip():
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1]], "album": "十一月的萧邦", "format": "flac"}
    data = build_ncm(b"RAW-AUDIO-BYTES", meta, cover=b"JPEGDATA", rc4_key=b"keykeykeykeykey1")
    result = parse_ncm(data)
    assert result.metadata["musicName"] == "夜曲"
    assert result.metadata["artist"][0][0] == "周杰伦"
    assert result.cover == b"JPEGDATA"
    assert result.audio == b"RAW-AUDIO-BYTES"


def test_parse_skip_audio():
    from tests.conftest import build_ncm
    data = build_ncm(b"RAW", {"musicName": "t", "format": "flac"}, cover=b"IMG")
    r = parse_ncm(data, decode_audio=False)
    assert r.audio == b""
    assert r.metadata["musicName"] == "t"   # metadata still parsed
    assert r.cover == b"IMG"


def test_parse_rejects_non_ncm():
    import pytest
    from core.ncm import NotNcmError
    with pytest.raises(NotNcmError):
        parse_ncm(b"this is not an ncm file at all")
