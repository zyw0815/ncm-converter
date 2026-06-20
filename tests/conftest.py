# tests/conftest.py
import struct
import base64
import json
from Crypto.Cipher import AES
from core.decryptors.netease import CORE_KEY, META_KEY, xor_audio


def _pad(data: bytes) -> bytes:
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad


def build_ncm(audio: bytes, metadata: dict, cover: bytes = b"",
              rc4_key: bytes = b"0123456789abcdef") -> bytes:
    """用与解密一致的固定密钥，可逆地构造一个合法 .ncm 字节串。"""
    out = bytearray()
    out += b"CTENFDAM"
    out += b"\x00\x00"  # 2 字节间隔
    # 密钥块
    key_plain = b"neteasecloudmusic" + rc4_key
    enc = AES.new(CORE_KEY, AES.MODE_ECB).encrypt(_pad(key_plain))
    key_data = bytes(b ^ 0x64 for b in enc)
    out += struct.pack("<I", len(key_data)) + key_data
    # 元数据块
    meta_plain = b"music:" + json.dumps(metadata).encode("utf-8")
    enc = AES.new(META_KEY, AES.MODE_ECB).encrypt(_pad(meta_plain))
    b64 = base64.b64encode(enc)
    meta_pref = b"163 key(Don't modify):" + b64
    meta_data = bytes(b ^ 0x63 for b in meta_pref)
    out += struct.pack("<I", len(meta_data)) + meta_data
    # CRC32(解析时跳过) + 5 字节间隔
    out += struct.pack("<I", 0)
    out += b"\x00" * 5
    # 封面
    out += struct.pack("<I", len(cover)) + cover
    # 音频(XOR 对称，构造=解密同一函数)
    out += xor_audio(rc4_key, audio)
    return bytes(out)


def test_build_ncm_smoke():
    data = build_ncm(b"AUDIO", {"musicName": "t"}, cover=b"IMG")
    assert data[:8] == b"CTENFDAM"
    assert len(data) > 50
