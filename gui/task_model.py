# gui/task_model.py
import os
from dataclasses import dataclass, field
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QColor

HEADERS = ["标题", "歌手", "专辑", "格式", "状态"]
STATUS_TEXT = {"pending": "待转", "running": "转换中", "ok": "完成", "skipped": "跳过", "failed": "失败"}
# 状态文字配色（深浅主题通用、对比都足够）
STATUS_COLOR = {
    "pending": "#9aa0a6",
    "running": "#3b82f6",
    "ok": "#1aa260",
    "skipped": "#c08a00",
    "failed": "#e05260",
}
# 转换中动效用的旋转帧（盲文点阵，平滑）
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@dataclass
class Row:
    source: str
    title: str = ""
    artist: str = ""
    album: str = ""
    fmt: str = ""
    status: str = "pending"
    reason: str = ""
    cover: bytes = field(default=b"", repr=False)


class QueueModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.spinner = SPINNER_FRAMES[0]

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self.rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return r.title or os.path.basename(r.source)
            if col == 1:
                return r.artist
            if col == 2:
                return r.album
            if col == 3:
                return r.fmt
            if col == 4:
                if r.status == "running":
                    return f"{self.spinner} 转换中"
                return STATUS_TEXT.get(r.status, r.status) + (f"：{r.reason}" if r.reason else "")
        if role == Qt.ItemDataRole.ForegroundRole and col == 4:
            return QColor(STATUS_COLOR.get(r.status, "#9aa0a6"))
        return None

    def add_rows(self, rows):
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        self.rows.extend(rows)
        self.endInsertRows()

    def update_row(self, i, **kw):
        row = self.rows[i]
        for k, v in kw.items():
            setattr(row, k, v)
        self.dataChanged.emit(self.index(i, 0), self.index(i, len(HEADERS) - 1))

    def set_status(self, i, status, reason=""):
        self.update_row(i, status=status, reason=reason)

    def advance_spinner(self):
        idx = (SPINNER_FRAMES.index(self.spinner) + 1) % len(SPINNER_FRAMES)
        self.spinner = SPINNER_FRAMES[idx]
        for i, r in enumerate(self.rows):
            if r.status == "running":
                self.dataChanged.emit(self.index(i, 4), self.index(i, 4))

    def progress(self):
        done = sum(1 for r in self.rows if r.status in ("ok", "skipped", "failed"))
        return done, len(self.rows)

    def has_running(self):
        return any(r.status == "running" for r in self.rows)

    def failed_indexes(self):
        return [i for i, r in enumerate(self.rows) if r.status == "failed"]

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()
