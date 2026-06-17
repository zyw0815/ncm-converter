# tests/test_scan.py
import os
from gui.main_window import scan_ncm

def test_scan_recursive(tmp_path):
    (tmp_path / "a.ncm").write_text("x")
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.NCM").write_text("x")
    (tmp_path / "c.mp3").write_text("x")
    found = scan_ncm([str(tmp_path)])
    names = sorted(os.path.basename(p) for p in found)
    assert names == ["a.ncm", "b.NCM"]

def test_scan_single_file(tmp_path):
    f = tmp_path / "x.ncm"; f.write_text("x")
    assert scan_ncm([str(f)]) == [str(f)]

def test_scan_ignores_non_ncm(tmp_path):
    f = tmp_path / "x.mp3"; f.write_text("x")
    assert scan_ncm([str(f)]) == []
