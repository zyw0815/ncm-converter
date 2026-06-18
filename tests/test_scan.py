# tests/test_scan.py
import os
from gui.main_window import scan_inputs


def test_scan_recursive_ncm_and_mp3(tmp_path):
    (tmp_path / "a.ncm").write_text("x")
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.NCM").write_text("x")
    (tmp_path / "c.mp3").write_text("x")
    (tmp_path / "d.txt").write_text("x")
    found = scan_inputs([str(tmp_path)])
    names = sorted(os.path.basename(p) for p in found)
    assert names == ["a.ncm", "b.NCM", "c.mp3"]


def test_scan_single_file(tmp_path):
    f = tmp_path / "x.mp3"; f.write_text("x")
    assert scan_inputs([str(f)]) == [str(f)]


def test_scan_ignores_unsupported(tmp_path):
    (tmp_path / "x.flac").write_text("x")
    assert scan_inputs([str(tmp_path / "x.flac")]) == []
    assert scan_inputs([str(tmp_path)]) == []
