# core/ncm.py
import struct
import base64
import json
from Crypto.Cipher import AES

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


def xor_audio(rc4_key: bytes, data: bytes) -> bytes:
    box = build_keybox(rc4_key)
    out = bytearray(len(data))
    for i in range(len(data)):
        j = (i + 1) & 0xFF
        out[i] = data[i] ^ box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(out)


from dataclasses import dataclass


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
        raise NotNcmError("文件头不是 CTENFDAM，非 NCM 文件")
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
