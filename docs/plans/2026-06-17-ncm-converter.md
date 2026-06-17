# NCM 转换器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 subagent-driven-development(推荐)或 executing-plans 逐任务实现本计划。步骤用 `- [ ]` 复选框跟踪。

**Goal:** 跨平台 GUI 工具，把网易云 `.ncm` 还原为原始 flac/mp3（保留标题/歌手/专辑/封面），可批量、可选 ffmpeg 转码。

**Architecture:** `core/` 纯逻辑（解密/格式判定/标签/编排），不依赖 GUI，用合成 NCM 做 TDD；`gui/` 用 PyQt6 + QThreadPool 调度 core。

**Tech Stack:** Python 3.9（conda `work` 环境）、PyQt6、mutagen、pycryptodome、可选 ffmpeg、PyInstaller。

**环境约定：所有命令在 conda `work` 环境执行（`conda run -n work …`），不要用 base / 系统 Python。**

**测试边界（诚实声明）：** core 用「合成 NCM」做 round-trip 单测，证明解析与构造互逆、字段映射正确，全程离线无版权样本。但合成数据无法证明与网易云真实文件字节级一致，也无法在无编码器时生成合法 flac/mp3 来测 mutagen 写标签。因此**真实 .ncm 端到端 + 标签写入由 Task 13 手动验证**。

---

### Task 0: 脚手架与依赖

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `core/__init__.py`（空）
- Create: `gui/__init__.py`（空）
- Create: `tests/__init__.py`（空）

- [ ] **Step 1: 写 requirements.txt**

```
PyQt6==6.7.1
mutagen==1.47.0
pycryptodome==3.20.0
pytest==8.2.0
```

- [ ] **Step 2: 写 pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 3: 建空包文件**

建 `core/__init__.py`、`gui/__init__.py`、`tests/__init__.py`，内容均为空。

- [ ] **Step 4: 在 work 环境装依赖**

Run: `conda run -n work pip install -r requirements.txt`
Expected: 成功安装，无报错。

- [ ] **Step 5: 验证关键库可导入**

Run: `conda run -n work python -c "import PyQt6, mutagen, Crypto; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini core/ gui/ tests/
git commit -m "chore: project scaffolding and dependencies"
```

---

### Task 1: NCM 加解密原语

**Files:**
- Create: `core/ncm.py`
- Test: `tests/test_ncm_primitives.py`

- [ ] **Step 1: 写失败测试（keybox 与音频 XOR 对称性）**

```python
# tests/test_ncm_primitives.py
from core.ncm import build_keybox, xor_audio

def test_keybox_is_256_permutation():
    box = build_keybox(b"any-rc4-key-1234")
    assert len(box) == 256
    assert sorted(box) == list(range(256))

def test_xor_audio_is_symmetric():
    key = b"some-rc4-keymaterial"
    plain = bytes(range(256)) * 4
    enc = xor_audio(key, plain)
    dec = xor_audio(key, enc)
    assert dec == plain
    assert enc != plain
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_ncm_primitives.py -v`
Expected: FAIL（`ImportError: cannot import name 'build_keybox'`）

- [ ] **Step 3: 实现 core/ncm.py 的原语部分**

```python
# core/ncm.py
import struct
import base64
import json
from Crypto.Cipher import AES

CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")  # 'hzHRAmso5kInbaxW'
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")  # "#14ljk_!\\]&0U<'("
MAGIC = b"CTENFDAM"


def _unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


def build_keybox(rc4_key: bytes) -> bytes:
    box = bytearray(range(256))
    last_byte = 0
    key_offset = 0
    for i in range(256):
        swap = box[i]
        c = (swap + last_byte + rc4_key[key_offset]) & 0xFF
        key_offset = (key_offset + 1) % len(rc4_key)
        box[i] = box[c]
        box[c] = swap
        last_byte = c
    return bytes(box)


def xor_audio(rc4_key: bytes, data: bytes) -> bytes:
    box = build_keybox(rc4_key)
    out = bytearray(len(data))
    for i in range(len(data)):
        j = (i + 1) & 0xFF
        out[i] = data[i] ^ box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(out)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_ncm_primitives.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add core/ncm.py tests/test_ncm_primitives.py
git commit -m "feat(core): add NCM RC4 keybox and audio XOR primitives"
```

---

### Task 2: 合成 NCM 构造器（测试基础设施）

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: 写 conftest 构造器 + 自检测试**

