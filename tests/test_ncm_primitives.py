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
