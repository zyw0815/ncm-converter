# tests/test_lyrics.py
import os
from core.lyrics import parse_lrc, find_lrc, read_lyrics
from core.converter import convert_file


def test_read_lyrics_gbk(tmp_path):
    (tmp_path / "a.ncm").write_bytes(b"x")
    (tmp_path / "a.lrc").write_bytes("[00:01.00]你好世界".encode("gbk"))
    assert "你好世界" in read_lyrics(str(tmp_path / "a.ncm"))


def _mk(tmp_path):
    src = tmp_path / "s.mp3"
    src.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 200)
    (tmp_path / "s.lrc").write_text("[00:01.00]hi", encoding="utf-8")
    return src


def test_lyrics_mode_sidecar_default(tmp_path):
    src = _mk(tmp_path)
    res = convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename", embed_lyrics=True)
    sidecar = os.path.splitext(res.output_path)[0] + ".lrc"
    assert os.path.exists(sidecar)                       # 外嵌：输出旁生成 .lrc
    assert open(sidecar, encoding="utf-8").read() == "[00:01.00]hi"
    assert "已生成歌词文件" in res.reason
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        uslt = ID3(res.output_path).getall("USLT")
    except ID3NoHeaderError:
        uslt = []
    assert not uslt                                       # 外嵌不写内嵌标签


def test_lyrics_mode_embed_only(tmp_path):
    src = _mk(tmp_path)
    res = convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename",
                       embed_lyrics=True, lyrics_mode="embed")
    sidecar = os.path.splitext(res.output_path)[0] + ".lrc"
    assert not os.path.exists(sidecar)                   # 内嵌：不生成外挂文件
    from mutagen.id3 import ID3
    assert ID3(res.output_path).getall("USLT")           # 内嵌写进标签
    assert "已嵌入歌词" in res.reason


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
