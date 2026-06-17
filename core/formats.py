# core/formats.py
# 网易云 format 字段通常是 flac/mp3；全景声等特殊封装无法靠它判定，
# 故优先用音频内容的 magic 嗅探真实格式，识别不出再回落到声明值。
KNOWN_AUDIO = {"flac", "mp3"}


def detect_format(audio: bytes, declared: str = "") -> str:
    if audio[:4] == b"fLaC":
        return "flac"
    if audio[:3] == b"ID3":
        return "mp3"
    if len(audio) >= 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0:
        return "mp3"
    if audio[4:8] == b"ftyp":
        return "m4a"
    declared = (declared or "").lower()
    return declared if declared else "bin"


def is_special(fmt: str) -> bool:
    """非标准 flac/mp3（如全景声 m4a / 未知），需原样导出并提示。"""
    return fmt not in KNOWN_AUDIO
