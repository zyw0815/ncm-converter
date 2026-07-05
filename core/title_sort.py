import os
import locale
import unicodedata

from core.metadata import extract_tags, read_audio_tags
from core.ncm import parse_ncm

_ZH_COLLATE_LOCALE = None


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
    return title.strip() or _filename_title_for_sort(path)


def _filename_title_for_sort(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0].strip()
    if " - " in stem:
        _artist, title = stem.split(" - ", 1)
        title = title.strip()
        if title:
            return title
    return stem


def title_sort_key(title: str):
    text = unicodedata.normalize("NFKC", (title or "").strip())
    first = _first_significant_char(text)
    group = _char_group(first)
    return (group, _group_sort_text(group, text), text)


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
    if _is_kana(ch):
        return 4
    if _is_cyrillic(ch):
        return 5
    if _is_cjk(ch):
        return 6
    if code < 128:
        return 0
    return 3


def _group_sort_text(group: int, text: str):
    if group == 2:
        return _latin_sort_key(text)
    if group == 6:
        return _cjk_sort_key(text)
    return text.casefold()


def _latin_sort_key(text: str):
    letters = [ch for ch in text if _is_latin(ch) and ch.isalpha()]
    first = letters[0] if letters else _first_significant_char(text)
    if letters and all(ch.isupper() for ch in letters):
        case_rank = 0
    elif first.isupper():
        case_rank = 1
    else:
        case_rank = 2
    return (case_rank, text.casefold(), text)


def _cjk_sort_key(text: str):
    loc = _zh_collate_locale()
    if not loc:
        return text
    current = locale.setlocale(locale.LC_COLLATE)
    try:
        locale.setlocale(locale.LC_COLLATE, loc)
        return locale.strxfrm(text)
    finally:
        locale.setlocale(locale.LC_COLLATE, current)


def _zh_collate_locale():
    global _ZH_COLLATE_LOCALE
    if _ZH_COLLATE_LOCALE is not None:
        return _ZH_COLLATE_LOCALE

    current = locale.setlocale(locale.LC_COLLATE)
    for loc in ("zh_CN.UTF-8", "zh_CN", "Chinese_China.936"):
        try:
            locale.setlocale(locale.LC_COLLATE, loc)
            _ZH_COLLATE_LOCALE = loc
            break
        except locale.Error:
            continue
    else:
        _ZH_COLLATE_LOCALE = ""
    locale.setlocale(locale.LC_COLLATE, current)
    return _ZH_COLLATE_LOCALE


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