```python
# tests/conftest.py
import struct
import base64
import json
from Crypto.Cipher import AES
from core.ncm import CORE_KEY, META_KEY, xor_audio


def _pad(data: bytes) -> bytes:
    pad = 16 - len(data) % 16
    return data + bytes([pad]) * pad


def build_ncm(audio: bytes, metadata: dict, cover: bytes = b"",
              rc4_key: bytes = b"0123456789abcdef") -> bytes:
    """用与解密一致的固定密钥，可逆地构造一个合法 .ncm 字节串。"""
    out = bytearray()
    out += b"CTENFDAM"
    out += b"\x00\x00"  # 2 字节间隔
    # 密钥块
    key_plain = b"neteasecloudmusic" + rc4_key
    enc = AES.new(CORE_KEY, AES.MODE_ECB).encrypt(_pad(key_plain))
    key_data = bytes(b ^ 0x64 for b in enc)
    out += struct.pack("<I", len(key_data)) + key_data
    # 元数据块
    meta_plain = b"music:" + json.dumps(metadata).encode("utf-8")
    enc = AES.new(META_KEY, AES.MODE_ECB).encrypt(_pad(meta_plain))
    b64 = base64.b64encode(enc)
    meta_pref = b"163 key(Don't modify):" + b64
    meta_data = bytes(b ^ 0x63 for b in meta_pref)
    out += struct.pack("<I", len(meta_data)) + meta_data
    # CRC32(解析时跳过) + 5 字节间隔
    out += struct.pack("<I", 0)
    out += b"\x00" * 5
    # 封面
    out += struct.pack("<I", len(cover)) + cover
    # 音频(XOR 对称，构造=解密同一函数)
    out += xor_audio(rc4_key, audio)
    return bytes(out)


def test_build_ncm_smoke():
    data = build_ncm(b"AUDIO", {"musicName": "t"}, cover=b"IMG")
    assert data[:8] == b"CTENFDAM"
    assert len(data) > 50
```

- [ ] **Step 2: 跑自检测试确认通过**

Run: `conda run -n work pytest tests/conftest.py -v`
Expected: PASS（test_build_ncm_smoke）

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add synthetic NCM builder fixture"
```

---

### Task 3: NCM 解析（头/密钥/元数据/封面/音频）

**Files:**
- Modify: `core/ncm.py`（新增 `parse_ncm`）
- Test: `tests/test_ncm_parse.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ncm_parse.py
from tests.conftest import build_ncm
from core.ncm import parse_ncm

def test_parse_roundtrip():
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1]], "album": "十一月的萧邦", "format": "flac"}
    data = build_ncm(b"RAW-AUDIO-BYTES", meta, cover=b"JPEGDATA", rc4_key=b"keykeykeykeykey1")
    result = parse_ncm(data)
    assert result.metadata["musicName"] == "夜曲"
    assert result.metadata["artist"][0][0] == "周杰伦"
    assert result.cover == b"JPEGDATA"
    assert result.audio == b"RAW-AUDIO-BYTES"  # 已解密回原始音频

def test_parse_rejects_non_ncm():
    import pytest
    from core.ncm import NotNcmError
    with pytest.raises(NotNcmError):
        parse_ncm(b"this is not an ncm file at all")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_ncm_parse.py -v`
Expected: FAIL（`cannot import name 'parse_ncm'`）

- [ ] **Step 3: 实现 parse_ncm**

在 `core/ncm.py` 末尾追加：

```python
from dataclasses import dataclass


class NotNcmError(ValueError):
    pass


@dataclass
class NcmContent:
    rc4_key: bytes
    metadata: dict
    cover: bytes
    audio: bytes  # 已解密的原始音频字节


def parse_ncm(data: bytes) -> "NcmContent":
    if data[:8] != MAGIC:
        raise NotNcmError("文件头不是 CTENFDAM，非 NCM 文件")
    offset = 10  # 8 magic + 2 gap

    key_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    key_data = bytes(b ^ 0x64 for b in data[offset:offset + key_len])
    offset += key_len
    key_dec = _unpad(AES.new(CORE_KEY, AES.MODE_ECB).decrypt(key_data))
    rc4_key = key_dec[17:]  # 去掉 'neteasecloudmusic'

    meta_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    if meta_len:
        meta_raw = bytes(b ^ 0x63 for b in data[offset:offset + meta_len])
        offset += meta_len
        meta_b64 = base64.b64decode(meta_raw[22:])  # 去掉 "163 key(Don't modify):"
        meta_dec = _unpad(AES.new(META_KEY, AES.MODE_ECB).decrypt(meta_b64))
        metadata = json.loads(meta_dec[6:])  # 去掉 'music:'
    else:
        metadata = {}

    offset += 4  # CRC32
    offset += 5  # gap
    img_len = struct.unpack("<I", data[offset:offset + 4])[0]
    offset += 4
    cover = data[offset:offset + img_len]
    offset += img_len

    audio = xor_audio(rc4_key, data[offset:])
    return NcmContent(rc4_key=rc4_key, metadata=metadata, cover=cover, audio=audio)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_ncm_parse.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add core/ncm.py tests/test_ncm_parse.py
