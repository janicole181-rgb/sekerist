"""
dun163_py._fp
=============

Helpers used exclusively by `get_fp` (and the inner `wR.get` /
fingerprint pipeline). Most of these are near-duplicates of the helpers
in `_helpers` / `_cipher` but with subtly different conventions (signed
vs unsigned bytes, recursive vs iterative normalize, throws vs returns
empty). We port them verbatim to keep byte parity with the JS.

Mapping JS -> Python (this file):
    fp_wk   -> fp_wk      (fill array with constant)
    fp_wz   -> fp_wz      (recursive signed-byte normalize)
    fp_wC   -> fp_wC      (signed-byte XOR)
    fp_wQ   -> fp_wQ      (signed-byte ADD)
    fp_ww   -> fp_ww      (elementwise XOR with length guard)
    fp_w0   -> fp_w0      (wX substitution)
    fp_w1   -> fp_w1      (cyclic 64-byte pad)
    fp_w2   -> fp_w2      (CRC32 -> hex string)
    fp_w3   -> fp_w3      (custom base64 alphabet)
    fp_w5   -> fp_w5      (array copy with throws)
    fp_w6   -> fp_w6      (uint32 -> 4 unsigned bytes BE)
    fp_w7   -> fp_w7      (encodeURIComponent -> bytes)
    fp_w8   -> fp_w8      (hex -> signed bytes)
    fp_w9   -> fp_w9      (byte -> 2 hex chars)
    fp_wd   -> fp_wd      (object -> "{'k1':'v1',...}")
    fp_ws   -> fp_ws      (MurmurHash3-32 + decimal stats suffix)
    wF      -> wF         (digit-string truncating "round")
    wl      -> wl         (left/right pad to width)

The functions that depend on `Date`, `Math.random`, `navigator.*` etc.
(i.e. `wm`, `wR.get`, `get_fp` itself) live in `_get_fp.py`.
"""

from __future__ import annotations

import urllib.parse as _urlparse
from typing import Any, List, Optional

from ._constants import K, X as _CRC_TABLE, m, wX
from ._helpers import _js_encode_uri_component


# --- fp_wk(n, c): JS ~996 ----------------------------------------------
def fp_wk(wb: int, wD) -> list:
    if wb <= 0:
        return [0]
    return [wD] * int(wb)


# --- fp_wz(N): JS ~1471 -- recursive signed-byte normalize -------------
# Equivalent to F() for typical numeric inputs but kept separate for
# faithful behavior on edge cases.
def fp_wz(wb: int) -> int:
    n = int(wb)
    return ((n + 128) & 0xFF) - 128


# --- fp_wC(N, X): JS ~1570 ---------------------------------------------
def fp_wC(wb, wD) -> int:
    return fp_wz(fp_wz(wb) ^ fp_wz(wD))


# --- fp_wQ(N, X): JS ~1565 ---------------------------------------------
def fp_wQ(wb, wD) -> int:
    return fp_wz(wb + wD)


# --- fp_ww(arr1, arr2): JS ~1577 ---------------------------------------
# Element-wise XOR. If either is None or lengths differ, returns wb.
def fp_ww(wb, wD) -> list:
    if wb is None or wD is None or len(wb) != len(wD):
        return wb
    return [fp_wC(wb[i], wD[i]) for i in range(len(wb))]


# --- fp_w0(arr): JS ~1601 ----------------------------------------------
# Substitution via the wX 256-entry lookup, indexed by `byte & 0xFF`.
def fp_w0(wb) -> Optional[list]:
    if wb is None:
        return None
    out = []
    for v in wb:
        v = int(v)
        # JS: wX[(C1 >>> 4 & 15) * m[49] + (C1 & 15)]  with m[49] = 16
        # which simplifies to wX[byte & 0xFF].
        out.append(wX[v & 0xFF])
    return out


# --- fp_w1(arr): JS ~1547 ----------------------------------------------
# Cyclically pad/truncate to exactly 64 entries. Unlike `q` from _cipher,
# this version copies (does NOT splice/mutate) the source on the >=64 path.
def fp_w1(wb) -> list:
    if len(wb) >= 64:
        return [wb[i] for i in range(64)]
    n = len(wb)
    return [wb[i % n] for i in range(64)]


