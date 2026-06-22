# core/ncm.py
import struct
import base64
import json
from dataclasses import dataclass
from Crypto.Cipher import AES

CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")  # 'hzHRAmso5kInbaxW'
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")  # "#14ljk_!\\]&0U<'("
MAGIC = b"CTENFDAM"


def _unpad(data: bytes) -> bytes:
    if not data:
        return data
    n = data[-1]
    if n == 0 or n > len(data):
        return data
    return data[:-n]


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
    """密钥流以 256 字节为周期（每字节只取决于 (i+1) mod 256），
    预计算这一个周期的 256 字节密钥垫。"""
    box = build_keybox(rc4_key)
    pad = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        pad[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(pad)


def xor_audio(rc4_key: bytes, data: bytes) -> bytes:
    """用周期性密钥垫 + numpy 位运算分块异或。numpy ufunc 计算时会释放 GIL，
    使批量转换时界面线程仍能流畅运行；结果与逐字节算法完全一致。"""
    if not data:
        return b""
    import numpy as np
    pad = np.frombuffer(keystream_pad(rc4_key), dtype=np.uint8)
    arr = np.frombuffer(data, dtype=np.uint8)
    out = np.empty_like(arr)
    chunk = 1 << 20  # 1 MiB，为 256 的整数倍，故每块都从相位 0 开始
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


def _read(data: bytes, offset: int, size: int, label: str) -> tuple:
    """从 data[offset:] 读取 size 字节，数据不足时抛出明确的 NotNcmError。"""
    if offset + size > len(data):
        raise NotNcmError(f"文件被截断：读取 {label} 需要 {size} 字节，"
                          f"但只剩 {len(data) - offset} 字节")
    return data[offset:offset + size]


def parse_ncm(data: bytes, decode_audio: bool = True) -> "NcmContent":
    if len(data) < 10:
        raise NotNcmError("文件太短，不是有效的 NCM 文件")
    if data[:8] != MAGIC:
        raise NotNcmError("文件头不是 CTENFDAM，非 NCM 文件")
    offset = 10  # 8 magic + 2 gap

    key_len = struct.unpack("<I", _read(data, offset, 4, "key_len"))[0]
    offset += 4
    key_data = bytes(b ^ 0x64 for b in _read(data, offset, key_len, "key_data"))
    offset += key_len
    key_dec = _unpad(AES.new(CORE_KEY, AES.MODE_ECB).decrypt(key_data))
    rc4_key = key_dec[17:]  # 去掉 'neteasecloudmusic'

    meta_len = struct.unpack("<I", _read(data, offset, 4, "meta_len"))[0]
    offset += 4
    if meta_len:
        meta_raw = bytes(b ^ 0x63 for b in _read(data, offset, meta_len, "meta_data"))
        offset += meta_len
        meta_b64 = base64.b64decode(meta_raw[22:])  # 去掉 "163 key(Don't modify):"
        meta_dec = _unpad(AES.new(META_KEY, AES.MODE_ECB).decrypt(meta_b64))
        metadata = json.loads(meta_dec[6:])  # 去掉 'music:'
    else:
        metadata = {}

    _read(data, offset, 4, "crc32")  # 校验完整性，值本身不用
    offset += 4  # CRC32
    _read(data, offset, 5, "gap")
    offset += 5  # gap
    img_len = struct.unpack("<I", _read(data, offset, 4, "img_len"))[0]
    offset += 4
    cover = _read(data, offset, img_len, "cover_image")
    offset += img_len

    audio = xor_audio(rc4_key, data[offset:]) if decode_audio else b""
    return NcmContent(rc4_key=rc4_key, metadata=metadata, cover=cover, audio=audio)
