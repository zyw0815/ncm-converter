# tests/test_task_model.py
from PyQt6.QtCore import Qt
from gui.task_model import QueueModel, Row


def test_add_and_count():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm")])
    assert m.rowCount() == 2


def test_progress_summary():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm"), Row(source="c.ncm")])
    m.set_status(0, "ok")
    m.set_status(1, "failed")
    done, total = m.progress()
    assert (done, total) == (2, 3)


def test_failed_rows():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm")])
    m.set_status(1, "failed", "坏了")
    assert m.failed_indexes() == [1]


def test_row_number_column():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm", title="甲"), Row(source="b.ncm", title="乙")])
    assert m.columnCount() == 6
    assert m.data(m.index(0, 0), Qt.ItemDataRole.DisplayRole) == "1"
    assert m.data(m.index(1, 0), Qt.ItemDataRole.DisplayRole) == "2"
    # 标题移到第 1 列
    assert m.data(m.index(0, 1), Qt.ItemDataRole.DisplayRole) == "甲"


def test_remove_rows():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm"), Row(source="c.ncm")])
    removed = m.remove_rows([0, 2])
    assert set(removed) == {"a.ncm", "c.ncm"}
    assert m.rowCount() == 1
    assert m.rows[0].source == "b.ncm"