# --- fp_w6(uint32): JS ~1513 -------------------------------------------
# uint32 -> [hi, .., .., lo] as UNSIGNED bytes (in [0, 255]).
def fp_w6(wb: int) -> list:
    n = int(wb) & 0xFFFFFFFF
    return [
        (n >> 24) & 0xFF,
        (n >> 16) & 0xFF,
        (n >> 8) & 0xFF,
        n & 0xFF,
    ]


# --- fp_w9(byte): JS ~1522 ---------------------------------------------
_HEX = "0123456789abcdef"


def fp_w9(wb: int) -> str:
    n = int(wb)
    return _HEX[(n >> 4) & 0xF] + _HEX[n & 0xF]


# --- fp_w2(arr): JS ~1530 ----------------------------------------------
# CRC32 over a (possibly signed) byte array; returns 8-char lowercase hex.
def fp_w2(wb) -> str:
    wD = 0xFFFFFFFF
    for byte in wb:
        wD = (wD >> 8) ^ _CRC_TABLE[(wD ^ (int(byte) & 0xFF)) & 0xFF]
    bytes_arr = fp_w6(wD ^ 0xFFFFFFFF)
    return "".join(fp_w9(b) for b in bytes_arr)


# --- fp_w8(hex_str): JS ~1485 ------------------------------------------
def fp_w8(wb) -> list:
    if wb is None or len(wb) == 0:
        return []
    s = str(wb)
    out = []
    half = len(s) // 2
    j = 0
    for _ in range(half):
        hi = int(s[j], 16) << 4
        j += 1
        lo = int(s[j], 16)
        j += 1
        out.append(fp_wz(hi + lo))
    return out


# --- fp_w7(s): JS ~1498 ------------------------------------------------
# encodeURIComponent + percent-decode + raw charCodeAt for non-%.
# Differs from wK_O in that ASCII chars are pushed unmodified (no F()).
# For typical ASCII inputs this is identical to wK_O but for safety we
# port it exactly.
def fp_w7(wb) -> Optional[list]:
    if wb is None:
        return wb
    s = _js_encode_uri_component(str(wb))
    out: List[int] = []
    j = 0
    n = len(s)
    while j < n:
        ch = s[j]
        if ch == "%":
            # JS: ++C0 twice; hits the next two chars
            pair = s[j + 1] + s[j + 2]
            out.append(fp_w8(pair)[0])
            j += 3
        else:
            # NOTE: not F-normalized; JS pushes raw charCodeAt.
            # encodeURIComponent guarantees ASCII so values are 0..127.
            out.append(ord(ch))
            j += 1
    return out


# --- fp_w5(N, X, J, Z, B): JS ~1588 ------------------------------------
# Array copy with throws (vs wz_H which silently absorbs out-of-range).
def fp_w5(wb, wD: int, wv: list, C0: int, C1: int) -> list:
    if wb is None or len(wb) == 0:
        return wv
    if wv is None:
        raise ValueError(K[133])
    if len(wb) < C1:
        raise ValueError(K[135])

    # Grow destination if needed (JS `arr[i] = v` auto-extends).
    target = C0 + C1
    if len(wv) < target:
        wv.extend([0] * (target - len(wv)))
    for C2 in range(C1):
        wv[C0 + C2] = wb[wD + C2]
    return wv


# --- fp_w3(arr, off, n): JS ~1613 -- custom-alphabet base64 encode -----
# The JS array is preserved verbatim, including the unusual `"\\"` slot
# at index 10 (a literal backslash) and `"V"` at index 14 (NOT "u" --
# `wK_O`'s alphabet uses the lowercase variant; this one uses uppercase).
_FP_W3_ALPHABET = [
    "2", "4", "0", "a", "Y", "H", "i", "Q", "x", "L", "\\", "Z", "u", "f",
    "V", "l", "g", "8", "s", "P", "M", "R", "6", "d", "G", "k", "X", "v",
    "O", "/", "C", "b", "w", "9", "W", "D", "j", "1", "E", "T", "y", "I",
    "S", "c", "m", "e", "o", "J", "z", "3", "7", "q", "t", "h", "B", "r",
    "U", "+", "K", "N", "A", "5", "p", "n",
]
_FP_W3_PAD = "F"


