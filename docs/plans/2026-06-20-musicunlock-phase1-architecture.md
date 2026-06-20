# MusicUnlock 阶段一:解密器架构重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 ncm 专用解密逻辑重构成「解密器注册表」架构,行为完全不变、现有测试全绿,为后续接入 QQ/酷狗/酷我打好地基。

**Architecture:** 新增 `core/decryptors/`(`base.py` 定义统一接口 + 数据结构,`netease.py` 承接原 `ncm.py`)与 `core/registry.py`(按扩展名 + magic 分派)。`converter.py`、`gui/workers.py`、`gui/main_window.py` 改为通过注册表工作,不再直接 import ncm。

**Tech Stack:** Python 3.9、PyQt6、pycryptodome(AES)、numpy(向量化 XOR)、pytest。

参考设计:`docs/specs/2026-06-20-musicunlock-design.md`(§3 架构、§4 性能)。

---

## 文件结构

新增:
- `core/decryptors/__init__.py` — 包标记(空)
- `core/decryptors/base.py` — `DecryptResult` 数据类、`Decryptor` 基类、异常
- `core/decryptors/netease.py` — 原 `core/ncm.py` 的全部逻辑 + `NeteaseDecryptor`
- `core/registry.py` — `DECRYPTORS` 列表、`get_decryptor()`、`supported_exts()`
- `tests/test_registry.py` — 注册表分派测试

修改:
- `core/converter.py` — `convert_file()` 改走注册表
- `gui/workers.py` — `PreviewWorker` 改走注册表
- `gui/main_window.py:21` — `SUPPORTED_EXT` 改为从注册表派生
- `tests/conftest.py:6` — import 从 `core.ncm` 改为 `core.decryptors.netease`
- `tests/test_ncm_primitives.py:2`、`tests/test_ncm_parse.py` — 同上

删除:
- `core/ncm.py`(逻辑迁入 `netease.py`)

**关键设计点:** 性能特性(numpy XOR + 释放 GIL + 256 字节周期密钥垫)随代码原样迁移,不改算法。

---

## Task 1: 解密器基类与数据结构

**Files:**
- Create: `core/decryptors/__init__.py`
- Create: `core/decryptors/base.py`
- Test: `tests/test_registry.py`(本任务先建文件并写第一个测试)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_registry.py`:

```python
# tests/test_registry.py
from core.decryptors.base import DecryptResult, Decryptor, NotSupportedError


def test_decrypt_result_defaults():
    r = DecryptResult(audio=b"X", fmt="flac")
    assert r.audio == b"X"
    assert r.fmt == "flac"
    assert r.metadata is None
    assert r.cover is None


def test_base_decryptor_preview_defaults_to_decrypt():
    class Dummy(Decryptor):
        exts = (".dummy",)

        @staticmethod
        def sniff(data: bytes) -> bool:
            return data[:3] == b"DUM"

        @staticmethod
        def decrypt(data: bytes) -> DecryptResult:
            return DecryptResult(audio=b"AUDIO", fmt="mp3", metadata={"t": 1}, cover=b"C")

    r = Dummy.preview(b"DUMxxx")
    assert r.fmt == "mp3"
    assert r.metadata == {"t": 1}
    assert r.cover == b"C"
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_registry.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'core.decryptors'`

- [ ] **Step 3: 建包与基类**

创建空文件 `core/decryptors/__init__.py`。

创建 `core/decryptors/base.py`:

```python
# core/decryptors/base.py
from dataclasses import dataclass


class DecryptError(Exception):
    """解密失败(文件损坏、格式异常等)。"""


class NotSupportedError(DecryptError):
    """识别出格式但当前无法解密(如尚未支持的最新加密变体)。"""


@dataclass
class DecryptResult:
    audio: bytes                 # 解密后的原始音频字节(必有)
    fmt: str                     # 内层真实格式:flac / mp3 / ogg / m4a / bin
    metadata: dict | None = None # 壳内自带元数据(仅网易云有,其余为 None)
    cover: bytes | None = None   # 壳内自带封面(仅网易云有,其余为 None)


