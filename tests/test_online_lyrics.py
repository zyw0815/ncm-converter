from urllib.request import Request

import pytest

import core.converter as converter
import core.online_lyrics as online
from core.lyrics import merge_lrc
from tests.conftest import build_ncm


@pytest.mark.parametrize("value,kind,expected", [
    ("12345", "song", 12345),
    ("https://music.163.com/song?id=12345", "song", 12345),
    ("https://music.163.com/#/playlist?id=67890&userid=1", "playlist", 67890),
    ("https://y.music.163.com/m/playlist?id=67890", "playlist", 67890),
    ("https://music.163.com/playlist/67890/123456", "playlist", 67890),
])
def test_parse_music_input(value, kind, expected):
    assert online.parse_music_input(value, kind) == expected


def test_parse_music_input_rejects_wrong_site_or_type():
    with pytest.raises(online.LyricsLookupError):
        online.parse_music_input("https://example.com/playlist?id=1", "playlist")
    with pytest.raises(online.LyricsLookupError):
        online.parse_music_input("https://music.163.com/song?id=1", "playlist")


def test_parse_share_short_link(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def geturl(self):
            return "https://music.163.com/#/playlist?id=456"

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(online, "build_opener", lambda *_: Opener())
    assert online.parse_music_input("https://163cn.tv/example", "playlist") == 456


def test_share_redirect_rejects_non_netease_host():
    handler = online._OfficialRedirects()
    with pytest.raises(online.LyricsLookupError):
        handler.redirect_request(Request("https://163cn.tv/x"), None, 302, "", {},
                                 "http://127.0.0.1/internal")


def test_merge_lrc_keeps_original_before_translation():
    original = "[ti:Test]\n[00:02.00]二\n[00:01.0]一\n"
    translated = "[00:01.00]one\n[00:02.00]two\n"
    assert merge_lrc(original, translated).splitlines() == [
        "[ti:Test]", "[00:01.0]一", "[00:01.0]one",
        "[00:02.00]二", "[00:02.00]two",
    ]


def test_client_combines_original_and_translation(monkeypatch):
    client = online.NeteaseLyricsClient()
    monkeypatch.setattr(client, "_get_json", lambda *_: {
        "lrc": {"lyric": "[00:01.00]原文"},
        "tlyric": {"lyric": "[00:01.00]translation"},
    })
    assert client.song_lyrics(123).splitlines() == [
        "[00:01.00]原文", "[00:01.00]translation",
    ]


def test_playlist_uses_all_track_ids(monkeypatch):
    client = online.NeteaseLyricsClient()
    monkeypatch.setattr(client, "_get_json", lambda *_: {
        "playlist": {"trackCount": 3, "tracks": [{"id": 1}],
                     "trackIds": [{"id": 1}, {"id": 2}, {"id": 3}]}
    })
    assert client.playlist_song_ids(42) == [1, 2, 3]


def test_incomplete_playlist_is_an_error(monkeypatch):
    client = online.NeteaseLyricsClient()
    monkeypatch.setattr(client, "_get_json", lambda *_: {
        "playlist": {"trackCount": 3, "trackIds": [{"id": 1}]}
    })
    with pytest.raises(online.LyricsLookupError, match="不完整"):
        client.playlist_song_ids(42)


def test_inaccessible_playlist_mentions_visibility(monkeypatch):
    client = online.NeteaseLyricsClient()

    def unavailable(*_):
        raise online.LyricsLookupError("网易云返回错误：404")

    monkeypatch.setattr(client, "_get_json", unavailable)
    with pytest.raises(online.LyricsLookupError, match="可能不公开"):
        client.playlist_song_ids(42)


def test_download_reports_saved_existing_missing_and_failed(tmp_path):
    class Client:
        def playlist_song_ids(self, _id):
            return [1, 2, 3, 4]

        def song_details(self, ids):
            return {i: {"name": "Song", "ar": [{"name": "Artist"}]} for i in ids}

        def song_lyrics(self, song_id):
            if song_id == 2:
                return ""
            if song_id == 3:
                raise online.LyricsLookupError("请求超时")
            return f"[00:01.00]song {song_id}"

    existing = tmp_path / "Previous title [1].lrc"
    existing.write_text("local", encoding="utf-8")
    progress = []
    result = online.download_lyrics("playlist", "42", str(tmp_path),
                                    progress=lambda *args: progress.append(args), client=Client())
    assert (result.total, result.saved, result.skipped, result.missing, result.failed) == (4, 1, 1, 1, 1)
    assert existing.read_text(encoding="utf-8") == "local"
    assert (tmp_path / "Song - Artist [4].lrc").read_text(encoding="utf-8") == "[00:01.00]song 4"
    assert len(progress) == 4
    assert "3:" in result.errors[0]


def test_download_can_cancel_between_songs(tmp_path):
    class Client:
        def playlist_song_ids(self, _id):
            return [1, 2]

        def song_details(self, _ids):
            return {}

        def song_lyrics(self, _id):
            return "[00:01.00]line"

    progress = []
    result = online.download_lyrics("playlist", "42", str(tmp_path),
                                    progress=lambda *args: progress.append(args),
                                    cancelled=lambda: bool(progress), client=Client())
    assert result.cancelled
    assert result.saved == 1
    assert len(list(tmp_path.glob("*.lrc"))) == 1


def test_download_cancelled_before_lookup_does_not_call_client(tmp_path):
    class Client:
        def song_details(self, _ids):
            raise AssertionError("cancelled work should not query song details")

    result = online.download_lyrics("song", "123", str(tmp_path),
                                    cancelled=lambda: True, client=Client())
    assert result.cancelled
    assert result.total == 0


def test_convert_prefers_local_lrc_over_online(tmp_path, monkeypatch):
    class Client:
        def song_lyrics(self, _id):
            raise AssertionError("local lyrics should prevent network lookup")

    monkeypatch.setattr(converter, "NeteaseLyricsClient", Client)
    src = tmp_path / "song.ncm"
    src.write_bytes(build_ncm(b"\xff\xfb\x90\x00" + b"\x00" * 64,
                              {"musicName": "Song", "format": "mp3", "musicId": 123}))
    (tmp_path / "song.lrc").write_text("[00:01.00]local", encoding="utf-8")
    result = converter.convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename",
                                    write_tags=False, embed_lyrics=True)
    assert result.status == "ok"
    from mutagen.id3 import ID3
    assert ID3(result.output_path).getall("USLT")[0].text == "[00:01.00]local"
    assert not (tmp_path / "out" / "Song.lrc").exists()

    sidecar = converter.convert_file(str(src), str(tmp_path / "sidecar"), "{标题}", "rename",
                                     write_tags=False, embed_lyrics=True, lyrics_mode="sidecar")
    assert sidecar.status == "ok"
    assert (tmp_path / "sidecar" / "Song.lrc").read_text(encoding="utf-8") == "[00:01.00]local"


