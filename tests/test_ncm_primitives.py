# tests/test_ncm_primitives.py
from core.ncm import build_keybox, xor_audio


def _naive_xor(key, data):
    box = build_keybox(key)
    out = bytearray(len(data))
    for i in range(len(data)):
        j = (i + 1) & 0xFF
        out[i] = data[i] ^ box[(box[j] + box[(box[j] + j) & 0xFF]) & 0xFF]
    return bytes(out)


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


def test_xor_matches_naive_reference():
    # 快速实现必须与逐字节朴素算法完全一致（跨多个 256 周期、含不整除尾部）
    key = b"abcdef0123456789"
    data = bytes((i * 7 + 3) & 0xFF for i in range(256 * 5 + 37))
    assert xor_audio(key, data) == _naive_xor(key, data)


def test_xor_empty():
    assert xor_audio(b"key0", b"") == b""