class Decryptor:
    """所有平台解密器的统一接口。"""

    exts: tuple = ()

    @staticmethod
    def sniff(data: bytes) -> bool:
        """看 magic 判断这段数据是否本格式。"""
        raise NotImplementedError

    @staticmethod
    def decrypt(data: bytes) -> DecryptResult:
        """完整解密,返回解码后的音频。"""
        raise NotImplementedError

    @classmethod
    def preview(cls, data: bytes) -> DecryptResult:
        """仅取元数据/封面/格式用于预览;默认走完整解密,子类可重写以加速。"""
        return cls.decrypt(data)
```

> 注:`dict | None` 在 Python 3.9 的类型注解里用于 dataclass 字段是合法的(作为注解字符串求值时不会报错,因 dataclass 不在运行时解析联合类型为对象)。若运行报 `TypeError: unsupported operand`,改用 `from __future__ import annotations` 置于文件首行。

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_registry.py -q`
Expected: PASS(2 passed)

- [ ] **Step 5: 提交**

```bash
git add core/decryptors/__init__.py core/decryptors/base.py tests/test_registry.py
git commit -m "feat(core): add decryptor base interface and result type"
```

---

## Task 2: 网易云解密器(迁移 ncm.py)

**Files:**
- Create: `core/decryptors/netease.py`
- Test: `tests/test_registry.py`(追加)

- [ ] **Step 1: 写失败测试**

在 `tests/test_registry.py` 末尾追加:

```python
from tests.conftest import build_ncm


def test_netease_decrypt_roundtrip():
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaC\x00\x01\x02audio", {"musicName": "歌", "format": "flac"}, cover=b"IMG")
    assert NeteaseDecryptor.sniff(data) is True
    r = NeteaseDecryptor.decrypt(data)
    assert r.audio == b"fLaC\x00\x01\x02audio"
    assert r.fmt == "flac"
    assert r.metadata["musicName"] == "歌"
    assert r.cover == b"IMG"


def test_netease_preview_skips_audio():
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaCaudio", {"musicName": "歌"}, cover=b"IMG")
    r = NeteaseDecryptor.preview(data)
    assert r.audio == b""
    assert r.metadata["musicName"] == "歌"
    assert r.cover == b"IMG"


def test_netease_sniff_rejects_non_ncm():
    from core.decryptors.netease import NeteaseDecryptor
    assert NeteaseDecryptor.sniff(b"NOTNCM..") is False
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_registry.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'core.decryptors.netease'`

- [ ] **Step 3: 迁移逻辑并实现解密器**

创建 `core/decryptors/netease.py`,内容为原 `core/ncm.py` 全部内容 + 末尾新增 `NeteaseDecryptor`,并在 parse 后用 `detect_format` 定格式:

```python
# core/decryptors/netease.py
import struct
import base64
import json
from dataclasses import dataclass
from Crypto.Cipher import AES

from core.formats import detect_format
from core.decryptors.base import DecryptResult, Decryptor

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


def keystream_pad(rc4_key: bytes) -> bytes:
    """密钥流以 256 字节为周期(每字节只取决于 (i+1) mod 256),
    预计算这一个周期的 256 字节密钥垫。"""
    box = build_keybox(rc4_key)
    pad = bytearray(256)
    for i in range(256):
        j = (i + 1) & 0xFF
        pad[i] = box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(pad)


def xor_audio(rc4_key: bytes, data: bytes) -> bytes:
    """用周期性密钥垫 + numpy 位运算分块异或。numpy ufunc 计算时会释放 GIL,
    使批量转换时界面线程仍能流畅运行;结果与逐字节算法完全一致。"""
    if not data:
        return b""
    import numpy as np
    pad = np.frombuffer(keystream_pad(rc4_key), dtype=np.uint8)
    arr = np.frombuffer(data, dtype=np.uint8)
    out = np.empty_like(arr)
    chunk = 1 << 20  # 1 MiB,为 256 的整数倍,故每块都从相位 0 开始
    for off in range(0, arr.size, chunk):
        block = arr[off:off + chunk]
        np.bitwise_xor(block, np.resize(pad, block.size), out=out[off:off + chunk])
    return out.tobytes()


class NotNcmError(ValueError):
    pass


@dataclass
class NcmContent:
    rc4_key: bytes
    metadata: dict
    cover: bytes
    audio: bytes  # 已解密的原始音频字节


def parse_ncm(data: bytes, decode_audio: bool = True) -> "NcmContent":
    if data[:8] != MAGIC:
        raise NotNcmError("文件头不是 CTENFDAM,非 NCM 文件")
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

    audio = xor_audio(rc4_key, data[offset:]) if decode_audio else b""
    return NcmContent(rc4_key=rc4_key, metadata=metadata, cover=cover, audio=audio)


class NeteaseDecryptor(Decryptor):
    exts = (".ncm",)

    @staticmethod
    def sniff(data: bytes) -> bool:
        return data[:8] == MAGIC

    @staticmethod
    def decrypt(data: bytes) -> DecryptResult:
        c = parse_ncm(data, decode_audio=True)
        fmt = detect_format(c.audio, c.metadata.get("format", ""))
        return DecryptResult(audio=c.audio, fmt=fmt, metadata=c.metadata, cover=c.cover)

    @classmethod
    def preview(cls, data: bytes) -> DecryptResult:
        c = parse_ncm(data, decode_audio=False)
        fmt = c.metadata.get("format", "") or "?"
        return DecryptResult(audio=b"", fmt=fmt, metadata=c.metadata, cover=c.cover)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_registry.py -q`