def fp_w3(wb, wD: int, wv: int) -> str:
    """Encode wv bytes from wb starting at wD into 4 alphabet chars.

    `wv` must be 1, 2, or 3; anything else raises (matches JS).
    """
    A = _FP_W3_ALPHABET
    P = _FP_W3_PAD

    if wv == 1:
        v0 = int(wb[wD]) & 0xFF
        C3 = 0
        return (
            A[(v0 >> 2) & 0x3F]
            + A[((v0 << 4) & 0x30) + ((C3 >> 4) & 0x0F)]
            + P + P
        )
    if wv == 2:
        v0 = int(wb[wD]) & 0xFF
        v1 = int(wb[wD + 1]) & 0xFF
        v2 = 0
        return (
            A[(v0 >> 2) & 0x3F]
            + A[((v0 << 4) & 0x30) + ((v1 >> 4) & 0x0F)]
            + A[((v1 << 2) & 0x3C) + ((v2 >> 6) & 0x03)]
            + P
        )
    if wv == 3:
        v0 = int(wb[wD]) & 0xFF
        v1 = int(wb[wD + 1]) & 0xFF
        v2 = int(wb[wD + 2]) & 0xFF
        return (
            A[(v0 >> 2) & 0x3F]
            + A[((v0 << 4) & 0x30) + ((v1 >> 4) & 0x0F)]
            + A[((v1 << 2) & 0x3C) + ((v2 >> 6) & 0x03)]
            + A[v2 & 0x3F]
        )
    raise ValueError("1010")


# --- fp_wd(obj): JS ~1448 ----------------------------------------------
# Custom JSON-ish serialize. Iterates a fixed key whitelist and uses
# single quotes. Replaces single quotes with the bizarre sequence "':'"
# (matches the JS `replace(/'/g, "':'")`); double quotes get re-escaped.
_FP_WD_KEYS = ["v", "fp", "u", "h", "ec", "em", "icp"]


def fp_wd(wb: Any) -> Optional[str]:
    if not isinstance(wb, dict):
        return None
    parts = ["{"]
    for key in _FP_WD_KEYS:
        if key in wb:
            val = wb[key]
            # JS: "" + wb[key]   then   .replace(/'/g, "':'").replace(/"/g, '"')
            sval = "" + str(val) if val is not None else "null"
            sval = sval.replace("'", "':'")
            # The JS regex /"/g replacement is the literal string '"' --
            # i.e. it's a no-op (replaces " with "). Preserved verbatim.
            parts.append("'" + key + "':'" + sval + "',")
    if parts[-1].endswith(","):
        parts[-1] = parts[-1][:-1]
    parts.append("}")
    return "".join(parts)


# --- wF(wb, wD): JS ~1004 ----------------------------------------------
# Truncates a number to its first wD significant decimal *digits*
# (period removed). E.g. wF(0.5, 2) -> 5; wF(2.34, 2) -> 23.
def wF(wb, wD: int) -> int:
    if wb < 0 or wb >= m[34]:  # m[34] = 10
        raise ValueError(K[32])
    pad = ["0"] * int(wD)
    s = "" + _js_number_to_string(wb)
    wv = 0
    C0 = 0
    while wv < len(pad) and C0 < len(s):
        if s[C0] != K[40]:  # K[40] = '.'
            pad[wv] = s[C0]
            wv += 1
        C0 += 1
    return int("".join(pad))


def _js_number_to_string(n) -> str:
    """Reproduce JS `'' + n` for floats. CPython and V8 use IEEE 754 with
    nearly identical formatting rules (shortest round-trip representation);
    this matches in all cases that arise in fp_ws (means/spreads of small
    integer divisions).
    """
    if isinstance(n, bool):
        return "true" if n else "false"
    if isinstance(n, int):
        return str(n)
    if isinstance(n, float):
        # Python repr() also uses shortest round-trip.
        if n.is_integer():
            return str(int(n))
        return repr(n)
    return str(n)


