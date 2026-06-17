# tests/test_metadata.py
from core.metadata import extract_tags


def test_extract_full():
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1], ["方文山", 2]], "album": "十一月的萧邦"}
    tags = extract_tags(meta)
    assert tags["title"] == "夜曲"
    assert tags["artists"] == ["周杰伦", "方文山"]
    assert tags["album"] == "十一月的萧邦"


def test_extract_missing_fields():
    tags = extract_tags({})
    assert tags == {"title": "", "artists": [], "album": ""}