Expected: PASS(全部通过)

- [ ] **Step 5: 提交**

```bash
git add core/decryptors/netease.py tests/test_registry.py
git commit -m "feat(core): add NeteaseDecryptor (migrated from ncm.py)"
```

---

## Task 3: 注册表分派

**Files:**
- Create: `core/registry.py`
- Test: `tests/test_registry.py`(追加)

- [ ] **Step 1: 写失败测试**

在 `tests/test_registry.py` 末尾追加:

```python
def test_registry_picks_netease_by_ext_and_magic():
    from core.registry import get_decryptor
    from core.decryptors.netease import NeteaseDecryptor
    data = build_ncm(b"fLaCaudio", {"musicName": "歌"})
    dec = get_decryptor("song.ncm", data)
    assert dec is NeteaseDecryptor


def test_registry_returns_none_for_unknown_ext():
    from core.registry import get_decryptor
    assert get_decryptor("song.xyz", b"whatever") is None


def test_registry_returns_none_when_magic_mismatch():
    from core.registry import get_decryptor
    # 扩展名像 ncm 但内容不是
    assert get_decryptor("fake.ncm", b"NOTNCM12") is None


def test_supported_exts_includes_ncm():
    from core.registry import supported_exts
    assert ".ncm" in supported_exts()
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_registry.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'core.registry'`

- [ ] **Step 3: 实现注册表**

创建 `core/registry.py`:

```python
# core/registry.py
import os
from core.decryptors.base import Decryptor
from core.decryptors.netease import NeteaseDecryptor

# 后续阶段在此追加:QQDecryptor / KugouDecryptor / KuwoDecryptor
DECRYPTORS: tuple = (
    NeteaseDecryptor,
)


def get_decryptor(path: str, data: bytes):
    """按扩展名找候选解密器,再用 magic 确认;都不匹配返回 None。"""
    ext = os.path.splitext(path)[1].lower()
    for dec in DECRYPTORS:
        if ext in dec.exts and dec.sniff(data):
            return dec
    return None


def supported_exts() -> tuple:
    """所有解密器支持的加密扩展名(不含直通的 .mp3/.flac)。"""
    out = []
    for dec in DECRYPTORS:
        out.extend(dec.exts)
    return tuple(out)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_registry.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/registry.py tests/test_registry.py
git commit -m "feat(core): add decryptor registry with ext+magic dispatch"
```

---

## Task 4: converter 改走注册表

**Files:**
- Modify: `core/converter.py`
- Test: `tests/test_converter.py`(现有,作为回归;不改)

- [ ] **Step 1: 先跑现有 converter 测试,确认当前全绿(基线)**

Run: `pytest tests/test_converter.py -q`
Expected: PASS(全部通过)

- [ ] **Step 2: 修改 import 段**

把 `core/converter.py` 顶部:

```python
from core.ncm import parse_ncm, NotNcmError
from core.formats import detect_format, is_special
```

改为:

```python
from core.registry import get_decryptor
from core.formats import is_special
```

- [ ] **Step 3: 替换 `convert_file` 的解密段**

把 `convert_file` 中从 `try:` 读文件之后的解密块(原第 110-129 行,`try: content = parse_ncm(data) ...` 到设置 `res.special` 为止)整体替换为:

