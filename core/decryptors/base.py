from __future__ import annotations

# core/decryptors/base.py
from dataclasses import dataclass


class DecryptError(Exception):
    """解密失败(文件损坏、格式异常等)。"""


class NotSupportedError(DecryptError):
    """识别出格式但当前无法解密(如尚未支持的最新加密变体)。"""


@dataclass
class DecryptResult:
    audio: bytes                 # 解密后的原始音频字节(必有)
    fmt: str                     # 内层真实格式:flac / mp3 / ogg / m4a / bin
    metadata: dict | None = None # 壳内自带元数据(仅网易云有,其余为 None)
    cover: bytes | None = None   # 壳内自带封面(仅网易云有,其余为 None)


class Decryptor:
    """所有平台解密器的统一接口。"""

    exts: tuple = ()

    @staticmethod
    def sniff(data: bytes) -> bool:
        raise NotImplementedError

    @staticmethod
    def decrypt(data: bytes) -> DecryptResult:
        raise NotImplementedError

    @classmethod
    def preview(cls, data: bytes) -> DecryptResult:
        """仅取元数据/封面/格式用于预览;默认走完整解密,子类可重写以加速。"""
        return cls.decrypt(data)
