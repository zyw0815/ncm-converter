# core/decryptors/netease.py
import struct
import base64
import json
from dataclasses import dataclass
from Crypto.Cipher import AES

from core.formats import detect_format
from core.decryptors.base import DecryptResult, Decryptor

CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")  # 'hzHRAmso5kInbaxW'
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")  # "#14ljk_!\\]&0U<'("
MAGIC = b"CTENFDAM"


def _unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


def build_keybox(rc4_key: bytes) -> bytes:
    box = bytearray(range(256))
    last_byte = 0
    key_offset = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last_byte + rc4_key[key_offset]) & 0xFF
        key_offset = (key_offset + 1) % len(rc4_key)
        box[i] = box[c]
        box[c] = swap
        last_byte = c
    return bytes(box)


def keystream_pad(rc4_key: bytes) -> bytes:
    """密钥流以 256 字节为周期(每字节只取决于 (i+1) mod 256),
    预计算这一个周期的 256 字节密钥垫。"""
    box = build_keybox(rc4_key)
    pad = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        pad[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(pad)


def xor_audio(rc4_key: bytes, data: bytes) -> bytes:
    """用周期性密钥垫 + numpy 位运算分块异或。numpy ufunc 计算时会释放 GIL,
    使批量转换时界面线程仍能流畅运行;结果与逐字节算法完全一致。"""
    if not data:
        return b""
    import numpy as np
    pad = np.frombuffer(keystream_pad(rc4_key), dtype=np.uint8)
    arr = np.frombuffer(data, dtype=np.uint8)
    out = np.empty_like(arr)
    chunk = 1 << 20  # 1 MiB,为 256 的整数倍,故每块都从相位 0 开始
    for off in range(0, arr.size, chunk):
        block = arr[off:off + chunk]
        np.bitwise_xor(block, np.resize(pad, block.size), out=out[off:off + chunk])
    return out.tobytes()


class NotNcmError(ValueError):
    pass


@dataclass
class NcmContent:
    rc4_key: bytes
    metadata: dict
    cover: bytes
    audio: bytes  # 已解密的原始音频字节


def parse_ncm(data: bytes, decode_audio: bool = True) -> "NcmContent":
    if data[:8] != MAGIC:
        raise NotNcmError("文件头不是 CTENFDAM,非 NCM 文件")
    offset = 10  # 8 magic + 2 gap

    key_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    key_data = bytes(b ^ 0x64 for b in data[offset:offset + key_len])
    offset += key_len
    key_dec = _unpad(AES.new(CORE_KEY, AES.MODE_ECB).decrypt(key_data))
    rc4_key = key_dec[17:]  # 去掉 'neteasecloudmusic'

    meta_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    if meta_len:
        meta_raw = bytes(b ^ 0x63 for b in data[offset:offset + meta_len])
        offset += meta_len
        meta_b64 = base64.b64decode(meta_raw[22:])  # 去掉 "163 key(Don't modify):"
        meta_dec = _unpad(AES.new(META_KEY, AES.MODE_ECB).decrypt(meta_b64))
        metadata = json.loads(meta_dec[6:])  # 去掉 'music:'
    else:
        metadata = {}

    offset += 4  # CRC32
    offset += 5  # gap
    img_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    cover = data[offset:offset + img_len]
    offset += img_len

    audio = xor_audio(rc4_key, data[offset:]) if decode_audio else b""
    return NcmContent(rc4_key=rc4_key, metadata=metadata, cover=cover, audio=audio)


class NeteaseDecryptor(Decryptor):
    exts = (".ncm",)

    @staticmethod
    def sniff(data: bytes) -> bool:
        return data[:8] == MAGIC

    @staticmethod
    def decrypt(data: bytes) -> DecryptResult:
        c = parse_ncm(data, decode_audio=True)
        fmt = detect_format(c.audio, c.metadata.get("format", ""))
        return DecryptResult(audio=c.audio, fmt=fmt, metadata=c.metadata, cover=c.cover)

    @classmethod
    def preview(cls, data: bytes) -> DecryptResult:
        c = parse_ncm(data, decode_audio=False)
        fmt = c.metadata.get("format", "") or "?"
        return DecryptResult(audio=b"", fmt=fmt, metadata=c.metadata, cover=c.cover)