```python
    dec = get_decryptor(src, data)
    if dec is None:
        res.status = "skipped"
        res.reason = "不支持的格式,已跳过"
        return res

    try:
        result = dec.decrypt(data)
    except Exception as e:
        res.status = "failed"
        res.reason = f"文件损坏或格式异常:{e}"
        return res

    from core.metadata import extract_tags  # 局部 import 保持与原文件结构一致
    metadata = result.metadata or {}
    tags = extract_tags(metadata)
    res.title = tags["title"]
    res.artist = ", ".join(tags["artists"])
    res.album = tags["album"]
    res.cover = result.cover or b""

    fmt = result.fmt
    res.fmt = fmt
    res.special = is_special(fmt)
```

> 说明:其余写文件、写标签、歌词、命名逻辑保持不变,但把原先引用 `content.audio` 的地方改为 `result.audio`。

- [ ] **Step 4: 把后续 `content.audio` / `content.cover` 引用改名**

在 `convert_file` 写文件处,把:

```python
        with open(final, "wb") as f:
            f.write(content.audio)
```

改为:

```python
        with open(final, "wb") as f:
            f.write(result.audio)
```

并把写标签处的 `content.cover` 改为 `result.cover or b""`:

```python
            if fmt == "flac":
                write_flac_tags(final, tags, result.cover or b"")
            elif fmt == "mp3":
                write_mp3_tags(final, tags, result.cover or b"")
```

> 检查:`convert_file` 内不再出现 `content`、`parse_ncm`、`NotNcmError`、`detect_format`。顶部原有的 `from core.metadata import extract_tags, ...` 已经导入 `extract_tags`,Step 3 里的局部 import 可省略——若顶部已 import,请删掉 Step 3 中那行局部 import 避免重复。

- [ ] **Step 5: 运行回归测试**

Run: `pytest tests/test_converter.py tests/test_e2e.py -q`
Expected: PASS(全部通过,行为不变)

- [ ] **Step 6: 提交**

```bash
git add core/converter.py
git commit -m "refactor(core): route convert_file through decryptor registry"
```

---

## Task 5: PreviewWorker 改走注册表

**Files:**
- Modify: `gui/workers.py`
- Test: `tests/test_main_window.py`(现有回归)

- [ ] **Step 1: 修改 PreviewWorker.run**

把 `gui/workers.py` 底部的 import 与 `PreviewWorker.run`:

```python
from core.ncm import parse_ncm
from core.metadata import extract_tags, read_audio_tags
```

改为:

```python
from core.registry import get_decryptor
from core.metadata import extract_tags, read_audio_tags
```

把 `PreviewWorker.run` 中 `.ncm` 分支:

```python
            with open(self.src, "rb") as f:
                data = f.read()
            content = parse_ncm(data, decode_audio=False)
            tags = extract_tags(content.metadata)
            fmt = content.metadata.get("format", "") or "?"
            self.signals.done.emit(self.index, tags, fmt, content.cover or b"")
```

替换为:

```python
            with open(self.src, "rb") as f:
                data = f.read()
            dec = get_decryptor(self.src, data)
            if dec is None:
                self.signals.done.emit(self.index, {"title": "", "artists": [], "album": ""}, "?", b"")
                return
            result = dec.preview(data)
            tags = extract_tags(result.metadata or {})
            fmt = result.fmt or "?"
            self.signals.done.emit(self.index, tags, fmt, result.cover or b"")
```

- [ ] **Step 2: 运行回归测试**

