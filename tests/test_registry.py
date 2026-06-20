# tests/test_registry.py
from core.decryptors.base import DecryptResult, Decryptor


def test_decrypt_result_defaults():
    r = DecryptResult(audio=b"X", fmt="flac")
    assert r.audio == b"X"
    assert r.fmt == "flac"
    assert r.metadata is None
    assert r.cover is None


def test_base_decryptor_preview_defaults_to_decrypt():
    class Dummy(Decryptor):
        exts = (".dummy",)

        @staticmethod
        def sniff(data: bytes) -> bool:
            return data[:3] == b"DUM"

        @staticmethod
        def decrypt(data: bytes) -> DecryptResult:
            return DecryptResult(audio=b"AUDIO", fmt="mp3", metadata={"t": 1}, cover=b"C")

    r = Dummy.preview(b"DUMxxx")
    assert r.fmt == "mp3"
    assert r.metadata == {"t": 1}
    assert r.cover == b"C"


from tests.conftest import build_ncm


def test_netease_decrypt_roundtrip():
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaC\x00\x01\x02audio", {"musicName": "歌", "format": "flac"}, cover=b"IMG")
    assert NeteaseDecryptor.sniff(data) is True
    r = NeteaseDecryptor.decrypt(data)
    assert r.audio == b"fLaC\x00\x01\x02audio"
    assert r.fmt == "flac"
    assert r.metadata["musicName"] == "歌"
    assert r.cover == b"IMG"


def test_netease_preview_skips_audio():
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaCaudio", {"musicName": "歌"}, cover=b"IMG")
    r = NeteaseDecryptor.preview(data)
    assert r.audio == b""
    assert r.metadata["musicName"] == "歌"
    assert r.cover == b"IMG"


def test_netease_sniff_rejects_non_ncm():
    from core.decryptors.netease import NeteaseDecryptor
    assert NeteaseDecryptor.sniff(b"NOTNCM..") is False


def test_registry_picks_netease_by_ext_and_magic():
    from core.registry import get_decryptor
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaCaudio", {"musicName": "歌"})
    dec = get_decryptor("song.ncm", data)
    assert dec is NeteaseDecryptor


def test_registry_returns_none_for_unknown_ext():
    from core.registry import get_decryptor
    assert get_decryptor("song.xyz", b"whatever") is None


def test_registry_returns_none_when_magic_mismatch():
    from core.registry import get_decryptor
    assert get_decryptor("fake.ncm", b"NOTNCM12") is None


def test_supported_exts_includes_ncm():
    from core.registry import supported_exts
    assert ".ncm" in supported_exts()