git commit -m "feat(core): parse NCM container into key/metadata/cover/audio"
```

---

### Task 4: 真实格式判定（内容嗅探）

**Files:**
- Create: `core/formats.py`
- Test: `tests/test_formats.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_formats.py
from core.formats import detect_format

def test_detect_flac():
    assert detect_format(b"fLaC\x00\x00\x00", "mp3") == "flac"

def test_detect_mp3_id3():
    assert detect_format(b"ID3\x04\x00", "") == "mp3"

def test_detect_mp3_frame_sync():
    assert detect_format(b"\xff\xfb\x90\x00", "") == "mp3"

def test_detect_m4a():
    assert detect_format(b"\x00\x00\x00\x20ftypM4A ", "") == "m4a"

def test_fallback_to_declared():
    assert detect_format(b"\x01\x02\x03\x04abcd", "flac") == "flac"

def test_fallback_unknown():
    assert detect_format(b"\x01\x02\x03\x04abcd", "") == "bin"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_formats.py -v`
Expected: FAIL（`No module named 'core.formats'`）

- [ ] **Step 3: 实现 core/formats.py**

```python
# core/formats.py
# 网易云 format 字段通常是 flac/mp3；全景声等特殊封装无法靠它判定，
# 故优先用音频内容的 magic 嗅探真实格式，识别不出再回落到声明值。
KNOWN_AUDIO = {"flac", "mp3"}


def detect_format(audio: bytes, declared: str = "") -> str:
    if audio[:4] == b"fLaC":
        return "flac"
    if audio[:3] == b"ID3":
        return "mp3"
    if len(audio) >= 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0:
        return "mp3"
    if audio[4:8] == b"ftyp":
        return "m4a"
    declared = (declared or "").lower()
    return declared if declared else "bin"


def is_special(fmt: str) -> bool:
    """非标准 flac/mp3（如全景声 m4a / 未知），需原样导出并提示。"""
    return fmt not in KNOWN_AUDIO
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_formats.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add core/formats.py tests/test_formats.py
git commit -m "feat(core): detect real audio format by content sniffing"
```

---

### Task 5: 元数据字段提取与写入

**Files:**
- Create: `core/metadata.py`
- Test: `tests/test_metadata.py`

> 说明：标签字段映射（处理 artist 嵌套列表、缺字段）是值得单测的纯逻辑；mutagen 写文件是薄封装，由 Task 13 真实文件验证。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_metadata.py -v`
Expected: FAIL（`No module named 'core.metadata'`）

- [ ] **Step 3: 实现 core/metadata.py**

```python
# core/metadata.py
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError


def extract_tags(meta: dict) -> dict:
    return {
        "title": meta.get("musicName", "") or "",
        "artists": [a[0] for a in meta.get("artist", []) if a],
        "album": meta.get("album", "") or "",
    }


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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_metadata.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add core/metadata.py tests/test_metadata.py
git commit -m "feat(core): extract tag values and write flac/mp3 tags"
```

---

### Task 6: 文件名模板与冲突处理

**Files:**
- Create: `core/naming.py`
- Test: `tests/test_naming.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_naming.py
import os
from core.naming import render_name, resolve_conflict

def test_render_template():
    tags = {"title": "夜曲", "artists": ["周杰伦"], "album": "十一月"}
    assert render_name("{歌手} - {标题}", tags) == "周杰伦 - 夜曲"
    assert render_name("{专辑}/{标题}", tags) == os.path.join("十一月", "夜曲")

def test_render_sanitizes_illegal_chars():
    tags = {"title": "a/b:c", "artists": ["x"], "album": ""}
    name = render_name("{标题}", tags)
    assert "/" not in os.path.basename(name)
    assert ":" not in name

def test_conflict_skip(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    assert resolve_conflict(str(p), "skip") is None

def test_conflict_overwrite(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    assert resolve_conflict(str(p), "overwrite") == str(p)

def test_conflict_rename(tmp_path):
    p = tmp_path / "song.flac"
    p.write_text("x")
    out = resolve_conflict(str(p), "rename")
    assert out.endswith("song (1).flac")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_naming.py -v`
Expected: FAIL（`No module named 'core.naming'`）

- [ ] **Step 3: 实现 core/naming.py**