Run: `pytest tests/test_main_window.py -q`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add gui/workers.py
git commit -m "refactor(gui): route PreviewWorker through decryptor registry"
```

---

## Task 6: SUPPORTED_EXT 从注册表派生

**Files:**
- Modify: `gui/main_window.py:21`
- Test: `tests/test_scan.py`(现有回归)

- [ ] **Step 1: 修改 SUPPORTED_EXT**

把 `gui/main_window.py:21`:

```python
SUPPORTED_EXT = (".ncm", ".mp3", ".flac")
```

改为:

```python
from core.registry import supported_exts
SUPPORTED_EXT = supported_exts() + (".mp3", ".flac")
```

> 放在文件已有的 import 段附近;阶段一 `supported_exts()` 返回 `(".ncm",)`,故 `SUPPORTED_EXT == (".ncm", ".mp3", ".flac")`,与原值一致。

- [ ] **Step 2: 运行回归测试**

Run: `pytest tests/test_scan.py -q`
Expected: PASS(`.ncm/.mp3/.flac` 仍被识别)

- [ ] **Step 3: 提交**

```bash
git add gui/main_window.py
git commit -m "refactor(gui): derive SUPPORTED_EXT from decryptor registry"
```

---

## Task 7: 删除 ncm.py,更新测试 import

**Files:**
- Delete: `core/ncm.py`
- Modify: `tests/conftest.py:6`
- Modify: `tests/test_ncm_primitives.py:2`
- Modify: `tests/test_ncm_parse.py`(第 3、27 行)

- [ ] **Step 1: 改 conftest import**

`tests/conftest.py:6`:

```python
from core.ncm import CORE_KEY, META_KEY, xor_audio
```

改为:

```python
from core.decryptors.netease import CORE_KEY, META_KEY, xor_audio
```

- [ ] **Step 2: 改 test_ncm_primitives import**

`tests/test_ncm_primitives.py:2`:

```python
from core.ncm import build_keybox, xor_audio
```

改为:

```python
from core.decryptors.netease import build_keybox, xor_audio
```

- [ ] **Step 3: 改 test_ncm_parse import**

`tests/test_ncm_parse.py` 第 3 行 `from core.ncm import parse_ncm` 改为
`from core.decryptors.netease import parse_ncm`;
第 27 行 `from core.ncm import NotNcmError` 改为
`from core.decryptors.netease import NotNcmError`。

- [ ] **Step 4: 删除旧文件并确认无残留引用**

```bash
git rm core/ncm.py
grep -rn "core.ncm\|from core import ncm\|import ncm" --include=*.py . || echo "无残留引用"
```

Expected: 输出「无残留引用」(grep 无匹配)。

- [ ] **Step 5: 跑全套测试**

Run: `pytest -q`
Expected: PASS(原 58 + 新增 registry 测试,全部通过)

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "refactor(core): remove ncm.py, point tests at decryptors.netease"
```

---

## Task 8: 阶段收尾(全量验证 + PR)

- [ ] **Step 1: 全套测试 + 手动起界面冒烟**

```bash
pytest -q
python main.py   # 手动:拖入一个 .ncm 转换,确认能转、预览正常、封面/标题正确
```

Expected: 全绿;界面行为与重构前一致。

- [ ] **Step 2: 推分支并开 PR(引用总目标 issue)**

```bash
git push -u origin feat/musicunlock-phase1
gh pr create --title "refactor: 解密器注册表架构(MusicUnlock 阶段一)" \
  --body "重构为解密器注册表,行为不变、测试全绿,为接入 QQ/酷狗/酷我打地基。见 docs/specs/2026-06-20-musicunlock-design.md。Refs #<总目标issue号>"
```

- [ ] **Step 3: 等 CI(ci.yml)在 macOS + Windows 跑绿后合并**

```bash
gh pr merge <PR#> --squash --delete-branch
```

---

## 自审结论(对照 spec)

- **§3 架构 / 接口**:Task 1-3 实现 `base`/`netease`/`registry`,接口字段(`audio/fmt/metadata/cover`)与 spec §3.1 一致。✅
- **§4 性能**:numpy XOR + 释放 GIL + 256 字节周期密钥垫随 `xor_audio` 原样迁移,未改算法。✅
- **§6 GUI**:`SUPPORTED_EXT` 改为注册表派生(Task 6);`PreviewWorker` 走注册表(Task 5)。阶段一不改标题/提示文字(留到收尾改名阶段,避免本阶段引入行为变化)。✅
- **§7 测试**:新增 `test_registry.py`;现有测试 import 更新后保持全绿;分派/magic 不匹配的边界已覆盖。✅
- **范围**:本计划仅阶段一(架构 + ncm 迁移),不含任何新平台解密——符合 spec §9 分阶段。QQ/酷狗/酷我各自的实现计划在对应阶段、拿到真实样本与参考实现后单独编写。

> 注:窗口标题/品牌、`.qmc*` 等扩展名、改名发布属于后续阶段,本计划有意不触及,以保证阶段一「行为完全不变」。