def test_convert_fetches_online_lrc_by_embedded_song_id(tmp_path, monkeypatch):
    seen = []

    class Client:
        def song_lyrics(self, song_id):
            seen.append(song_id)
            return "[00:01.00]online"

    monkeypatch.setattr(converter, "NeteaseLyricsClient", Client)
    src = tmp_path / "song.ncm"
    src.write_bytes(build_ncm(b"\xff\xfb\x90\x00" + b"\x00" * 64,
                              {"musicName": "Song", "format": "mp3", "musicId": 123}))
    result = converter.convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename",
                                    write_tags=False, embed_lyrics=True)
    assert result.status == "ok"
    assert seen == [123]
    from mutagen.id3 import ID3
    assert ID3(result.output_path).getall("USLT")[0].text == "[00:01.00]online"
    assert not (tmp_path / "out" / "Song.lrc").exists()


def test_convert_online_failure_keeps_audio(tmp_path, monkeypatch):
    class Client:
        def song_lyrics(self, _id):
            raise online.LyricsLookupError("请求超时")

    monkeypatch.setattr(converter, "NeteaseLyricsClient", Client)
    src = tmp_path / "song.ncm"
    src.write_bytes(build_ncm(b"\xff\xfb\x90\x00" + b"\x00" * 64,
                              {"musicName": "Song", "format": "mp3", "musicId": 123}))
    result = converter.convert_file(str(src), str(tmp_path / "out"), "{标题}", "rename",
                                    write_tags=False, embed_lyrics=True)
    assert result.status == "ok"
    assert "在线歌词获取失败" in result.reason
    assert (tmp_path / "out" / "Song.mp3").exists()
    assert not (tmp_path / "out" / "Song.lrc").exists()
