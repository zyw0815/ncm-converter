# core/converter.py
import os
import shutil
from dataclasses import dataclass, field
from core.registry import get_decryptor
from core.formats import is_special
from core.metadata import extract_tags, read_audio_tags, write_flac_tags, write_mp3_tags, write_lyrics
from core.naming import render_name, resolve_conflict
from core.lyrics import read_lyrics


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


def _maybe_embed_lyrics(src: str, out_path: str, fmt: str, res: "ConvertResult",
                        mode: str = "sidecar") -> None:
    """启用嵌入歌词：找到同名 .lrc 后，按 mode 处理并在状态里注明。
    mode='sidecar' 在输出旁生成同名 .lrc（外挂，兼容性好）；mode='embed' 写进音频标签（内嵌）。"""
    lyrics = read_lyrics(src)
    if not lyrics:
        res.reason = (res.reason + "；未找到歌词").lstrip("；") if res.reason else "未找到歌词"
        return
    try:
        if mode == "embed":
            write_lyrics(out_path, fmt, lyrics)
            note = "已嵌入歌词"
        else:
            sidecar = os.path.splitext(out_path)[0] + ".lrc"
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write(lyrics)
            note = "已生成歌词文件"
        res.reason = (res.reason + "；" + note).lstrip("；") if res.reason else note
    except Exception as e:
        res.status = "partial"
        res.reason = (res.reason + f"；歌词写入失败：{e}").lstrip("；") if res.reason else f"歌词写入失败：{e}"


def _passthrough(src: str, out_dir: str, template: str, conflict: str,
                 embed_lyrics: bool = False, lyrics_mode: str = "sidecar") -> ConvertResult:
    """已是可播放格式（mp3 / flac）：不转码，按命名模板原样复制到输出目录
    （移动与否由上层 delete_src 决定）。"""
    fmt = "flac" if src.lower().endswith(".flac") else "mp3"
    res = ConvertResult(source=src, fmt=fmt, passthrough=True)
    tags, cover = read_audio_tags(src)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = cover

    os.makedirs(out_dir, exist_ok=True)
    rel = render_name(template, tags) if tags["title"] else os.path.splitext(os.path.basename(src))[0]
    target = os.path.join(out_dir, rel + "." + fmt)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    final = resolve_conflict(target, conflict)
    if final is None:
        res.status = "skipped"
        res.reason = "目标已存在，按设置跳过"
        return res

    note = f"{fmt.upper()} 原样导出（未转换）"
    if os.path.abspath(final) == os.path.abspath(src):
        # 源与目标同一文件，无需复制
        res.output_path = final
        res.reason = note
        if embed_lyrics:
            _maybe_embed_lyrics(src, final, fmt, res, lyrics_mode)
        return res

    try:
        shutil.copy2(src, final)
    except OSError as e:
        res.status = "failed"
        res.reason = f"输出目录无法写入：{e}"
        return res

    res.output_path = final
    res.reason = note
    if embed_lyrics:
        _maybe_embed_lyrics(src, final, fmt, res, lyrics_mode)
    return res


def convert_file(src: str, out_dir: str, template: str, conflict: str,
                 write_tags: bool = True, embed_lyrics: bool = False,
                 lyrics_mode: str = "sidecar") -> ConvertResult:
    if src.lower().endswith((".mp3", ".flac")):
        return _passthrough(src, out_dir, template, conflict, embed_lyrics, lyrics_mode)
    res = ConvertResult(source=src)
    try:
        with open(src, "rb") as f:
            data = f.read()
    except OSError as e:
        res.status = "failed"
        res.reason = f"无法读取文件：{e}"
        return res

    dec = get_decryptor(src, data)
    if dec is None:
        res.status = "skipped"
        res.reason = "非 NCM 文件，已跳过"
        return res

    try:
        result = dec.decrypt(data)
    except Exception as e:
        res.status = "failed"
        res.reason = f"文件损坏或格式异常：{e}"
        return res

    metadata = result.metadata or {}
    tags = extract_tags(metadata)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = result.cover or b""

    fmt = result.fmt
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
            f.write(result.audio)
    except OSError as e:
        res.status = "failed"
        res.reason = f"输出目录无法写入：{e}"
        return res

    res.output_path = final

    if write_tags and not res.special:
        try:
            if fmt == "flac":
                write_flac_tags(final, tags, res.cover)
            elif fmt == "mp3":
                write_mp3_tags(final, tags, res.cover)
        except Exception as e:
            res.status = "partial"
            res.reason = f"标签写入失败：{e}"

    if embed_lyrics and not res.special and fmt in ("flac", "mp3"):
        _maybe_embed_lyrics(src, final, fmt, res, lyrics_mode)

    if res.special and not res.reason:
        res.reason = "特殊格式（如全景声），已原样导出"
    return res