```python
# core/naming.py
import os

_ILLEGAL = '<>:"/\\|?*'
_FIELD_MAP = {"{标题}": "title", "{歌手}": "artists", "{专辑}": "album"}


def _sanitize(name: str) -> str:
    for ch in _ILLEGAL:
        name = name.replace(ch, "_")
    return name.strip() or "untitled"


def render_name(template: str, tags: dict) -> str:
    parts = template.split("/")
    rendered = []
    for part in parts:
        text = part
        for token, key in _FIELD_MAP.items():
            value = tags.get(key, "")
            if isinstance(value, list):
                value = ", ".join(value)
            text = text.replace(token, str(value))
        rendered.append(_sanitize(text))
    return os.sep.join(rendered)


def resolve_conflict(path: str, policy: str):
    """返回最终写入路径；policy='skip' 且已存在时返回 None。"""
    if not os.path.exists(path):
        return path
    if policy == "skip":
        return None
    if policy == "overwrite":
        return path
    # rename: song.flac -> song (1).flac -> song (2).flac ...
    root, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{root} ({i}){ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_naming.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
git add core/naming.py tests/test_naming.py
git commit -m "feat(core): filename templating and conflict resolution"
```

---

### Task 7: 单文件转换编排

**Files:**
- Create: `core/converter.py`
- Test: `tests/test_converter.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_converter.py
import os
from tests.conftest import build_ncm
from core.converter import convert_file

def test_convert_flac_outputs_file(tmp_path):
    meta = {"musicName": "夜曲", "artist": [["周杰伦", 1]], "album": "十一月", "format": "flac"}
    audio = b"fLaC" + b"\x00" * 64  # 合法 flac 魔数 + 占位
    src = tmp_path / "a.ncm"
    src.write_bytes(build_ncm(audio, meta))
    res = convert_file(str(src), str(tmp_path / "out"), template="{歌手} - {标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "ok"
    assert res.title == "夜曲"
    assert res.fmt == "flac"
    assert res.output_path.endswith("周杰伦 - 夜曲.flac")
    assert os.path.exists(res.output_path)
    with open(res.output_path, "rb") as f:
        assert f.read() == audio  # 写出的就是解密后的原始音频

def test_convert_non_ncm_skipped(tmp_path):
    src = tmp_path / "x.ncm"
    src.write_bytes(b"not an ncm")
    res = convert_file(str(src), str(tmp_path / "out"), template="{标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "skipped"
    assert "NCM" in res.reason

def test_convert_special_format_exported_as_is(tmp_path):
    meta = {"musicName": "atmos", "artist": [], "album": "", "format": ""}
    audio = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32  # m4a 特征
    src = tmp_path / "s.ncm"
    src.write_bytes(build_ncm(audio, meta))
    res = convert_file(str(src), str(tmp_path / "out"), template="{标题}",
                       conflict="rename", write_tags=False)
    assert res.status == "ok"
    assert res.fmt == "m4a"
    assert res.special is True
    assert res.output_path.endswith(".m4a")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_converter.py -v`
Expected: FAIL（`No module named 'core.converter'`）

- [ ] **Step 3: 实现 core/converter.py**

```python
# core/converter.py
import os
from dataclasses import dataclass, field
from core.ncm import parse_ncm, NotNcmError
from core.formats import detect_format, is_special
from core.metadata import extract_tags, write_flac_tags, write_mp3_tags
from core.naming import render_name, resolve_conflict


@dataclass
class ConvertResult:
    source: str
    status: str = "ok"          # ok | skipped | failed
    reason: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    fmt: str = ""
    special: bool = False
    output_path: str = ""
    cover: bytes = field(default=b"", repr=False)


def convert_file(src: str, out_dir: str, template: str, conflict: str,
                 write_tags: bool = True) -> ConvertResult:
    res = ConvertResult(source=src)
    try:
        with open(src, "rb") as f:
            data = f.read()
    except OSError as e:
        res.status = "failed"
        res.reason = f"无法读取文件：{e}"
        return res

    try:
        content = parse_ncm(data)
    except NotNcmError:
        res.status = "skipped"
        res.reason = "非 NCM 文件，已跳过"
        return res
    except Exception as e:  # 解析中途异常 → 视为损坏
        res.status = "failed"
        res.reason = f"文件损坏或格式异常：{e}"
        return res

    tags = extract_tags(content.metadata)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = content.cover

    fmt = detect_format(content.audio, content.metadata.get("format", ""))
    res.fmt = fmt
    res.special = is_special(fmt)

    os.makedirs(out_dir, exist_ok=True)
    rel = render_name(template, tags) if tags["title"] else os.path.splitext(os.path.basename(src))[0]
    target = os.path.join(out_dir, rel + "." + fmt)
    os.makedirs(os.path.dirname(target), exist_ok=True)

    final = resolve_conflict(target, conflict)
    if final is None:
        res.status = "skipped"
        res.reason = "目标已存在，按设置跳过"
        return res

    try:
        with open(final, "wb") as f:
            f.write(content.audio)
    except OSError as e:
        res.status = "failed"
        res.reason = f"输出目录无法写入：{e}"
        return res

    res.output_path = final

    if write_tags and not res.special:
        try:
            if fmt == "flac":
                write_flac_tags(final, tags, content.cover)
            elif fmt == "mp3":
                write_mp3_tags(final, tags, content.cover)
        except Exception as e:
            # 音频已成功导出；标签写入失败仅记录，不算整体失败
            res.reason = f"已导出，但标签写入失败：{e}"

    if res.special and not res.reason:
        res.reason = "特殊格式（如全景声），已原样导出"
    return res
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_converter.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 跑全部 core 测试**

Run: `conda run -n work pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add core/converter.py tests/test_converter.py
git commit -m "feat(core): orchestrate single-file NCM conversion"
```

---

### Task 8: 可选 ffmpeg 转码

**Files:**
- Create: `core/transcode.py`
- Test: `tests/test_transcode.py`

- [ ] **Step 1: 写失败测试（monkeypatch 模拟 ffmpeg，不依赖真实安装）**

```python
# tests/test_transcode.py
import pytest
from core import transcode

