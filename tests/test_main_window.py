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