# --- wl(wb, wD, wv, C0): JS ~1020 -- left/right pad to wv width --------
def wl(wb, wD, wv: int, C0: str) -> str:
    s = "" + _js_number_to_string(wb)
    if len(s) > wv:
        raise ValueError(K[89])
    if len(s) == wv:
        return s
    pad = C0 * (wv - len(s))
    return (pad + s) if wD else (s + pad)


# --- fp_ws(s): JS ~1035 ------------------------------------------------
# MurmurHash3-32 with seed=31 plus a "decimal stats" suffix made of the
# digit-mean and a digit-spread metric. Returns a digit string (e.g.
# "37550335803948...").
def fp_ws(wb: str) -> str:
    seed = m[79]   # 31
    c1 = m[12]     # 0xCC9E2D51 = 3432918353
    c2 = m[365]   # 0x1B873593 = 461845907

    n = len(wb)
    tail_len = n & 3
    body_len = n - tail_len

    h = seed

    # --- body: 4-byte little-endian chunks -----------------------------
    j = 0
    while j < body_len:
        k = (
            (ord(wb[j]) & 0xFF)
            | ((ord(wb[j + 1]) & 0xFF) << 8)
            | ((ord(wb[j + 2]) & 0xFF) << 16)
            | ((ord(wb[j + 3]) & 0xFF) << m[65])  # m[65] = 24
        )
        j += 4
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> m[51])) & 0xFFFFFFFF  # ROTL_15  (m[51]=17)
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << m[41]) | (h >> m[55])) & 0xFFFFFFFF  # ROTL_13 (m[41]=13)
        h = ((h * m[17]) + (m[384] + (m[425] << 16))) & 0xFFFFFFFF
        # The JS form decomposes this as separate low/high additions;
        # we showed in-line that the truncation-mod-2**32 result is
        # identical to (h*5 + 0xE6546B64) & 0xFFFFFFFF.

    # --- tail ---------------------------------------------------------
    k = 0
    if tail_len == 3:
        k ^= (ord(wb[j + 2]) & 0xFF) << 16
    if tail_len >= 2:
        k ^= (ord(wb[j + 1]) & 0xFF) << 8
    if tail_len >= 1:
        k ^= ord(wb[j]) & 0xFF
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> m[51])) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k

    # --- finalization -------------------------------------------------
    h ^= n
    h ^= h >> 16
    h = (h * m[396]) & 0xFFFFFFFF  # 0x85ebca6b
    h ^= h >> m[41]
    h = (h * m[339]) & 0xFFFFFFFF  # 0xc2b2ae35
    h ^= h >> 16

    h_uint = h & 0xFFFFFFFF

    # --- decimal stats suffix -----------------------------------------
    parts: List[str] = [str(h_uint)]
    s_hash = str(h_uint)

    # mean-of-digits (with non-digit chars contributing +1 -- but for a
    # pure-uint32 string these never occur)
    sum_digits = 0
    cnt = 0
    for ch in s_hash:
        if ch.isdigit():
            sum_digits += int(ch)
        else:
            sum_digits += 1
        cnt += 1
    if cnt == 0:
        cnt = 1
    mean = wF(sum_digits / cnt, 2)  # 2 == wg

    # threshold: mean // 10^(wg-1) = mean // 10
    threshold = mean // (m[34] ** (2 - 1))

    below_count = 0
    below_sum = 0
    above_count = 0
    above_sum = 0
    for ch in s_hash:
        if ch.isdigit():
            d = int(ch)
            if d < threshold:
                below_count += 1
                below_sum += d
            else:
                above_count += 1
                above_sum += d
        else:
            above_count += 1
            above_sum += threshold

    if above_count == 0:
        above_count = 1
    if below_count == 0:
        below_count = 1
    spread = wF(above_sum / above_count - below_sum / below_count, 2)  # wj=2

    parts.append(wl(mean, True, 2, K[43]))   # K[43] = '0'
    parts.append(wl(spread, True, 2, K[43]))
    return "".join(parts)
