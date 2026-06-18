import os
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from core.converter import convert_file
from core.transcode import transcode, FfmpegNotFound


class WorkerSignals(QObject):
    finished = pyqtSignal(int, object)  # row index, ConvertResult


class ConvertWorker(QRunnable):
    def __init__(self, index, src, out_dir, template, conflict,
                 to_wav=False, delete_src=False):
        super().__init__()
        self.index = index
        self.src = src
        self.out_dir = out_dir
        self.template = template
        self.conflict = conflict
        self.to_wav = to_wav
        self.delete_src = delete_src
        self.signals = WorkerSignals()

    def run(self):
        res = convert_file(self.src, self.out_dir, self.template, self.conflict)
        if res.status == "ok" and self.to_wav and not res.special and not res.passthrough:
            original = res.output_path
            try:
                wav = original.rsplit(".", 1)[0] + ".wav"
                transcode(original, wav)
                res.output_path = wav
                res.fmt = "wav"
                # 转码成功后删掉中间的原始格式文件，只保留 wav
                if os.path.abspath(wav) != os.path.abspath(original):
                    try:
                        os.remove(original)
                    except OSError:
                        pass
            except FfmpegNotFound:
                res.reason = "未找到 ffmpeg，已保留原始格式"
            except Exception as e:
                res.reason = f"转码失败，已保留原始格式：{e}"
        if res.status == "ok" and self.delete_src:
            try:
                os.remove(self.src)
            except OSError:
                pass
        self.signals.finished.emit(self.index, res)


from core.ncm import parse_ncm
from core.metadata import extract_tags, read_audio_tags


class PreviewSignals(QObject):
    done = pyqtSignal(int, dict, str, bytes)  # row index, tags, fmt, cover


class PreviewWorker(QRunnable):
    """轻量解析：只读元数据/封面/声明格式，不解密音频，用于转换前预览。"""
    def __init__(self, index, src):
        super().__init__()
        self.index = index
        self.src = src
        self.signals = PreviewSignals()

    def run(self):
        try:
            if self.src.lower().endswith(".mp3"):
                tags, cover = read_audio_tags(self.src)
                self.signals.done.emit(self.index, tags, "mp3", cover or b"")
                return
            with open(self.src, "rb") as f:
                data = f.read()
            content = parse_ncm(data, decode_audio=False)
            tags = extract_tags(content.metadata)
            fmt = content.metadata.get("format", "") or "?"
            self.signals.done.emit(self.index, tags, fmt, content.cover or b"")
        except Exception:
            self.signals.done.emit(self.index, {"title": "", "artists": [], "album": ""}, "?", b"")
