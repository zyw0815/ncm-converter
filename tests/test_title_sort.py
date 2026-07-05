from core.title_sort import sorted_import_paths, title_sort_key
from tests.conftest import build_ncm


def test_title_sort_category_order():
    titles = [
        "我记得",
        "あさひ",
        "†KRUSHDAFIGHT!†",
        "Умри если меня не любишь",
        "Bad Guy",
        "17",
        "#Lov3",
        "【FREE】lucky",
        "'Resident Evil",
    ]

    assert sorted(titles, key=title_sort_key) == [
        "#Lov3",
        "'Resident Evil",
        "17",
        "Bad Guy",
        "Умри если меня не любишь",
        "†KRUSHDAFIGHT!†",
        "【FREE】lucky",
        "あさひ",
        "我记得",
    ]


def test_sorted_import_paths_uses_ncm_title(tmp_path):
    chinese = tmp_path / "01.ncm"
    symbol = tmp_path / "02.ncm"
    latin = tmp_path / "03.ncm"
    chinese.write_bytes(build_ncm(b"audio", {"musicName": "我记得"}))
    symbol.write_bytes(build_ncm(b"audio", {"musicName": "#Lov3"}))
    latin.write_bytes(build_ncm(b"audio", {"musicName": "Bad Guy"}))

    assert sorted_import_paths([str(chinese), str(latin), str(symbol)]) == [
        str(symbol),
        str(latin),
        str(chinese),
    ]
