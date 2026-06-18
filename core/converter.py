# core/converter.py
import os
import shutil
from dataclasses import dataclass, field
from core.ncm import parse_ncm, NotNcmError
from core.formats import detect_format, is_special
from core.metadata import extract_tags, read_audio_tags, write_flac_tags, write_mp3_tags
from core.naming import render_name, resolve_conflict


@dataclass
class ConvertResult:
    source: str
    status: str = "ok"          # ok | skipped | failed
    reason: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    fmt: str = ""
    special: bool = False
    passthrough: bool = False   # True 表示原样导出（如 mp3），未做转码
    output_path: str = ""
    cover: bytes = field(default=b"", repr=False)


def _passthrough_mp3(src: str, out_dir: str, template: str, conflict: str) -> ConvertResult:
    """已是 mp3：不转码，按命名模板原样复制到输出目录（移动与否由上层 delete_src 决定）。"""
    res = ConvertResult(source=src, fmt="mp3", passthrough=True)
    tags, cover = read_audio_tags(src)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = cover

    os.makedirs(out_dir, exist_ok=True)
    rel = render_name(template, tags) if tags["title"] else os.path.splitext(os.path.basename(src))[0]
    target = os.path.join(out_dir, rel + ".mp3")
    os.makedirs(os.path.dirname(target), exist_ok=True)

    final = resolve_conflict(target, conflict)
    if final is None:
        res.status = "skipped"
        res.reason = "目标已存在，按设置跳过"
        return res

    if os.path.abspath(final) == os.path.abspath(src):
        # 源与目标同一文件，无需复制
        res.output_path = final
        res.reason = "MP3 原样导出（未转换）"
        return res

    try:
        shutil.copy2(src, final)
    except OSError as e:
        res.status = "failed"
        res.reason = f"输出目录无法写入：{e}"
        return res

    res.output_path = final
    res.reason = "MP3 原样导出（未转换）"
    return res


def convert_file(src: str, out_dir: str, template: str, conflict: str,
                 write_tags: bool = True) -> ConvertResult:
    if src.lower().endswith(".mp3"):
        return _passthrough_mp3(src, out_dir, template, conflict)
    res = ConvertResult(source=src)
    try:
        with open(src, "rb") as f:
            data = f.read()
    except OSError as e:
        res.status = "failed"
        res.reason = f"无法读取文件：{e}"
        return res

    try:
        content = parse_ncm(data)
    except NotNcmError:
        res.status = "skipped"
        res.reason = "非 NCM 文件，已跳过"
        return res
    except Exception as e:
        res.status = "failed"
        res.reason = f"文件损坏或格式异常：{e}"
        return res

    tags = extract_tags(content.metadata)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = content.cover

    fmt = detect_format(content.audio, content.metadata.get("format", ""))
    res.fmt = fmt
    res.special = is_special(fmt)

    os.makedirs(out_dir, exist_ok=True)
    rel = render_name(template, tags) if tags["title"] else os.path.splitext(os.path.basename(src))[0]
    target = os.path.join(out_dir, rel + "." + fmt)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    final = resolve_conflict(target, conflict)
    if final is None:
        res.status = "skipped"
        res.reason = "目标已存在，按设置跳过"
        return res

    try:
        with open(final, "wb") as f:
            f.write(content.audio)
    except OSError as e:
        res.status = "failed"
        res.reason = f"输出目录无法写入：{e}"
        return res

    res.output_path = final

    if write_tags and not res.special:
        try:
            if fmt == "flac":
                write_flac_tags(final, tags, content.cover)
            elif fmt == "mp3":
                write_mp3_tags(final, tags, content.cover)
        except Exception as e:
            res.reason = f"已导出，但标签写入失败：{e}"

    if res.special and not res.reason:
        res.reason = "特殊格式（如全景声），已原样导出"
    return res
