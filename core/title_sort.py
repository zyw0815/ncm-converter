import os
import unicodedata

from core.metadata import extract_tags, read_audio_tags
from core.ncm import parse_ncm


def display_title_for_sort(path: str) -> str:
    """Return the best available song title for import ordering."""
    try:
        low = path.lower()
        if low.endswith((".mp3", ".flac")):
            tags, _cover = read_audio_tags(path)
            title = tags.get("title", "")
        elif low.endswith(".ncm"):
            with open(path, "rb") as f:
                content = parse_ncm(f.read(), decode_audio=False)
            title = extract_tags(content.metadata).get("title", "")
        else:
            title = ""
    except Exception:
        title = ""
    return title.strip() or os.path.splitext(os.path.basename(path))[0]


def title_sort_key(title: str):
    text = unicodedata.normalize("NFKC", (title or "").strip())
    first = _first_significant_char(text)
    group = _char_group(first)
    return (group, text.casefold(), text)


def import_sort_key(path: str):
    return title_sort_key(display_title_for_sort(path))


def sorted_import_paths(paths):
    return sorted(paths, key=import_sort_key)


def _first_significant_char(text: str) -> str:
    for ch in text:
        if not ch.isspace():
            return ch
    return ""


def _char_group(ch: str) -> int:
    if not ch:
        return 7
    code = ord(ch)
    if ch.isdigit():
        return 1
    if _is_latin(ch):
        return 2
    if _is_cyrillic(ch):
        return 3
    if _is_kana(ch):
        return 5
    if _is_cjk(ch):
        return 6
    if code < 128:
        return 0
    return 4


def _is_latin(ch: str) -> bool:
    return "LATIN" in unicodedata.name(ch, "")


def _is_cyrillic(ch: str) -> bool:
    return "CYRILLIC" in unicodedata.name(ch, "")


def _is_kana(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3040 <= code <= 0x309F  # Hiragana
        or 0x30A0 <= code <= 0x30FF  # Katakana
        or 0x31F0 <= code <= 0x31FF  # Katakana phonetic extensions
    )


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
    )
