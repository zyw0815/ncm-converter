# core/metadata.py
from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError


def image_info(data: bytes):
    """从图片字节解析 (mime, width, height, depth_bits)。支持 JPEG / PNG，
    解析不出时返回 ('image/jpeg', 0, 0, 0)。零第三方依赖。"""
    if data[:2] == b"\xff\xd8":  # JPEG
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        i, n = 2, len(data)
        while i + 1 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                i += 2
                continue
            if marker == 0xD9:  # EOI
                break
            if marker in sof and i + 9 < n:
                precision = data[i + 4]
                height = (data[i + 5] << 8) | data[i + 6]
                width = (data[i + 7] << 8) | data[i + 8]
                comps = data[i + 9]
                return "image/jpeg", width, height, precision * comps
            if i + 4 > n:
                break
            seglen = (data[i + 2] << 8) | data[i + 3]
            i += 2 + seglen
        return "image/jpeg", 0, 0, 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        bit_depth = data[24]
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(data[25], 3)
        return "image/png", width, height, bit_depth * channels
    return "image/jpeg", 0, 0, 0


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
        mime, width, height, depth = image_info(cover)
        pic = Picture()
        pic.type = 3  # front cover
        pic.mime = mime
        pic.width = width
        pic.height = height
        pic.depth = depth
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
        mime, _w, _h, _d = image_info(cover)
        id3.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover))
    id3.save(path)
