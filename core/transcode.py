# core/transcode.py
import os
import shutil
import subprocess


class FfmpegNotFound(RuntimeError):
    pass


# 额外探测 GUI 程序（Finder / Dock 启动）可能漏掉的常见位置
_COMMON_DIRS = [
    "/opt/homebrew/bin",   # Apple Silicon Homebrew
    "/usr/local/bin",      # Intel Homebrew / 手动安装
    "/usr/bin",
    "/opt/local/bin",      # MacPorts
]


def find_ffmpeg():
    # 1) shutil.which 搜 PATH（含 conda env、用户自定义路径等）
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 2) 兜底：GUI 程序可能没继承 shell PATH，手动扫常见目录
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
