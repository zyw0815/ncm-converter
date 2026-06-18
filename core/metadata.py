# core/metadata.py
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError


def extract_tags(meta: dict) -> dict:
    return {
        "title": meta.get("musicName", "") or "",
        "artists": [a[0] for a in meta.get("artist", []) if a],
        "album": meta.get("album", "") or "",
    }


def read_audio_tags(path: str):
    """从已有音频文件（如 mp3）读取标题/歌手/专辑与封面，返回 (tags, cover)。
    读不出时各字段为空，不抛异常。"""
    tags = {"title": "", "artists": [], "album": ""}
    cover = b""
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None and audio.tags:
            tags["title"] = (audio.tags.get("title") or [""])[0]
            tags["artists"] = list(audio.tags.get("artist") or [])
            tags["album"] = (audio.tags.get("album") or [""])[0]
    except Exception:
        pass
    try:
        id3 = ID3(path)
        for key in id3.keys():
            if key.startswith("APIC"):
                cover = id3[key].data
                break
    except Exception:
        pass
    return tags, cover


def write_flac_tags(path: str, tags: dict, cover: bytes) -> None:
    audio = FLAC(path)
    if tags["title"]:
        audio["title"] = tags["title"]
    if tags["artists"]:
        audio["artist"] = tags["artists"]
    if tags["album"]:
        audio["album"] = tags["album"]
    if cover:
        pic = Picture()
        pic.type = 3  # front cover
        pic.mime = "image/jpeg"
        pic.data = cover
        audio.clear_pictures()
        audio.add_picture(pic)
    audio.save()


def write_mp3_tags(path: str, tags: dict, cover: bytes) -> None:
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()
    if tags["title"]:
        id3.add(TIT2(encoding=3, text=tags["title"]))
    if tags["artists"]:
        id3.add(TPE1(encoding=3, text="/".join(tags["artists"])))
    if tags["album"]:
        id3.add(TALB(encoding=3, text=tags["album"]))
    if cover:
        id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
    id3.save(path)
