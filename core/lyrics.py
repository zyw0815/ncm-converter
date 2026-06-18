# core/lyrics.py
import os
import json


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
