# tests/test_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_wav_disabled_without_ffmpeg(app, monkeypatch):
    import gui.main_window as mw
    monkeypatch.setattr(mw, "find_ffmpeg", lambda: None)
    w = mw.MainWindow()
    assert w.to_wav.isEnabled() is False
    assert w.to_wav.isChecked() is False
    # 转换结束恢复控件后，仍应保持禁用
    w.set_busy(True)
    w.set_busy(False)
    assert w.to_wav.isEnabled() is False


def test_wav_enabled_with_ffmpeg(app, monkeypatch):
    import gui.main_window as mw
    monkeypatch.setattr(mw, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    w = mw.MainWindow()
    assert w.to_wav.isEnabled() is True


def test_default_conflict_is_overwrite(app):
    import gui.main_window as mw
    w = mw.MainWindow()
    assert w.conflict.currentText() == "覆盖"
    assert w.conflict.itemText(0) == "覆盖"


def test_embed_status_hint(app, tmp_path):
    import gui.main_window as mw
    from gui.task_model import Row
    ncm = tmp_path / "song.ncm"; ncm.write_bytes(b"x")
    (tmp_path / "song.lrc").write_text("[00:01.00]hi", encoding="utf-8")
    nolrc = tmp_path / "other.ncm"; nolrc.write_bytes(b"x")
    w = mw.MainWindow()
    w.model.add_rows([Row(source=str(ncm)), Row(source=str(nolrc))])
    w.embed_lrc.setChecked(True)  # 触发 toggled
    assert w.model.rows[0].reason == "准备嵌入歌词"   # 有 .lrc
    assert w.model.rows[1].reason == ""              # 无 .lrc
    w.embed_lrc.setChecked(False)
    assert w.model.rows[0].reason == ""              # 取消后清除


def test_remove_selected_row(app):
    import gui.main_window as mw
    from gui.task_model import Row
    w = mw.MainWindow()
    w.model.add_rows([Row(source="a.ncm"), Row(source="b.ncm"), Row(source="c.ncm")])
    w.table.selectRow(1)
    w.remove_selected()
    assert w.model.rowCount() == 2
    assert [r.source for r in w.model.rows] == ["a.ncm", "c.ncm"]
