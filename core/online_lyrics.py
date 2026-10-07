"""Read-only NetEase song and public-playlist lyric lookup."""

import json
import os
import re
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from core.lyrics import merge_lrc
from core.naming import _sanitize


_API = "https://music.163.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 NCM-Converter", "Referer": "https://music.163.com/"}
_SHORT_HOST = "163cn.tv"
_SAVED_ID = re.compile(r"\[(\d+)\]\.lrc$", re.IGNORECASE)


def lyrics_download_dir():
    """Return the dedicated folder for standalone lyric downloads."""
    if os.name == "nt":
        return r"C:\LRC"
    return os.path.join(os.path.expanduser("~"), "Music", "LRC")


class LyricsLookupError(ValueError):
    """Invalid input or a public lookup that cannot be completed."""


def _official_host(host):
    return host == "music.163.com" or host.endswith(".music.163.com")


def _validate_url(url, allow_short=False):
    try:
        parsed = urlsplit(url)
        invalid = (parsed.scheme not in ("http", "https") or parsed.username or
                   parsed.password or parsed.port is not None)
    except ValueError as exc:
        raise LyricsLookupError("网址格式无效") from exc
    if invalid:
        raise LyricsLookupError("请输入网易云音乐的歌曲或歌单网址")
    host = (parsed.hostname or "").lower()
    if not _official_host(host) and not (allow_short and host == _SHORT_HOST):
        raise LyricsLookupError("仅支持网易云音乐的歌曲、歌单网址及官方分享短链")
    return parsed


class _OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl, allow_short=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_music_input(value, kind):
    """Return an ID from a number, official URL, or 163cn.tv share link."""
    value = value.strip()
    if kind not in ("song", "playlist"):
        raise LyricsLookupError("请选择歌曲或歌单")
    if value.isdecimal() and int(value) > 0:
        return int(value)
    parsed = _validate_url(value, allow_short=True)
    if (parsed.hostname or "").lower() == _SHORT_HOST:
        try:
            opener = build_opener(_OfficialRedirects())
            with opener.open(Request(value, headers=_HEADERS), timeout=8) as response:
                parsed = _validate_url(response.geturl())
        except (HTTPError, URLError, OSError) as exc:
            raise LyricsLookupError(f"分享链接解析失败：{exc}") from exc
    route = urlsplit(parsed.fragment) if parsed.fragment.startswith("/") else parsed
    segments = route.path.strip("/").split("/")
    if kind not in segments:
        raise LyricsLookupError("网址类型与所选歌曲／歌单不一致")
    ids = parse_qs(route.query).get("id", [])
    route_index = segments.index(kind)
    if not ids and len(segments) > route_index + 1:
        ids = [segments[route_index + 1]]
    if len(ids) != 1 or not ids[0].isdecimal() or int(ids[0]) <= 0:
        raise LyricsLookupError("网址中缺少有效的歌曲或歌单 ID")
    return int(ids[0])


class NeteaseLyricsClient:
    def _get_json(self, path, params):
        url = _API + path + "?" + urlencode(params)
        try:
            with urlopen(Request(url, headers=_HEADERS), timeout=8) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise LyricsLookupError("接口返回内容过大")
            data = json.loads(raw)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise LyricsLookupError(f"网易云请求失败：{exc}") from exc
        if not isinstance(data, dict):
            raise LyricsLookupError("网易云返回了无效数据")
        if data.get("code") != 200:
            raise LyricsLookupError(f"网易云返回错误：{data.get('code', '未知')}")
        return data

    def playlist_song_ids(self, playlist_id):
        try:
            data = self._get_json("/api/v6/playlist/detail", {"id": playlist_id})
        except LyricsLookupError as exc:
            raise LyricsLookupError(f"无法读取歌单；它可能不公开或已失效（{exc}）") from exc
        playlist = data.get("playlist")
        if not isinstance(playlist, dict):
            raise LyricsLookupError("无法读取歌单；它可能不公开或已失效")
        track_ids = playlist.get("trackIds")
        if not isinstance(track_ids, list):
            raise LyricsLookupError("歌单缺少完整的歌曲 ID 列表")
        ids = [int(item["id"]) for item in track_ids if isinstance(item, dict) and str(item.get("id", "")).isdecimal()]
        try:
            expected = int(playlist.get("trackCount") or 0)
        except (TypeError, ValueError) as exc:
            raise LyricsLookupError("歌单歌曲数量无效") from exc
        if len(ids) < expected:
            raise LyricsLookupError("歌单歌曲列表不完整，已停止下载")
        return list(dict.fromkeys(ids))

    def song_details(self, song_ids):
        details = {}
        for start in range(0, len(song_ids), 50):
            batch = song_ids[start:start + 50]
            data = self._get_json("/api/song/detail", {"ids": json.dumps(batch)})
            songs = data.get("songs") or []
            if not isinstance(songs, list):
                raise LyricsLookupError("网易云返回了无效歌曲资料")
            for song in songs:
                if isinstance(song, dict) and str(song.get("id", "")).isdecimal():
                    details[int(song["id"])] = song
        return details

    def song_lyrics(self, song_id):
        data = self._get_json("/api/song/lyric", {"id": song_id, "lv": -1, "tv": -1})
        original_data = data.get("lrc") or {}
        translated_data = data.get("tlyric") or {}
        if not isinstance(original_data, dict) or not isinstance(translated_data, dict):
            raise LyricsLookupError("网易云返回了无效歌词")
        original = original_data.get("lyric") or ""
        translated = translated_data.get("lyric") or ""
        if not isinstance(original, str) or not isinstance(translated, str):
            raise LyricsLookupError("网易云返回了无效歌词")
        return merge_lrc(original, translated)


