# gui/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QLineEdit, QComboBox, QCheckBox, QProgressBar, QFileDialog,
    QMessageBox, QHeaderView, QFrame,
)
from PyQt6.QtCore import Qt, QThreadPool, QUrl
from PyQt6.QtGui import QDesktopServices
from gui.task_model import QueueModel, Row
from gui.workers import ConvertWorker, PreviewWorker
from gui import theme

NCM_EXT = ".ncm"
CONFLICT_MAP = {"重命名": "rename", "跳过": "skip", "覆盖": "overwrite"}


def scan_ncm(paths):
    found = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(NCM_EXT):
                        found.append(os.path.join(root, f))
        elif os.path.isfile(p) and p.lower().endswith(NCM_EXT):
            found.append(p)
    return found


class DropArea(QFrame):
    def __init__(self, on_paths):
        super().__init__()
        self.on_paths = on_paths
        self.setAcceptDrops(True)
        self.setObjectName("DropArea")
        self.setMinimumHeight(90)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("把 NCM 文件或文件夹拖到这里", alignment=Qt.AlignmentFlag.AlignCenter))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.on_paths([u.toLocalFile() for u in e.mimeData().urls()])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM 转换器")
        self.resize(840, 580)
        self.pool = QThreadPool.globalInstance()
        self.model = QueueModel()
        self.dark = False
        self.delete_confirmed = False
        self._base_dirs = {}

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("<b>NCM 转换器</b>"))
        top.addStretch()
        self.theme_btn = QPushButton("🌙 深色")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme_btn)
        root.addLayout(top)

        root.addWidget(DropArea(self.add_paths))
        pick = QHBoxLayout()
        b1 = QPushButton("选择文件"); b1.clicked.connect(self.pick_files)
        b2 = QPushButton("选择文件夹"); b2.clicked.connect(self.pick_folder)
        pick.addWidget(b1); pick.addWidget(b2); pick.addStretch()
        root.addLayout(pick)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        outrow = QHBoxLayout()
        outrow.addWidget(QLabel("输出目录:"))
        self.out_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "Music", "ncm-out"))
        outrow.addWidget(self.out_edit, 1)
        ob = QPushButton("更改"); ob.clicked.connect(self.pick_out)
        outrow.addWidget(ob)
        root.addLayout(outrow)

        opt = QHBoxLayout()
        opt.addWidget(QLabel("命名:"))
        self.tmpl = QComboBox(); self.tmpl.setEditable(True)
        self.tmpl.addItems(["{歌手} - {标题}", "{标题}", "{专辑}/{标题}", "{歌手}/{专辑}/{标题}"])
        opt.addWidget(self.tmpl)
        opt.addWidget(QLabel("冲突:"))
        self.conflict = QComboBox(); self.conflict.addItems(["重命名", "跳过", "覆盖"])
        opt.addWidget(self.conflict)
        self.keep_tree = QCheckBox("保留目录结构")
        self.to_wav = QCheckBox("转 WAV")
        self.del_src = QCheckBox("删除原 NCM")
        opt.addWidget(self.keep_tree); opt.addWidget(self.to_wav); opt.addWidget(self.del_src)
        opt.addStretch()
        root.addLayout(opt)

        bot = QHBoxLayout()
        self.bar = QProgressBar()
        bot.addWidget(self.bar, 1)
        self.start_btn = QPushButton("开始转换"); self.start_btn.clicked.connect(self.start)
        self.retry_btn = QPushButton("重试失败"); self.retry_btn.clicked.connect(self.retry_failed)
        self.clear_btn = QPushButton("清空"); self.clear_btn.clicked.connect(self.clear)
        self.open_btn = QPushButton("打开输出目录"); self.open_btn.clicked.connect(self.open_out)
        for b in (self.start_btn, self.retry_btn, self.clear_btn, self.open_btn):
            bot.addWidget(b)
        root.addLayout(bot)

        self.apply_theme()

    def add_paths(self, paths):
        files = scan_ncm(paths)
        existing = {r.source for r in self.model.rows}
        new = [f for f in files if f not in existing]
        if not new:
            return
        start = self.model.rowCount()
        self.model.add_rows([Row(source=f) for f in new])
        for p in paths:
            if os.path.isdir(p):
                ap = os.path.abspath(p)
                for f in new:
                    if os.path.abspath(f).startswith(ap):
                        self._base_dirs[f] = ap
        for offset, f in enumerate(new):
            w = PreviewWorker(start + offset, f)
            w.signals.done.connect(self.on_preview)
            self.pool.start(w)

    def on_preview(self, index, tags, fmt, cover):
        self.model.update_row(index, title=tags.get("title", ""),
                              artist=", ".join(tags.get("artists", [])),
                              album=tags.get("album", ""), fmt=fmt, cover=cover)

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择 NCM 文件", "", "NCM (*.ncm)")
        if files:
            self.add_paths(files)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            self.add_paths([d])

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.out_edit.setText(d)

    def _out_dir_for(self, src):
        out = self.out_edit.text().strip()
        if self.keep_tree.isChecked() and src in self._base_dirs:
            rel = os.path.relpath(os.path.dirname(src), self._base_dirs[src])
            if rel and rel != ".":
                return os.path.join(out, rel)
        return out

    def start(self):
        if self.del_src.isChecked() and not self.delete_confirmed:
            r = QMessageBox.question(self, "确认", "转换成功后将删除原 NCM 文件，确定？")
            if r != QMessageBox.StandardButton.Yes:
                return
            self.delete_confirmed = True
        pending = [i for i, r in enumerate(self.model.rows) if r.status == "pending"]
        if pending:
            self._run_indexes(pending)

    def _run_indexes(self, indexes):
        for i in indexes:
            self.model.set_status(i, "pending")
            src = self.model.rows[i].source
            w = ConvertWorker(i, src, self._out_dir_for(src), self.tmpl.currentText(),
                              CONFLICT_MAP[self.conflict.currentText()],
                              to_wav=self.to_wav.isChecked(), delete_src=self.del_src.isChecked())
            w.signals.finished.connect(self.on_finished)
            self.pool.start(w)
        self.update_progress()

    def on_finished(self, index, res):
        cur = self.model.rows[index]
        self.model.update_row(index, title=res.title or cur.title, artist=res.artist or cur.artist,
                              album=res.album or cur.album, fmt=res.fmt or cur.fmt,
                              status=res.status, reason=res.reason)
        self.update_progress()

    def retry_failed(self):
        failed = self.model.failed_indexes()
        if failed:
            self._run_indexes(failed)

    def update_progress(self):
        done, total = self.model.progress()
        self.bar.setMaximum(total or 1)
        self.bar.setValue(done)

    def clear(self):
        self.model.clear()
        self._base_dirs.clear()
        self.update_progress()

    def open_out(self):
        out = self.out_edit.text().strip()
        os.makedirs(out, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def toggle_theme(self):
        self.dark = not self.dark
        self.theme_btn.setText("☀️ 浅色" if self.dark else "🌙 深色")
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(theme.DARK_QSS if self.dark else theme.LIGHT_QSS)