def test_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(transcode.shutil, "which", lambda _: None)
    with pytest.raises(transcode.FfmpegNotFound):
        transcode.transcode("in.flac", "out.wav")

def test_build_command():
    cmd = transcode.build_command("in.flac", "out.wav")
    assert cmd[0] == "ffmpeg"
    assert "in.flac" in cmd and "out.wav" in cmd
    assert "-y" in cmd
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_transcode.py -v`
Expected: FAIL（`No module named 'core.transcode'`）

- [ ] **Step 3: 实现 core/transcode.py**

```python
# core/transcode.py
import shutil
import subprocess


class FfmpegNotFound(RuntimeError):
    pass


def build_command(src: str, dst: str) -> list:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, dst]


def transcode(src: str, dst: str) -> None:
    if shutil.which("ffmpeg") is None:
        raise FfmpegNotFound("未找到 ffmpeg，无法转码")
    subprocess.run(build_command(src, dst), check=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_transcode.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add core/transcode.py tests/test_transcode.py
git commit -m "feat(core): optional ffmpeg transcode helper"
```

---

### Task 9: GUI — 队列数据模型

**Files:**
- Create: `gui/task_model.py`
- Test: `tests/test_task_model.py`

> 模型的纯数据/计数逻辑可单测；视图交互在 Task 11/12 手动验证。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_task_model.py
from gui.task_model import QueueModel, Row

def test_add_and_count():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm")])
    assert m.rowCount() == 2

def test_progress_summary():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm"), Row(source="c.ncm")])
    m.set_status(0, "ok")
    m.set_status(1, "failed")
    done, total = m.progress()
    assert (done, total) == (2, 3)

def test_failed_rows():
    m = QueueModel()
    m.add_rows([Row(source="a.ncm"), Row(source="b.ncm")])
    m.set_status(1, "failed", "坏了")
    assert m.failed_indexes() == [1]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n work pytest tests/test_task_model.py -v`
Expected: FAIL（`No module named 'gui.task_model'`）

- [ ] **Step 3: 实现 gui/task_model.py**

```python
# gui/task_model.py
from dataclasses import dataclass, field
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex

HEADERS = ["标题", "歌手", "专辑", "格式", "状态"]
STATUS_TEXT = {"pending": "待转", "ok": "完成", "skipped": "跳过", "failed": "失败"}


@dataclass
class Row:
    source: str
    title: str = ""
    artist: str = ""
    album: str = ""
    fmt: str = ""
    status: str = "pending"
    reason: str = ""
    cover: bytes = field(default=b"", repr=False)


class QueueModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        r = self.rows[index.row()]
        col = index.column()
        if col == 0:
            return r.title or os.path.basename(r.source)
        if col == 1:
            return r.artist
        if col == 2:
            return r.album
        if col == 3:
            return r.fmt
        if col == 4:
            return STATUS_TEXT.get(r.status, r.status) + (f"：{r.reason}" if r.reason else "")
        return None

    def add_rows(self, rows):
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        self.rows.extend(rows)
        self.endInsertRows()

    def update_row(self, i, **kw):
        row = self.rows[i]
        for k, v in kw.items():
            setattr(row, k, v)
        self.dataChanged.emit(self.index(i, 0), self.index(i, len(HEADERS) - 1))

    def set_status(self, i, status, reason=""):
        self.update_row(i, status=status, reason=reason)

    def progress(self):
        done = sum(1 for r in self.rows if r.status in ("ok", "skipped", "failed"))
        return done, len(self.rows)

    def failed_indexes(self):
        return [i for i, r in enumerate(self.rows) if r.status == "failed"]

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()


import os  # noqa: E402  (data() 中用到)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n work pytest tests/test_task_model.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add gui/task_model.py tests/test_task_model.py
git commit -m "feat(gui): queue table model with progress and failure tracking"
```

---

### Task 10: GUI — 后台转换 Worker

**Files:**
- Create: `gui/workers.py`

> Qt 信号/线程为 I/O 协调，难做纯单测；以实现 + 可导入验证为主，逻辑核心已在 core 覆盖。

- [ ] **Step 1: 实现 gui/workers.py**

```python
# gui/workers.py
import os
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from core.converter import convert_file
from core.transcode import transcode, FfmpegNotFound


class WorkerSignals(QObject):
    finished = pyqtSignal(int, object)  # row index, ConvertResult


class ConvertWorker(QRunnable):
    def __init__(self, index, src, out_dir, template, conflict,
                 to_wav=False, delete_src=False):
        super().__init__()
        self.index = index
        self.src = src
        self.out_dir = out_dir
        self.template = template
        self.conflict = conflict
        self.to_wav = to_wav
        self.delete_src = delete_src
        self.signals = WorkerSignals()

    def run(self):
        res = convert_file(self.src, self.out_dir, self.template, self.conflict)
        if res.status == "ok" and self.to_wav and not res.special:
            try:
                wav = res.output_path.rsplit(".", 1)[0] + ".wav"
                transcode(res.output_path, wav)
                res.output_path = wav
            except FfmpegNotFound:
                res.reason = "未找到 ffmpeg，已保留原始格式"
            except Exception as e:
                res.reason = f"转码失败，已保留原始格式：{e}"
        if res.status == "ok" and self.delete_src:
            try:
                os.remove(self.src)
            except OSError:
                pass
        self.signals.finished.emit(self.index, res)
```

- [ ] **Step 2: 验证可导入**

Run: `conda run -n work python -c "from gui.workers import ConvertWorker; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: Commit**

```bash
git add gui/workers.py
git commit -m "feat(gui): background convert worker with optional transcode/delete"
```

---

### Task 11: GUI — 主窗口与主题

**Files:**
- Create: `gui/theme.py`
- Create: `gui/main_window.py`

- [ ] **Step 1: 实现 gui/theme.py**

```python
# gui/theme.py
DARK = """
QWidget { background:#1e1e22; color:#e8e8ea; font-size:13px; }
QPushButton { background:#2d2d33; border:1px solid #3a3a42; border-radius:6px; padding:6px 12px; }
QPushButton:hover { background:#37373f; }
QTableView { background:#202024; gridline-color:#33333a; selection-background-color:#3a5bd0; }
QHeaderView::section { background:#26262b; padding:4px; border:none; }
#DropZone { border:2px dashed #4a4a55; border-radius:10px; padding:24px; color:#9a9aa5; }
QProgressBar { border:1px solid #3a3a42; border-radius:6px; text-align:center; }
QProgressBar::chunk { background:#3a5bd0; border-radius:6px; }
"""

LIGHT = """
QWidget { background:#f6f6f8; color:#1c1c20; font-size:13px; }
QPushButton { background:#ffffff; border:1px solid #d0d0d8; border-radius:6px; padding:6px 12px; }
QPushButton:hover { background:#eef0f5; }
QTableView { background:#ffffff; gridline-color:#e3e3ea; selection-background-color:#3a5bd0; selection-color:#fff; }
QHeaderView::section { background:#ececf1; padding:4px; border:none; }
#DropZone { border:2px dashed #c2c2cc; border-radius:10px; padding:24px; color:#8a8a95; }
QProgressBar { border:1px solid #d0d0d8; border-radius:6px; text-align:center; }
QProgressBar::chunk { background:#3a5bd0; border-radius:6px; }
"""
```

- [ ] **Step 2: 实现 gui/main_window.py**

```python
# gui/main_window.py
import os
import sys
import subprocess
from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableView, QProgressBar, QFileDialog, QComboBox, QCheckBox, QMessageBox,
    QButtonGroup, QRadioButton,
)
from gui.task_model import QueueModel, Row
from gui.workers import ConvertWorker
from gui import theme

