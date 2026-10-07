# core/lyrics.py
import os
import json
import re


_TIMED_LINE = re.compile(r"^((?:\[\d{1,3}:\d{2}(?:\.\d{1,3})?\])+)(.*)$")
_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]")


def find_lrc(src: str):
    """同目录、同主名的 .lrc；找到返回路径，否则 None。"""
    candidate = os.path.splitext(src)[0] + ".lrc"
    return candidate if os.path.isfile(candidate) else None


def parse_lrc(text: str) -> str:
    """清理歌词：保留标准 [mm:ss.xx] 时间轴行；NetEase 的 JSON 行
    （{"t":..,"c":[{"tx":..}]}）提取其纯文本；其余行原样保留。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("{") and '"c"' in s:
            try:
                obj = json.loads(s)
                txt = "".join(part.get("tx", "") for part in obj.get("c", []))
                if txt.strip():
                    out.append(txt.rstrip())
                continue
            except (ValueError, AttributeError, TypeError):
                pass
        out.append(line.rstrip())
    return "\n".join(out)


def read_lyrics(src: str):
    """找到同名 .lrc 则读出并清理，返回歌词文本；否则 None。
    多编码兜底：UTF-8(含 BOM) → GBK → UTF-8 替换，避免非 UTF-8 文件读不出。"""
    path = find_lrc(src)
    if not path:
        return None
    raw = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                raw = f.read()
            break
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    if raw is None:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            return None
    return parse_lrc(raw)


def merge_lrc(original: str, translation: str) -> str:
    """按时间戳合并原文与译文，同一时间戳先写原文。"""
    headers = []
    lines = {}

    for source, keep_headers in ((original, True), (translation, False)):
        for line in parse_lrc(source or "").splitlines():
            match = _TIMED_LINE.match(line.strip())
            if not match:
                if keep_headers:
                    headers.append(line)
                continue
            for stamp in _TIMESTAMP.finditer(match.group(1)):
                minute, second, fraction = stamp.groups()
                millis = (int(minute) * 60 + int(second)) * 1000
                millis += int((fraction or "0").ljust(3, "0"))
                entry = lines.setdefault(millis, {"stamp": stamp.group(), "original": [], "translation": []})
                text = match.group(2).strip()
                if text:
                    entry["original" if keep_headers else "translation"].append(text)

    merged = list(headers)
    for millis in sorted(lines):
        entry = lines[millis]
        for text in entry["original"] + entry["translation"]:
            merged.append(entry["stamp"] + text)
    return "\n".join(merged)
