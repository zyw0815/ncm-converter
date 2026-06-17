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
