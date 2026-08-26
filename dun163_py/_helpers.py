"""
dun163_py._helpers
==================

Leaf-level helpers ported from dun163.js. None of these touch the cipher
core or the base64 layer; they are the building blocks every higher
function depends on.

Each function is annotated with the JS source line it came from so the
mapping is easy to audit. All ports preserve the JS data model:

* "byte" values are signed Python ints in [-128, 127]; negative numbers
  represent unsigned 0x80..0xFF when interpreted as a uint8. This matches
  what JS produces when a value is `>>>`-shifted and then stored as is.
* "uint32" values are non-negative Python ints; we mask with 0xFFFFFFFF
  whenever the JS code uses `>>> 0` or relies on 32-bit wraparound.
* Byte arrays are plain Python `list[int]` -- not `bytes`/`bytearray` --
  because the JS code mutates them in place and mixes negatives.
"""

from __future__ import annotations

import random as _random
import urllib.parse as _urlparse
from typing import List

from ._constants import X as _CRC_TABLE  # 256-entry CRC32 lookup


# --- F(N): JS line ~569 -------------------------------------------------
# function F(N) {
#     return N < -128 ? F(256 + N) : N > 127 ? F(N - 256) : N;
# }
# Signed-byte normalization. For any int, return value in [-128, 127] s.t.
# `(F(N) & 0xFF) == (N & 0xFF)`. Equivalent to: ((N + 128) & 0xFF) - 128.
def F(N: int) -> int:
    return ((int(N) + 128) & 0xFF) - 128


# --- A(N): JS line ~573 -------------------------------------------------
# Hex string -> signed byte array (only floor(len/2) bytes; trailing odd
# nibble is dropped, matching JS).
def A(N) -> List[int]:
    s = "" + str(N)
    out: List[int] = []
    z = 0
    half = len(s) // 2
    for _ in range(half):
        # parseInt("", 16) is NaN in JS; here input always has 2 chars per pair.
        hi = int(s[z], 16) << 4
        z += 1
        lo = int(s[z], 16)
        z += 1
        out.append(F(hi + lo))
    return out


# --- wK_O(N): JS line ~585 ----------------------------------------------
# Replicates: encodeURIComponent + iterate, decoding %XX into a single
# signed byte and copying everything else as F(charCodeAt(i)).
#
# JS `encodeURIComponent` does NOT encode: A-Z a-z 0-9 - _ . ! ~ * ' ( )
# everything else becomes %XX (UTF-8 bytes for multi-byte chars).
_JS_ENCODE_URI_COMPONENT_SAFE = "!~*'()"


def _js_encode_uri_component(s: str) -> str:
    return _urlparse.quote(s, safe=_JS_ENCODE_URI_COMPONENT_SAFE, encoding="utf-8")


def wK_O(N) -> List[int]:
    s = _js_encode_uri_component(str(N))
    out: List[int] = []
    j = 0
    z = len(s)
    while j < z:
        ch = s[j]
        if ch == "%":
            if j + 2 < z:
                # JS does ++j twice -> consumes the next two hex chars
                hex_pair = s[j + 1] + s[j + 2]
                out.append(A(hex_pair)[0])
                j += 3
            else:
                # Truncated trailing %; JS skips it silently because the
                # `if (J + 2 < Z)` guard fails (no else branch).
                j += 1
        else:
            # charCodeAt for surviving (i.e. non-encoded) ASCII chars.
            # encodeURIComponent guarantees these are ASCII (<128) so
            # F() is a no-op, but keep it for safety.
            out.append(F(ord(ch)))
            j += 1
    return out


# --- Y(N): JS line ~684 -------------------------------------------------
# Lower-case 2-char hex of a (signed or unsigned) byte. Uses unsigned
# bit-extraction so `Y(-1) == "ff"`.
_HEX = "0123456789abcdef"


def Y(N: int) -> str:
    n = int(N) & 0xFF  # works for both signed and unsigned inputs
    return _HEX[(n >> 4) & 0xF] + _HEX[n & 0xF]


# --- I(N): JS line ~689 -------------------------------------------------
# Hex-encode an array of bytes.
def I(N) -> str:
    return "".join(Y(x) for x in N)


# --- _m(N): JS line ~677 ------------------------------------------------
# uint32 -> 4-byte signed array, big-endian (most significant byte first).
def _m(N: int) -> List[int]:
    n = int(N) & 0xFFFFFFFF
    return [
        F((n >> 24) & 0xFF),
        F((n >> 16) & 0xFF),
        F((n >> 8) & 0xFF),
        F(n & 0xFF),
    ]


# --- _qN(N): JS line ~695 -----------------------------------------------
# uint32 -> 8-char lowercase hex (big-endian).
def _qN(N: int) -> str:
    return I(_m(N))


# --- j_wR(N): JS line ~699 ----------------------------------------------
# CRC32 over a signed byte array, returned as 8 lowercase hex chars
# (the standard zlib CRC32 polynomial -- table is in _constants.X).
#
# JS:
#   for (J = 0xFFFFFFFF, ...; ...) J = J >>> 8 ^ X[255 & (J ^ N[Z])];
#   return _qN(0xFFFFFFFF ^ J);
#
# `J ^ N[Z]` in JS coerces the bytes to int32; `& 255` then takes the low
# byte. We replicate by masking N[Z] with 0xFF first.
def j_wR(N) -> str:
    J = 0xFFFFFFFF
    for byte in N:
        idx = 0xFF & (J ^ (int(byte) & 0xFF))
        J = (J >> 8) ^ _CRC_TABLE[idx]
    return _qN(0xFFFFFFFF ^ (J & 0xFFFFFFFF))


# --- Z(): JS line ~601 --------------------------------------------------
# Four random signed bytes. Non-deterministic; not byte-comparable to JS.
def Z() -> List[int]:
    return [F(_random.randrange(0, 256)) for _ in range(4)]


# --- _K(wq): JS line ~707 -----------------------------------------------
# Shallow array-or-iterable copy. Renamed _K_arr to avoid clash with the
# `K` constant (and to keep a Python-friendly identifier).
def _K_arr(wq) -> list:
    return list(wq)


# --- wz_H(N, X, J, Z, B): JS line ~717 ----------------------------------
# Copy at most B elements from N[X..] into J[Z..], stopping when source
# is exhausted. JS mutates J in place and returns it; we do the same.
def wz_H(N, X: int, J: list, Z: int, B: int) -> list:
    P = len(N)
    for E in range(B):
        if X + E < P:
            J[Z + E] = N[X + E]
    return J