@dataclass
class DownloadSummary:
    total: int = 0
    saved: int = 0
    skipped: int = 0
    missing: int = 0
    failed: int = 0
    cancelled: bool = False
    errors: list = field(default_factory=list)


def _filename(song_id, details):
    name = str(details.get("name") or song_id)
    artists = details.get("ar") or details.get("artists") or []
    artist = ", ".join(str(a.get("name") or "") for a in artists if isinstance(a, dict))
    prefix = _sanitize(f"{name} - {artist}" if artist else name)
    prefix = "".join("_" if ord(char) < 32 else char for char in prefix)
    prefix = prefix.encode("utf-8")[:180].decode("utf-8", errors="ignore").rstrip()
    return f"{prefix} [{song_id}].lrc"


def download_lyrics(kind, value, out_dir, progress=None, cancelled=None, client=None):
    """Save one LRC per song. Existing files remain untouched."""
    client = client or NeteaseLyricsClient()
    summary = DownloadSummary()
    if cancelled and cancelled():
        summary.cancelled = True
        return summary
    item_id = parse_music_input(value, kind)
    if cancelled and cancelled():
        summary.cancelled = True
        return summary
    ids = [item_id] if kind == "song" else client.playlist_song_ids(item_id)
    summary.total = len(ids)
    if cancelled and cancelled():
        summary.cancelled = True
        return summary
    try:
        details = client.song_details(ids)
    except LyricsLookupError:
        details = {}  # Song IDs still identify the lyrics; use them as filenames.
    os.makedirs(out_dir, exist_ok=True)
    existing_ids = set()
    with os.scandir(out_dir) as entries:
        for entry in entries:
            match = _SAVED_ID.search(entry.name)
            if entry.is_file() and match:
                existing_ids.add(int(match.group(1)))
    for index, song_id in enumerate(ids, 1):
        if cancelled and cancelled():
            summary.cancelled = True
            break
        path = os.path.join(out_dir, _filename(song_id, details.get(song_id, {})))
        if song_id in existing_ids or os.path.exists(path):
            summary.skipped += 1
            outcome = "已存在，跳过"
        else:
            created = False
            try:
                lyrics = client.song_lyrics(song_id)
                if lyrics:
                    try:
                        with open(path, "x", encoding="utf-8") as handle:
                            created = True
                            handle.write(lyrics)
                    except FileExistsError:
                        summary.skipped += 1
                        outcome = "已存在，跳过"
                    else:
                        summary.saved += 1
                        existing_ids.add(song_id)
                        outcome = "已保存"
                else:
                    summary.missing += 1
                    outcome = "无歌词"
            except (LyricsLookupError, OSError) as exc:
                summary.failed += 1
                summary.errors.append(f"{song_id}: {exc}")
                outcome = "失败"
                if created:
                    try:
                        os.remove(path)  # Remove only an incomplete file from this attempt.
                    except OSError:
                        pass
        if progress:
            progress(index, summary.total, f"{song_id}：{outcome}")
    return summary
