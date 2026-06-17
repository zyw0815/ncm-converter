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
        if res.status == "ok" and self.to_wav and not res.special:
            try:
                wav = res.output_path.rsplit(".", 1)[0] + ".wav"
                transcode(res.output_path, wav)
                res.output_path = wav
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