NCM_EXT = ".ncm"


class DropZone(QLabel):
    def __init__(self, on_paths):
        super().__init__("把 NCM 文件或文件夹拖到这里")
        self.setObjectName("DropZone")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.on_paths = on_paths

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls()]
        self.on_paths(paths)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCM 转换器")
        self.resize(860, 560)
        self.pool = QThreadPool.globalInstance()
        self.model = QueueModel()
        self.out_dir = os.path.join(os.path.expanduser("~"), "Music")
        self.dark = True
        self._delete_warned = False
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("NCM 转换器"))
        top.addStretch()
        self.theme_btn = QPushButton("切换主题")
        self.theme_btn.clicked.connect(self._toggle_theme)
        top.addWidget(self.theme_btn)
        root.addLayout(top)

        self.drop = DropZone(self._add_paths)
        root.addWidget(self.drop)
        pick = QHBoxLayout()
        b1 = QPushButton("选择文件"); b1.clicked.connect(self._pick_files)
        b2 = QPushButton("选择文件夹"); b2.clicked.connect(self._pick_folder)
        pick.addWidget(b1); pick.addWidget(b2); pick.addStretch()
        root.addLayout(pick)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        outrow = QHBoxLayout()
        self.out_label = QLabel(f"输出目录：{self.out_dir}")
        ob = QPushButton("更改"); ob.clicked.connect(self._pick_outdir)
        outrow.addWidget(self.out_label, 1); outrow.addWidget(ob)
        root.addLayout(outrow)

        opt = QHBoxLayout()
        opt.addWidget(QLabel("命名模板"))
        self.tpl = QComboBox(); self.tpl.setEditable(True)
        self.tpl.addItems(["{歌手} - {标题}", "{标题}", "{专辑}/{标题}"])
        opt.addWidget(self.tpl)
        opt.addWidget(QLabel("冲突"))
        self.conflict_group = QButtonGroup(self)
        for i, name in enumerate(["跳过", "覆盖", "重命名"]):
            rb = QRadioButton(name)
            if name == "重命名":
                rb.setChecked(True)
            self.conflict_group.addButton(rb, i)
            opt.addWidget(rb)
        self.cb_wav = QCheckBox("转WAV"); opt.addWidget(self.cb_wav)
        self.cb_del = QCheckBox("删原NCM"); opt.addWidget(self.cb_del)
        opt.addStretch()
        root.addLayout(opt)

        bottom = QHBoxLayout()
        self.bar = QProgressBar(); self.bar.setValue(0)
        bottom.addWidget(self.bar, 1)
        self.start_btn = QPushButton("开始转换"); self.start_btn.clicked.connect(self._start)
        self.retry_btn = QPushButton("重试失败"); self.retry_btn.clicked.connect(self._retry)
        self.clear_btn = QPushButton("清空"); self.clear_btn.clicked.connect(self.model.clear)
        bottom.addWidget(self.start_btn); bottom.addWidget(self.retry_btn); bottom.addWidget(self.clear_btn)
        root.addLayout(bottom)

        self.setCentralWidget(central)

    def _scan(self, paths):
        found = []
        for p in paths:
            if os.path.isdir(p):
                for dirpath, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith(NCM_EXT):
                            found.append(os.path.join(dirpath, fn))
            elif p.lower().endswith(NCM_EXT):
                found.append(p)
        return found

    def _add_paths(self, paths):
        files = self._scan(paths)
        if files:
            self.model.add_rows([Row(source=f) for f in files])

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择 NCM 文件", "", "NCM (*.ncm)")
        self._add_paths(files)

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            self._add_paths([d])

    def _pick_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_dir)
        if d:
            self.out_dir = d
            self.out_label.setText(f"输出目录：{d}")

    def _conflict_policy(self):
        return {0: "skip", 1: "overwrite", 2: "rename"}[self.conflict_group.checkedId()]

    def _confirm_delete(self):
        if not self.cb_del.isChecked() or self._delete_warned:
            return True
        ok = QMessageBox.question(self, "确认", "转换成功后将删除原 NCM 文件，确定？") \
            == QMessageBox.StandardButton.Yes
        self._delete_warned = ok
        return ok

    def _dispatch(self, indexes):
        if not indexes:
            return
        if not self._confirm_delete():
            self.cb_del.setChecked(False)
        for i in indexes:
            row = self.model.rows[i]
            self.model.set_status(i, "pending")
            w = ConvertWorker(i, row.source, self.out_dir, self.tpl.currentText(),
                              self._conflict_policy(), self.cb_wav.isChecked(),
                              self.cb_del.isChecked())
            w.signals.finished.connect(self._on_done)
            self.pool.start(w)

    def _start(self):
        self._dispatch(list(range(self.model.rowCount())))

    def _retry(self):
        self._dispatch(self.model.failed_indexes())

    def _on_done(self, i, res):
        self.model.update_row(i, title=res.title, artist=res.artist, album=res.album,
                              fmt=res.fmt, status=res.status, reason=res.reason)
        done, total = self.model.progress()
        self.bar.setMaximum(total or 1)
        self.bar.setValue(done)
        if done == total and total > 0:
            self._finished_dialog()

    def _finished_dialog(self):
        box = QMessageBox(self)
        box.setWindowTitle("完成")
        box.setText("转换完成。")
        open_btn = box.addButton("打开输出目录", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == open_btn:
            self._open_dir(self.out_dir)

    def _open_dir(self, path):
        if sys.platform == "darwin":
            subprocess.run(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path])

    def _apply_theme(self):
        self.setStyleSheet(theme.DARK if self.dark else theme.LIGHT)

    def _toggle_theme(self):
        self.dark = not self.dark
        self._apply_theme()
