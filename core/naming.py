# core/naming.py
import os

_ILLEGAL = '<>:"/\\|?*'
_FIELD_MAP = {"{标题}": "title", "{歌手}": "artists", "{专辑}": "album"}


def _sanitize(name: str) -> str:
    name = name.replace("..", "_")  # 防止路径注入
    for ch in _ILLEGAL:
        name = name.replace(ch, "_")
    return name.strip() or "untitled"


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
