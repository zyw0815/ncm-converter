# gui/task_model.py
import os
from dataclasses import dataclass, field
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

HEADERS = ["标题", "歌手", "专辑", "格式", "状态"]
STATUS_TEXT = {"pending": "待转", "ok": "完成", "skipped": "跳过", "failed": "失败"}


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

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        r = self.rows[index.row()]
        col = index.column()
        if col == 0:
            return r.title or os.path.basename(r.source)
        if col == 1:
            return r.artist
        if col == 2:
            return r.album
        if col == 3:
            return r.fmt
        if col == 4:
            return STATUS_TEXT.get(r.status, r.status) + (f"：{r.reason}" if r.reason else "")
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

    def progress(self):
        done = sum(1 for r in self.rows if r.status in ("ok", "skipped", "failed"))
        return done, len(self.rows)

    def failed_indexes(self):
        return [i for i, r in enumerate(self.rows) if r.status == "failed"]

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()
