# core/transcode.py
import shutil
import subprocess


class FfmpegNotFound(RuntimeError):
    pass


def build_command(src: str, dst: str) -> list:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, dst]


def transcode(src: str, dst: str) -> None:
    if shutil.which("ffmpeg") is None:
        raise FfmpegNotFound("未找到 ffmpeg，无法转码")
    subprocess.run(build_command(src, dst), check=True)
