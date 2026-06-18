# gui/task_model.py
import os
from dataclasses import dataclass, field
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QColor, QPixmap, QIcon

HEADERS = ["#", "标题", "歌手", "专辑", "格式", "状态"]
STATUS_TEXT = {"pending": "待转", "running": "转换中", "ok": "完成",
               "partial": "部分完成", "skipped": "跳过", "failed": "失败"}
# 状态文字配色（深浅主题通用、对比都足够）
STATUS_COLOR = {
    "pending": "#9aa0a6",
    "running": "#3b82f6",
    "ok": "#1aa260",
    "partial": "#d98324",
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
    icon: object = field(default=None, repr=False, compare=False)  # 缓存的封面 QIcon


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
                return str(index.row() + 1)
            if col == 1:
                return r.title or os.path.basename(r.source)
            if col == 2:
                return r.artist
            if col == 3:
                return r.album
            if col == 4:
                return r.fmt
            if col == 5:
                if r.status == "running":
                    return f"{self.spinner} 转换中"
                return STATUS_TEXT.get(r.status, r.status) + (f"：{r.reason}" if r.reason else "")
        if role == Qt.ItemDataRole.TextAlignmentRole and col == 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole and col == 5:
            return QColor(STATUS_COLOR.get(r.status, "#9aa0a6"))
        if role == Qt.ItemDataRole.DecorationRole and col == 1 and r.cover:
            if r.icon is None:
                pix = QPixmap()
                pix.loadFromData(r.cover)
                r.icon = QIcon(pix) if not pix.isNull() else QIcon()
            return r.icon
        return None

    def add_rows(self, rows):
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        self.rows.extend(rows)
        self.endInsertRows()

    def update_row(self, i, **kw):
        row = self.rows[i]
        if "cover" in kw:
            row.icon = None  # 封面变了，丢弃旧缓存
        for k, v in kw.items():
            setattr(row, k, v)
        self.dataChanged.emit(self.index(i, 0), self.index(i, len(HEADERS) - 1))

    def set_status(self, i, status, reason=""):
        self.update_row(i, status=status, reason=reason)

    def advance_spinner(self):
        idx = (SPINNER_FRAMES.index(self.spinner) + 1) % len(SPINNER_FRAMES)
        self.spinner = SPINNER_FRAMES[idx]
        status_col = len(HEADERS) - 1
        for i, r in enumerate(self.rows):
            if r.status == "running":
                self.dataChanged.emit(self.index(i, status_col), self.index(i, status_col))

    def progress(self):
        done = sum(1 for r in self.rows if r.status in ("ok", "partial", "skipped", "failed"))
        return done, len(self.rows)

    def has_running(self):
        return any(r.status == "running" for r in self.rows)

    def failed_indexes(self):
        return [i for i, r in enumerate(self.rows) if r.status == "failed"]

    def remove_rows(self, indexes):
        """移除指定下标的行（从大到小删，避免下标错位）。返回被移除行的 source 列表。"""
        removed = []
        for i in sorted(set(indexes), reverse=True):
            if 0 <= i < len(self.rows):
                self.beginRemoveRows(QModelIndex(), i, i)
                removed.append(self.rows.pop(i).source)
                self.endRemoveRows()
        return removed

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()
