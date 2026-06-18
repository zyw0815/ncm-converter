# tests/test_lyrics.py
from core.lyrics import parse_lrc, find_lrc, read_lyrics


def test_parse_lrc_cleans_json_and_keeps_timed_lines():
    raw = (
        '{"t":0,"c":[{"tx":"作词: "},{"tx":"张三"},{"tx":"/"},{"tx":"李四"}]}\n'
        "[00:21.64]Yeah, you could be the greatest\n"
        "\n"
        "plain line\n"
    )
    out = parse_lrc(raw)
    assert out.splitlines() == [
        "作词: 张三/李四",
        "[00:21.64]Yeah, you could be the greatest",
        "plain line",
    ]


def test_find_lrc(tmp_path):
    audio = tmp_path / "song.ncm"
    audio.write_bytes(b"x")
    assert find_lrc(str(audio)) is None
    (tmp_path / "song.lrc").write_text("[00:01.00]hi", encoding="utf-8")
    assert find_lrc(str(audio)) == str(tmp_path / "song.lrc")


def test_read_lyrics(tmp_path):
    (tmp_path / "a.ncm").write_bytes(b"x")
    (tmp_path / "a.lrc").write_text("[00:01.00]hello\n", encoding="utf-8")
    assert read_lyrics(str(tmp_path / "a.ncm")) == "[00:01.00]hello"


def test_write_lyrics_mp3(tmp_path):
    from core.metadata import write_lyrics
    from mutagen.id3 import ID3
    p = tmp_path / "x.mp3"
    p.write_bytes(b"")  # ID3 可写入空文件（仅写标签头）
    write_lyrics(str(p), "mp3", "line1\nline2")
    uslt = ID3(str(p)).getall("USLT")
    assert uslt and uslt[0].text == "line1\nline2"