```

- [ ] **Step 3: 验证可导入**

Run: `conda run -n work python -c "from gui.main_window import MainWindow; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add gui/theme.py gui/main_window.py
git commit -m "feat(gui): main window with drag-drop, queue, options, theme"
```

---

### Task 12: 程序入口与手动冒烟

**Files:**
- Create: `main.py`
- Create: `README.md`

- [ ] **Step 1: 实现 main.py**

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 写 README.md（中性，无 AI 字样）**

````markdown
# NCM 转换器

把网易云音乐 `.ncm` 还原为通用播放器可播放的 flac / mp3，保留标题、歌手、专辑、封面。
支持批量、拖拽、原始格式优先、可选转 WAV。

## 开发与运行（conda work 环境）

```bash
conda run -n work pip install -r requirements.txt
conda run -n work python main.py
conda run -n work pytest
```
````

- [ ] **Step 3: 手动冒烟启动**

Run: `conda run -n work python main.py`
Expected: 窗口正常弹出；可切换主题；拖入/选择文件后队列出现行；空跑不崩溃。关闭窗口结束。

- [ ] **Step 4: Commit**

```bash
git add main.py README.md
git commit -m "feat: app entry point and README"
```

---

### Task 13: 真实文件端到端验证（关键验收）

- [ ] **Step 1: 用真实 .ncm 手动验证**

准备 1 个无损 .ncm、1 个 mp3 音质 .ncm（放仓库外，已被 gitignore）。
Run: `conda run -n work python main.py`，分别拖入转换。
Expected：
- 无损 → 输出 `.flac`，播放器可播放，标题/歌手/专辑/封面正确
- mp3 音质 → 输出 `.mp3`，标签与封面正确
- 队列「格式」列显示真实格式；若有全景声样本，显示「特殊/原样」且后缀非 flac

- [ ] **Step 2: 若字段/封面有偏差，回 `core/metadata.py`/`core/ncm.py` 调整并补单测，重跑**

Run: `conda run -n work pytest -v`
Expected: 全绿

- [ ] **Step 3: Commit（如有修正）**

```bash
git add -A
git commit -m "fix: align metadata/cover with real NCM files"
```

---

### Task 14: 打包（PyInstaller）

**Files:**
- Create: `build.md`

- [ ] **Step 1: 装 PyInstaller**

Run: `conda run -n work pip install pyinstaller`

- [ ] **Step 2: 打当前平台包**

Run: `conda run -n work pyinstaller --noconfirm --windowed --name "NCM转换器" main.py`
Expected: `dist/` 下生成可执行（macOS `.app` / Windows `.exe`，需在对应系统各打一次）

- [ ] **Step 3: 启动产物冒烟**

打开 `dist/` 产物，确认窗口正常、能转换一个文件。

- [ ] **Step 4: 写 build.md 记录命令与注意事项（ffmpeg 需系统安装或另行附带）**

- [ ] **Step 5: Commit**

```bash
git add build.md
git commit -m "docs: packaging instructions"
```

---

## Self-Review

- **Spec 覆盖**：原始格式优先(T4/7)、特殊格式原样导出(T4/7)、标题/歌手/专辑/封面(T5/7/13)、批量+递归(T11)、多线程(T10/11)、转换前预览(T9/11)、智能跳过(T7)、失败清单+重试(T9/11)、冲突处理(T6/11)、完成打开目录(T11)、命名模板(T6/11)、保留目录结构(T6 的 `/` 模板经 render_name 生成子目录)、主题(T11)、删原 NCM+二次确认(T11)、可选转码(T8/10)、打包(T14)。✓
- **占位扫描**：无 TODO/TBD；每个代码步骤含完整代码。✓
- **类型一致**：`ConvertResult`/`Row`/`QueueModel` 字段与 `convert_file(src, out_dir, template, conflict, write_tags)` 签名在 T7/T10 一致。✓
- **诚实边界**：标签写入与真实字节级兼容由 T13 真实文件验证补足，已在抬头声明。✓
