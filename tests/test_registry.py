# tests/test_registry.py
from core.decryptors.base import DecryptResult, Decryptor, NotSupportedError


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
