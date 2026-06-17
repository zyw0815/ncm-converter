# tests/test_task_model.py
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
