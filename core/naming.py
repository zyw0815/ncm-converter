# core/naming.py
import os

_ILLEGAL = '<>:"/\\|?*'
_FIELD_MAP = {"{标题}": "title", "{歌手}": "artists", "{专辑}": "album"}


def _sanitize(name: str) -> str:
    name = name.replace("..", "_")  # 防止路径注入
    for ch in _ILLEGAL:
        name = name.replace(ch, "_")
    name = name.strip() or "untitled"
    # macOS NAME_MAX = 255 字节；文件名过长会导致 Errno 63 (File name too long)
    # 保留 30 字节给扩展名（如 .flac、.lrc）和冲突后缀（如 " (999)"）
    LIMIT = 220
    if len(name.encode("utf-8")) > LIMIT:
        # 逐字符截断到 LIMIT 字节以内
        encoded = name.encode("utf-8")[:LIMIT]
        name = encoded.decode("utf-8", errors="ignore")
    return name


def render_name(template: str, tags: dict) -> str:
    parts = template.split("/")
    rendered = []
    for part in parts:
        text = part
        for token, key in _FIELD_MAP.items():
            value = tags.get(key, "")
            if isinstance(value, list):
                value = ", ".join(value)
            text = text.replace(token, str(value))
        rendered.append(_sanitize(text))
    return os.sep.join(rendered)


def resolve_conflict(path: str, policy: str):
    """返回最终写入路径；policy='skip' 且已存在时返回 None。"""
    if not os.path.exists(path):
        return path
    if policy == "skip":
        return None
    if policy == "overwrite":
        return path
    # rename: song.flac -> song (1).flac -> song (2).flac ...
    root, ext = os.path.splitext(path)
    for i in range(1, 1000):
        candidate = f"{root} ({i}){ext}"
        if not os.path.exists(candidate):
            return candidate
    raise OSError(f"重命名超过上限：{path}")
