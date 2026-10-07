# tests/test_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # noqa: E402

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


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
    assert w.embed_lrc.isChecked()
    assert w.lyrics_mode.currentData() == "embed"


def test_embed_status_hint(app, tmp_path):
    import gui.main_window as mw
    from gui.task_model import Row
    ncm = tmp_path / "song.ncm"
    ncm.write_bytes(b"x")
    (tmp_path / "song.lrc").write_text("[00:01.00]hi", encoding="utf-8")
    nolrc = tmp_path / "other.ncm"
    nolrc.write_bytes(b"x")
    w = mw.MainWindow()
    w.model.add_rows([Row(source=str(ncm)), Row(source=str(nolrc))])
    w.embed_lrc.setChecked(False)
    w.embed_lrc.setChecked(True)  # 触发 toggled
    assert w.model.rows[0].reason == "准备添加歌词"   # 有 .lrc
    assert w.model.rows[1].reason == ""              # 无 .lrc
    w.embed_lrc.setChecked(False)
    assert w.model.rows[0].reason == ""              # 取消后清除


def test_default_conversion_requests_embedded_lyrics(app, tmp_path):
    import gui.main_window as mw
    from gui.task_model import Row

    class Pool:
        def __init__(self):
            self.jobs = []

        def start(self, job):
            self.jobs.append(job)

    w = mw.MainWindow()
    w.pool = Pool()
    w.out_edit.setText(str(tmp_path))
    w.model.add_rows([Row(source=str(tmp_path / "song.ncm"))])
    w.start()

    assert len(w.pool.jobs) == 1
    assert w.pool.jobs[0].embed_lyrics
    assert w.pool.jobs[0].lyrics_mode == "embed"
    w.spinner_timer.stop()


def test_wav_conversion_keeps_matching_lrc(app, tmp_path, monkeypatch):
    from pathlib import Path
    import gui.workers as wk
    from tests.conftest import build_ncm

    src = tmp_path / "song.ncm"
    src.write_bytes(build_ncm(b"\xff\xfb\x90\x00" + b"\x00" * 64,
                              {"musicName": "Song", "format": "mp3"}))
    (tmp_path / "song.lrc").write_text("[00:01.00]local", encoding="utf-8")
    monkeypatch.setattr(wk, "transcode", lambda _src, dst: Path(dst).write_bytes(b"RIFF"))
    results = []
    worker = wk.ConvertWorker(0, str(src), str(tmp_path / "out"), "{标题}", "rename",
                              to_wav=True, embed_lyrics=True, lyrics_mode="embed")
    worker.signals.finished.connect(lambda _index, result: results.append(result))
    worker.run()

    assert results[0].status == "ok"
    assert (tmp_path / "out" / "Song.wav").exists()
    assert (tmp_path / "out" / "Song.lrc").read_text(encoding="utf-8") == "[00:01.00]local"
    assert not (tmp_path / "out" / "Song.mp3").exists()


def test_delete_src_also_removes_lrc(app, tmp_path):
    import gui.workers as wk
    src = tmp_path / "s.mp3"
    src.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 200)
    lrc = tmp_path / "s.lrc"
    lrc.write_text("[00:01.00]hi", encoding="utf-8")
    w = wk.ConvertWorker(0, str(src), str(tmp_path / "out"), "{标题}", "rename",
                         delete_src=True, embed_lyrics=False)  # 即便不嵌入也删 .lrc
    w.run()
    assert not src.exists()
    assert not lrc.exists()


def test_remove_selected_row(app):
    import gui.main_window as mw
    from gui.task_model import Row
    w = mw.MainWindow()
    w.model.add_rows([Row(source="a.ncm"), Row(source="b.ncm"), Row(source="c.ncm")])
    w.table.selectRow(1)
    w.remove_selected()
    assert w.model.rowCount() == 2
    assert [r.source for r in w.model.rows] == ["a.ncm", "c.ncm"]


def test_standalone_lyrics_start_and_cancel(app, tmp_path, monkeypatch):
    import gui.main_window as mw
    from core.online_lyrics import DownloadSummary

    class Pool:
        def __init__(self):
            self.jobs = []

        def start(self, job):
            self.jobs.append(job)

    lyric_dir = tmp_path / "lyrics"
    monkeypatch.setattr(mw, "lyrics_download_dir", lambda: str(lyric_dir))
    w = mw.MainWindow()
    w.pool = Pool()
    w.out_edit.setText(str(tmp_path / "audio"))
    w.lyrics_kind.setCurrentIndex(1)
    w.lyrics_input.setText("https://music.163.com/playlist?id=42")
    w.start_lyrics_download()
    assert len(w.pool.jobs) == 1
    assert w.pool.jobs[0].kind == "playlist"
    assert w.pool.jobs[0].out_dir == str(lyric_dir)
    assert str(lyric_dir) in w.lyrics_location.text()
    assert not w.lyrics_download_btn.isEnabled()
    w.cancel_lyrics_download()
    assert w.pool.jobs[0]._cancelled.is_set()
    w.on_lyrics_finished(DownloadSummary(total=2, saved=1, cancelled=True), "")
    assert w.lyrics_download_btn.isEnabled()
    assert "已取消" in w.lyrics_status.text()
