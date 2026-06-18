# gui/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QLineEdit, QComboBox, QCheckBox, QProgressBar, QFileDialog,
    QMessageBox, QHeaderView, QFrame, QAbstractItemView, QToolButton, QToolTip,
)
from PyQt6.QtCore import Qt, QThreadPool, QUrl, QTimer, QSize
from PyQt6.QtGui import QDesktopServices, QShortcut, QKeySequence, QCursor
from gui.task_model import QueueModel, Row
from gui.workers import ConvertWorker, PreviewWorker
from gui import theme
from core.transcode import find_ffmpeg
from core.lyrics import find_lrc

try:
    from version import __version__ as APP_VERSION
except Exception:
    APP_VERSION = ""

SUPPORTED_EXT = (".ncm", ".mp3", ".flac")
CONFLICT_MAP = {"重命名": "rename", "跳过": "skip", "覆盖": "overwrite"}


def scan_inputs(paths):
    found = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXT):
                        found.append(os.path.join(root, f))
        elif os.path.isfile(p) and p.lower().endswith(SUPPORTED_EXT):
            found.append(p)
    return found


class DropArea(QFrame):
    def __init__(self, on_paths):
        super().__init__()
        self.on_paths = on_paths
        self.setAcceptDrops(True)
        self.setObjectName("DropArea")
        self.setMinimumHeight(96)
        self.setProperty("hover", "false")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("把 NCM 文件或文件夹拖到这里",
                             alignment=Qt.AlignmentFlag.AlignCenter))

    def _set_hover(self, on):
        self.setProperty("hover", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if self.acceptDrops() and e.mimeData().hasUrls():
            self._set_hover(True)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._set_hover(False)

    def dropEvent(self, e):
        self._set_hover(False)
        self.on_paths([u.toLocalFile() for u in e.mimeData().urls()])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NCM 转换器 v{APP_VERSION}" if APP_VERSION else "NCM 转换器")
        self.resize(960, 660)
        self.pool = QThreadPool.globalInstance()
        # 限制并发数：避免占满 CPU、给界面线程留出余量（解密本身已大幅提速）
        self.pool.setMaxThreadCount(min(4, os.cpu_count() or 4))
        self.model = QueueModel()
        self.dark = False
        self.delete_confirmed = False
        self._base_dirs = {}
        self._running = 0

        self.spinner_timer = QTimer(self)
        self.spinner_timer.setInterval(95)
        self.spinner_timer.timeout.connect(self.model.advance_spinner)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # ---- top bar ----
        top = QHBoxLayout()
        title = QLabel("NCM 转换器")
        title.setObjectName("Title")
        top.addWidget(title)
        top.addStretch()
        self.theme_btn = QPushButton("🌙 深色")
        self.theme_btn.setObjectName("Theme")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme_btn)
        root.addLayout(top)

        # ---- drop area + pickers ----
        self.drop = DropArea(self.add_paths)
        root.addWidget(self.drop)
        pick = QHBoxLayout()
        pick.setSpacing(10)
        self.btn_files = QPushButton("选择文件")
        self.btn_files.clicked.connect(self.pick_files)
        self.btn_folder = QPushButton("选择文件夹")
        self.btn_folder.clicked.connect(self.pick_folder)
        pick.addWidget(self.btn_files)
        pick.addWidget(self.btn_folder)
        pick.addStretch()
        root.addLayout(pick)

        # ---- queue table ----
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setIconSize(QSize(34, 34))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for _key in (QKeySequence.StandardKey.Delete, QKeySequence(Qt.Key.Key_Backspace)):
            _sc = QShortcut(_key, self.table)
            _sc.activated.connect(self.remove_selected)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 「#」序号列保持窄
        hdr.setHighlightSections(False)
        root.addWidget(self.table, 1)

        # ---- output dir ----
        outrow = QHBoxLayout()
        outrow.setSpacing(10)
        lbl_out = QLabel("输出目录")
        lbl_out.setObjectName("FieldLabel")
        outrow.addWidget(lbl_out)
        self.out_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "Music", "ncm-out"))
        outrow.addWidget(self.out_edit, 1)
        self.btn_out = QPushButton("更改")
        self.btn_out.clicked.connect(self.pick_out)
        outrow.addWidget(self.btn_out)
        root.addLayout(outrow)

        # ---- naming + conflict on one compact row ----
        cfgrow = QHBoxLayout()
        cfgrow.setSpacing(8)
        lbl_name = QLabel("命名")
        lbl_name.setObjectName("FieldLabel")
        cfgrow.addWidget(lbl_name)
        self.tmpl = QComboBox()
        self.tmpl.setMinimumWidth(160)
        self.tmpl.addItems(["{歌手} - {标题}", "{标题}", "{专辑}/{标题}", "{歌手}/{专辑}/{标题}"])
        cfgrow.addWidget(self.tmpl)
        cfgrow.addWidget(self._help("输出文件如何命名。{歌手}{标题}{专辑} 会被替换；用 / 可建子文件夹，如「{专辑}/{标题}」。"))
        cfgrow.addSpacing(18)
        lbl_conf = QLabel("冲突")
        lbl_conf.setObjectName("FieldLabel")
        cfgrow.addWidget(lbl_conf)
        self.conflict = QComboBox()
        self.conflict.setMinimumWidth(110)
        self.conflict.addItems(["覆盖", "重命名", "跳过"])
        cfgrow.addWidget(self.conflict)
        cfgrow.addWidget(self._help("输出目录已存在同名文件时：覆盖＝替换旧文件；重命名＝自动加 (1)(2)；跳过＝不处理该文件。"))
        cfgrow.addStretch()
        root.addLayout(cfgrow)

        # ---- options (checkboxes, each with a ? help button) ----
        opt = QHBoxLayout()
        opt.setSpacing(6)
        self.keep_tree = QCheckBox("保留目录结构")
        self.embed_lrc = QCheckBox("嵌入歌词")
        self.lyrics_mode = QComboBox()
        self.lyrics_mode.addItems(["外嵌（推荐）", "内嵌"])
        self.lyrics_mode.setMinimumWidth(120)
        self.lyrics_mode.setEnabled(False)
        self.to_wav = QCheckBox("转 WAV")
        self.del_src = QCheckBox("删除原文件")

        def add_item(widget, tip, extra=None):
            opt.addWidget(widget)
            if extra is not None:
                opt.addSpacing(6)
                opt.addWidget(extra)
            opt.addSpacing(4)
            opt.addWidget(self._help(tip))
            opt.addSpacing(18)

        add_item(self.keep_tree, "选择文件夹批量转换时，在输出目录里复刻原来的子文件夹层级。")
        add_item(self.embed_lrc,
                 "把源文件同目录的同名 .lrc 歌词加入结果（WAV 不支持）。\n"
                 "· 外嵌（推荐）：在输出旁生成 .lrc 文件，兼容性好，几乎所有播放器都能显示。\n"
                 "· 内嵌：写进音频文件内部，单文件更整洁，但不少播放器不读、可能不显示。\n"
                 "若只想要单个文件又不在意歌词，建议直接不勾「嵌入歌词」。",
                 extra=self.lyrics_mode)
        add_item(self.to_wav, "把输出再转成 WAV（需要 ffmpeg）。WAV 兼容性强但体积大，且不含封面/标签/歌词，一般无需开启。")
        add_item(self.del_src, "转换成功后删除原始文件，并连同源文件旁的同名 .lrc 一起删除。默认关闭；首次勾选会二次确认。")
        opt.addStretch()
        root.addLayout(opt)

        # ---- progress on its own row ----
        self.bar = QProgressBar()
        root.addWidget(self.bar)

        # ---- action buttons, right-aligned ----
        bot = QHBoxLayout()
        bot.setSpacing(10)
        bot.addStretch()
        self.start_btn = QPushButton("开始转换")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self.start)
        self.retry_btn = QPushButton("重试失败")
        self.retry_btn.clicked.connect(self.retry_failed)
        self.remove_btn = QPushButton("移除所选")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.clear)
        self.open_btn = QPushButton("打开输出目录")
        self.open_btn.clicked.connect(self.open_out)
        for b in (self.start_btn, self.retry_btn, self.remove_btn, self.clear_btn, self.open_btn):
            bot.addWidget(b)
        root.addLayout(bot)

        # 转换时需要禁用的控件（主题切换不在内，转换中也能切）
        self._controls = [
            self.btn_files, self.btn_folder, self.out_edit, self.btn_out,
            self.tmpl, self.conflict, self.keep_tree, self.embed_lrc, self.lyrics_mode,
            self.to_wav, self.del_src,
            self.start_btn, self.retry_btn, self.remove_btn, self.clear_btn, self.open_btn,
        ]

        # 「转 WAV」依赖 ffmpeg：检测不到就置灰、不可勾选
        self._ffmpeg_ok = find_ffmpeg() is not None
        if self._ffmpeg_ok:
            self.to_wav.setToolTip("把输出转成 WAV（需要 ffmpeg）")
        else:
            self.to_wav.setChecked(False)
            self.to_wav.setEnabled(False)
            self.to_wav.setToolTip("未检测到 ffmpeg，无法转 WAV；安装 ffmpeg 后重启即可使用")

        self.embed_lrc.toggled.connect(self._on_embed_toggled)

        self.apply_theme()

    def _on_embed_toggled(self, checked=None):
        """勾选「嵌入歌词」后，给有同名 .lrc 的待转项在状态里标注「准备嵌入歌词」。"""
        if checked is None:
            checked = self.embed_lrc.isChecked()
        self.lyrics_mode.setEnabled(checked)  # 外嵌/内嵌选择仅在勾选嵌入歌词时可用
        for i, r in enumerate(self.model.rows):
            if r.status != "pending":
                continue
            if checked and find_lrc(r.source):
                if r.reason != "准备嵌入歌词":
                    self.model.update_row(i, reason="准备嵌入歌词")
            elif r.reason == "准备嵌入歌词":
                self.model.update_row(i, reason="")

    def _help(self, text):
        """生成一个「?」帮助按钮：悬停显示说明，点击也弹出说明气泡。"""
        b = QToolButton()
        b.setText("?")
        b.setObjectName("Help")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(text)
        b.clicked.connect(lambda: QToolTip.showText(QCursor.pos(), text, b))
        return b

    # ---------- adding files ----------
    def add_paths(self, paths):
        files = scan_inputs(paths)
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
        self._on_embed_toggled()  # 新加入的项若有歌词且已勾选嵌入，标注状态

    def on_preview(self, index, tags, fmt, cover):
        if self.model.rows[index].status != "pending":
            return
        self.model.update_row(index, title=tags.get("title", ""),
                              artist=", ".join(tags.get("artists", [])),
                              album=tags.get("album", ""), fmt=fmt, cover=cover)

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "音频 (*.ncm *.mp3 *.flac)")
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

    # ---------- conversion ----------
    def _out_dir_for(self, src):
        out = self.out_edit.text().strip()
        if self.keep_tree.isChecked() and src in self._base_dirs:
            rel = os.path.relpath(os.path.dirname(src), self._base_dirs[src])
            if rel and rel != ".":
                return os.path.join(out, rel)
        return out

    def set_busy(self, busy):
        for w in self._controls:
            w.setDisabled(busy)
        if not busy:
            if not self._ffmpeg_ok:
                self.to_wav.setDisabled(True)            # ffmpeg 不可用时始终保持禁用
            self.lyrics_mode.setEnabled(self.embed_lrc.isChecked())  # 仅勾选嵌入歌词时可用
        self.drop.setAcceptDrops(not busy)
        if busy:
            self.spinner_timer.start()
        else:
            self.spinner_timer.stop()

    def start(self):
        if self.del_src.isChecked() and not self.delete_confirmed:
            r = QMessageBox.question(self, "确认", "转换/导出成功后将删除原文件，确定？")
            if r != QMessageBox.StandardButton.Yes:
                return
            self.delete_confirmed = True
        pending = [i for i, r in enumerate(self.model.rows) if r.status == "pending"]
        if pending:
            self._run_indexes(pending)

    def _run_indexes(self, indexes):
        if not indexes:
            return
        self.set_busy(True)
        for i in indexes:
            self.model.set_status(i, "running")
            self._running += 1
            src = self.model.rows[i].source
            lyrics_mode = "embed" if self.lyrics_mode.currentText() == "内嵌" else "sidecar"
            w = ConvertWorker(i, src, self._out_dir_for(src), self.tmpl.currentText(),
                              CONFLICT_MAP[self.conflict.currentText()],
                              to_wav=self.to_wav.isChecked(), delete_src=self.del_src.isChecked(),
                              embed_lyrics=self.embed_lrc.isChecked(), lyrics_mode=lyrics_mode)
            w.signals.finished.connect(self.on_finished)
            self.pool.start(w)
        self.update_progress()

    def on_finished(self, index, res):
        cur = self.model.rows[index]
        self.model.update_row(index, title=res.title or cur.title, artist=res.artist or cur.artist,
                              album=res.album or cur.album, fmt=res.fmt or cur.fmt,
                              status=res.status, reason=res.reason)
        self._running -= 1
        self.update_progress()
        if self._running <= 0:
            self._running = 0
            self.set_busy(False)

    def retry_failed(self):
        failed = self.model.failed_indexes()
        if failed:
            self._run_indexes(failed)

    def update_progress(self):
        done, total = self.model.progress()
        self.bar.setMaximum(total or 1)
        self.bar.setValue(done)

    def remove_selected(self):
        if self._running:  # 转换进行中不允许改动队列
            return
        rows = {idx.row() for idx in self.table.selectionModel().selectedRows()}
        if not rows:
            return
        for src in self.model.remove_rows(rows):
            self._base_dirs.pop(src, None)
        self.update_progress()

    def clear(self):
        self.model.clear()
        self._base_dirs.clear()
        self.update_progress()

    def open_out(self):
        out = self.out_edit.text().strip()
        os.makedirs(out, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    # ---------- theme ----------
    def toggle_theme(self):
        self.dark = not self.dark
        self.theme_btn.setText("☀️ 浅色" if self.dark else "🌙 深色")
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(theme.DARK_QSS if self.dark else theme.LIGHT_QSS)
