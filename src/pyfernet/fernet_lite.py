#!/usr/bin/env python3
"""纯标准库 AES-128-CBC + Fernet 兼容加解密（无第三方依赖）。

口令 → PBKDF2-HMAC-SHA256 → 32 字节密钥 → urlsafe-b64 作为 Fernet key。
算法与 cryptography.fernet.Fernet 互通（同一 key / token）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time

# --- AES-128（最小实现，仅 ECB 单块 + CBC 包装）---

_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)
_INV_SBOX = tuple(_SBOX.index(i) for i in range(256))
_RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF


def _mul(a: int, b: int) -> int:
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


def _expand_key(key: bytes) -> list[list[int]]:
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    w = list(key)
    for i in range(4, 44):
        t = w[(i - 1) * 4 : i * 4]
        if i % 4 == 0:
            t = [_SBOX[t[1]] ^ _RCON[i // 4], _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
        w.extend(w[(i - 4) * 4 + j] ^ t[j] for j in range(4))
    return [w[i : i + 16] for i in range(0, 176, 16)]


def _add_round_key(s: list[int], rk: list[int]) -> None:
    for i in range(16):
        s[i] ^= rk[i]


def _sub_bytes(s: list[int], box: tuple[int, ...]) -> None:
    for i in range(16):
        s[i] = box[s[i]]


def _shift_rows(s: list[int]) -> None:
    s[1], s[5], s[9], s[13] = s[5], s[9], s[13], s[1]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[15], s[3], s[7], s[11]


def _inv_shift_rows(s: list[int]) -> None:
    s[1], s[5], s[9], s[13] = s[13], s[1], s[5], s[9]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[7], s[11], s[15], s[3]


def _mix_columns(s: list[int]) -> None:
    for c in range(4):
        i = c * 4
        a, b, d, e = s[i], s[i + 1], s[i + 2], s[i + 3]
        s[i] = _mul(a, 2) ^ _mul(b, 3) ^ d ^ e
        s[i + 1] = a ^ _mul(b, 2) ^ _mul(d, 3) ^ e
        s[i + 2] = a ^ b ^ _mul(d, 2) ^ _mul(e, 3)
        s[i + 3] = _mul(a, 3) ^ b ^ d ^ _mul(e, 2)


def _inv_mix_columns(s: list[int]) -> None:
    for c in range(4):
        i = c * 4
        a, b, d, e = s[i], s[i + 1], s[i + 2], s[i + 3]
        s[i] = _mul(a, 14) ^ _mul(b, 11) ^ _mul(d, 13) ^ _mul(e, 9)
        s[i + 1] = _mul(a, 9) ^ _mul(b, 14) ^ _mul(d, 11) ^ _mul(e, 13)
        s[i + 2] = _mul(a, 13) ^ _mul(b, 9) ^ _mul(d, 14) ^ _mul(e, 11)
        s[i + 3] = _mul(a, 11) ^ _mul(b, 13) ^ _mul(d, 9) ^ _mul(e, 14)


def _encrypt_block(block: bytes, round_keys: list[list[int]]) -> bytes:
    s = list(block)
    _add_round_key(s, round_keys[0])
    for r in range(1, 10):
        _sub_bytes(s, _SBOX)
        _shift_rows(s)
        _mix_columns(s)
        _add_round_key(s, round_keys[r])
    _sub_bytes(s, _SBOX)
    _shift_rows(s)
    _add_round_key(s, round_keys[10])
    return bytes(s)


def _decrypt_block(block: bytes, round_keys: list[list[int]]) -> bytes:
    s = list(block)
    _add_round_key(s, round_keys[10])
    for r in range(9, 0, -1):
        _inv_shift_rows(s)
        _sub_bytes(s, _INV_SBOX)
        _add_round_key(s, round_keys[r])
        _inv_mix_columns(s)
    _inv_shift_rows(s)
    _sub_bytes(s, _INV_SBOX)
    _add_round_key(s, round_keys[0])
    return bytes(s)


def _pkcs7_pad(data: bytes) -> bytes:
    n = 16 - (len(data) % 16)
    return data + bytes([n] * n)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("invalid padding")
    n = data[-1]
    if n < 1 or n > 16 or data[-n:] != bytes([n] * n):
        raise ValueError("invalid padding")
    return data[:-n]


def aes_cbc_encrypt(key16: bytes, iv: bytes, plain: bytes) -> bytes:
    if len(iv) != 16:
        raise ValueError("IV must be 16 bytes")
    round_keys = _expand_key(key16)
    data = _pkcs7_pad(plain)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = bytes(a ^ b for a, b in zip(data[i : i + 16], prev))
        enc = _encrypt_block(block, round_keys)
        out.extend(enc)
        prev = enc
    return bytes(out)


def aes_cbc_decrypt(key16: bytes, iv: bytes, cipher: bytes) -> bytes:
    if len(iv) != 16 or len(cipher) % 16:
        raise ValueError("invalid ciphertext")
    round_keys = _expand_key(key16)
    out = bytearray()
    prev = iv
    for i in range(0, len(cipher), 16):
        block = cipher[i : i + 16]
        dec = _decrypt_block(block, round_keys)
        out.extend(a ^ b for a, b in zip(dec, prev))
        prev = block
    return _pkcs7_unpad(bytes(out))


# --- Fernet（与 cryptography.fernet 兼容）---


class InvalidToken(Exception):
    pass


class FernetLite:
    """urlsafe-b64 32 字节 key：前 16 签名，后 16 加密。"""

    def __init__(self, key: bytes | str):
        if isinstance(key, str):
            key = key.encode("ascii")
        raw = base64.urlsafe_b64decode(key)
        if len(raw) != 32:
            raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes")
        self._signing_key = raw[:16]
        self._encryption_key = raw[16:]

    def encrypt(self, data: bytes) -> bytes:
        iv = os.urandom(16)
        ts = int(time.time())
        ciphertext = aes_cbc_encrypt(self._encryption_key, iv, data)
        basic = b"\x80" + struct.pack(">Q", ts) + iv + ciphertext
        digest = hmac.new(self._signing_key, basic, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(basic + digest)

    def decrypt(self, token: bytes, ttl: int | None = None) -> bytes:
        try:
            data = base64.urlsafe_b64decode(token)
        except Exception as e:
            raise InvalidToken("invalid token") from e
        if len(data) < 1 + 8 + 16 + 16 + 32 or data[0] != 0x80:
            raise InvalidToken("invalid token")
        basic, digest = data[:-32], data[-32:]
        expect = hmac.new(self._signing_key, basic, hashlib.sha256).digest()
        if not hmac.compare_digest(digest, expect):
            raise InvalidToken("invalid token")
        ts = struct.unpack(">Q", basic[1:9])[0]
        if ttl is not None and int(time.time()) - ts > ttl:
            raise InvalidToken("token expired")
        iv = basic[9:25]
        ciphertext = basic[25:]
        try:
            return aes_cbc_decrypt(self._encryption_key, iv, ciphertext)
        except ValueError as e:
            raise InvalidToken("invalid token") from e


def derive_fernet_key(password: str, salt: bytes, iterations: int = 390_000) -> bytes:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return base64.urlsafe_b64encode(raw)
