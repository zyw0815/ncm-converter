# core/registry.py
import os
from core.decryptors.netease import NeteaseDecryptor

# 后续阶段在此追加:QQDecryptor / KugouDecryptor / KuwoDecryptor
DECRYPTORS: tuple = (
    NeteaseDecryptor,
)


def get_decryptor(path: str, data: bytes):
    """按扩展名找候选解密器,再用 magic 确认;都不匹配返回 None。"""
    ext = os.path.splitext(path)[1].lower()
    for dec in DECRYPTORS:
        if ext in dec.exts and dec.sniff(data):
            return dec
    return None


def supported_exts() -> tuple:
    """所有解密器支持的加密扩展名(不含直通的 .mp3/.flac)。"""
    out = []
    for dec in DECRYPTORS:
        out.extend(dec.exts)
    return tuple(out)
