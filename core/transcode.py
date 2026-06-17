# core/transcode.py
import os
import shutil
import subprocess


class FfmpegNotFound(RuntimeError):
    pass


# GUI 程序从 Finder / Dock 启动时不会继承 shell 的 PATH（拿不到 /opt/homebrew/bin
# 等），导致 shutil.which 找不到 ffmpeg。这里额外探测常见安装位置作为兜底。
_COMMON_DIRS = [
    "/opt/homebrew/bin",   # Apple Silicon Homebrew
    "/usr/local/bin",      # Intel Homebrew / 手动安装
    "/usr/bin",
    "/opt/local/bin",      # MacPorts
]


def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    for d in _COMMON_DIRS:
        cand = os.path.join(d, "ffmpeg")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def build_command(ffmpeg: str, src: str, dst: str) -> list:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, dst]


def transcode(src: str, dst: str) -> None:
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise FfmpegNotFound("未找到 ffmpeg，无法转码")
    subprocess.run(build_command(ffmpeg, src, dst), check=True)
