"""
dun163_py._get_fp
=================

Top-level fingerprint pipeline. Provides:

    _wR_get_with_inputs(ua, canvas_str, plugins_str, tz_offset_min)
        -> [hash1, hash2]   (deterministic; for byte-matching against JS)
    wR_get(ua) -> [hash1, hash2]
        (uses real Math.random/Date)

    _get_fp_with_inputs(
        fp_h, ua, *,
        now_ms,
        wm_str_a, wm_str_b,
        c4_bytes,
        canvas_str, plugins_str,
        tz_offset_min,
    ) -> str
    get_fp(fp_h, ua) -> str   (uses real time/random)

The deterministic helpers exist so `test_dun163_port.py` can byte-compare
Python vs JS by injecting the same random/time state on both sides.
"""

from __future__ import annotations

import datetime as _dt
import math as _math
import random as _random
import time as _time
from typing import List, Optional, Sequence

from ._fp import (
    fp_w0, fp_w1, fp_w2, fp_w3, fp_w5, fp_w6, fp_w7, fp_wC, fp_wQ,
    fp_wd, fp_ws, fp_wz, fp_ww,
)


# --- wm: random alphanumeric string -----------------------------------
_WM_ALPHA = "aZbY0cXdW1eVf2Ug3Th4SiR5jQk6PlO7mNn8MoL9pKqJrIsHtGuFvEwDxCyBzA"


def _wm_with_rng(n: int, rng) -> str:
    return "".join(_WM_ALPHA[int(rng.random() * 62)] for _ in range(n))


def wm(n: int) -> str:
    return _wm_with_rng(n, _random)


# --- hardcoded strings exposed by wR ---------------------------------
# The JS file embeds these long constants inline. They are non-secret
# (they reflect the static OS/browser fingerprint targets) so we can
# copy them verbatim. Kept in this module to keep _fp.py focused on the
# math primitives.
_SYS_COLORS_STR = (
    "ActiveBorder:rgb(0, 0, 0):ActiveCaption:rgb(0, 0, 0):"
    "AppWorkspace:rgb(255, 255, 255):Background:rgb(255, 255, 255):"
    "ButtonFace:rgb(240, 240, 240):ButtonHighlight:rgb(240, 240, 240):"
    "ButtonShadow:rgb(240, 240, 240):ButtonText:rgb(0, 0, 0):"
    "CaptionText:rgb(0, 0, 0):GrayText:rgb(109, 109, 109):"
    "Highlight:rgb(0, 120, 215):HighlightText:rgb(255, 255, 255):"
    "InactiveBorder:rgb(0, 0, 0):InactiveCaption:rgb(255, 255, 255):"
    "InactiveCaptionText:rgb(128, 128, 128):"
    "InfoBackground:rgb(255, 255, 255):InfoText:rgb(0, 0, 0):"
    "Menu:rgb(255, 255, 255):MenuText:rgb(0, 0, 0):"
    "Scrollbar:rgb(255, 255, 255):ThreeDDarkShadow:rgb(0, 0, 0):"
    "ThreeDFace:rgb(240, 240, 240):ThreeDHighlight:rgb(0, 0, 0):"
    "ThreeDLightShadow:rgb(0, 0, 0):ThreeDShadow:rgb(0, 0, 0):"
    "Window:rgb(255, 255, 255):WindowFrame:rgb(0, 0, 0):"
    "WindowText:rgb(0, 0, 0)"
)


# --- _wR_get_with_inputs ----------------------------------------------
# Reproduces `new wR({b:false, a:false}).get(ua)` from JS line 2005.
# With Cz.b=false and Cz.a=false, the WebGL extensions string and the
# fonts string are NOT included; only canvas_str and sys_colors_str go
# into CR, and only the standard semi-dynamic fields go into Cs.
def _js_array_join(arr: Sequence, sep: str) -> str:
    """JS Array.prototype.join semantics: undefined/null become ''."""
    parts = []
    for v in arr:
        if v is None or v is _JS_UNDEFINED:
            parts.append("")
        elif isinstance(v, bool):
            parts.append("true" if v else "false")
        else:
            parts.append(str(v))
    return sep.join(parts)


# Sentinel for JS `undefined` (since Python only has None which serves
# as both null and undefined; the array `[null, undefined]` joins to
# "###" in JS, not "null###" -- both nullish entries become empty).
class _JsUndefined:
    def __repr__(self):  # pragma: no cover
        return "<undefined>"


_JS_UNDEFINED = _JsUndefined()


def _wR_get_with_inputs(
    ua: str,
    canvas_str: str,
    plugins_str: str,
    tz_offset_min: int,
) -> List[str]:
    # CR (constants + canvas + sys_colors). Cz.b=false drops WebGL.
    CR = [
        True,             # sessionStorage
        True,             # localStorage
        True,             # indexedDB
        "undefined",      # addBehavior (JS pushes the *string* "undefined")
        "undefined",      # openDatabase ditto
        _JS_UNDEFINED,    # cpuClass (real `undefined`)
        "Win32",          # navigator.platform
        canvas_str,       # getcanvasToDataURL() result
        _SYS_COLORS_STR,  # C2() (sys colors)
    ]

    # Cs (semi-dynamic). Cz.a=false drops fonts.
    Cs = [
        ua,               # navigator.userAgent
        "zh-CN",          # navigator.language
        24,               # screen.colorDepth
        "864x1536",       # ['864','1536'].join('x')
        tz_offset_min,    # new Date().getTimezoneOffset()
        None,             # navigator.doNotTrack -> JS null
        plugins_str,      # C4() (plugins)
    ]

    return [
        fp_ws(_js_array_join(CR, "###")),
        fp_ws(_js_array_join(Cs, "###")),
    ]


def wR_get(ua: str) -> List[str]:
    """Production wR.get(ua) -- uses real Math.random / Date."""
    canvas_str = _math_random_to_string_36(_random.random())
    plugins_str = _math_random_to_string_36(_random.random())
    tz_offset = _current_tz_offset_min()
    return _wR_get_with_inputs(ua, canvas_str, plugins_str, tz_offset)


# --- get_fp ----------------------------------------------------------
# Follows the structure of dun163.js line 1990+ verbatim. Names mirror
# the JS locals (C0..Cn) where convenient.
_GET_FP_KEY_HEX = "14731255234d414cF91356d684E4E8F5F56c8f1bc"


def _get_fp_with_inputs(
    fp_h: str,
    ua: str,
    *,
    now_ms: int,
    wm_str_a: str,
    wm_str_b: str,
    c4_bytes: Sequence[int],
    canvas_str: str,
    plugins_str: str,
    tz_offset_min: int,
) -> str:
    """Deterministic core of get_fp. All non-deterministic inputs are
    passed in explicitly so the output is fully reproducible.
    """
    if len(c4_bytes) != 4:
        raise ValueError("c4_bytes must have length 4")

    # --- Build the wD object -----------------------------------------
    wD = {"v": "v1.1", "h": fp_h}
    C0 = now_ms + 900000  # 15-minute window
    wD["u"] = wm_str_a + str(C0) + wm_str_b

    C2 = _wR_get_with_inputs(ua, canvas_str, plugins_str, tz_offset_min)
    wD["fp"] = ",".join(C2)

    C3 = fp_wd(wD)
    C4_hex = fp_w2(fp_w7(C3))      # CRC32 hex of fp_w7(serialized object)
    C5 = fp_w7(C3 + C4_hex)        # bytes of (object + crc_hex)
    C6 = fp_w7(_GET_FP_KEY_HEX)    # bytes of secret key string

    # 4 random "salt" bytes (provided as c4_bytes)
    C4 = [fp_wz(int(b)) for b in c4_bytes]

    # State init: C6 = fp_w1(fp_ww(fp_w1(C6), fp_w1(C4)))
    C6 = fp_w1(C6)
    C6 = fp_ww(C6, fp_w1(C4))
    C7 = C6 = fp_w1(C6)

    # --- Pad C8 = C5 to multiple of 64 with length suffix ------------
    C8 = list(C5)
    Cw = len(C8)
    if Cw % 64 <= 60:
        CC = 64 - (Cw % 64) - 4
    else:
        CC = 128 - (Cw % 64) - 4
    C5 = []
    fp_w5(C8, 0, C5, 0, Cw)
    for CQ in range(CC):
        # Grow as needed
        while len(C5) <= Cw + CQ:
            C5.append(0)
        C5[Cw + CQ] = 0
    Cz = fp_w6(Cw)
    fp_w5(Cz, 0, C5, Cw + CC, 4)

    Cw_arr = C5
    if len(Cw_arr) % 64 != 0:
        raise ValueError("1110")

    # --- Chunk into 64-byte blocks -----------------------------------
    C9: List[List[int]] = []
    idx = 0
    for CF in range(len(Cw_arr) // 64):
        block = [0] * 64
        for Cl in range(64):
            block[Cl] = Cw_arr[idx]
            idx += 1
        C9.append(block)

    # --- Output buffer starts with c4_bytes prefix -------------------
    CR_out: List[int] = []
    fp_w5(C4, 0, CR_out, 0, 4)

    # --- Per-block round --------------------------------------------
    for CW in range(len(C9)):
        Ci = C9[CW]
        # Round 1: XOR each byte with constant 37
        CK = fp_wz(37)
        Cs = [fp_wC(v, CK) for v in Ci]

        # Round 2: XOR each byte with decreasing 35,34,33,...
        CA = fp_wz(35)
        CF_arr: List[int] = []
        for v in Cs:
            CF_arr.append(fp_wC(v, CA))
            CA -= 1
        Cs = CF_arr

        # Round 3: ADD each byte with increasing -44,-43,-42,...
        CY = fp_wz(-44)
        CF_arr = []
        for v in Cs:
            CF_arr.append(fp_wQ(v, CY))
            CY += 1
        CL = CF_arr

        # XOR with state C6
        Ct = fp_ww(CL, C6)

        # ADD with state C7 (cyclic)
        Cs = Ct
        if Cs is None:
            Cq = None
        else:
            CF_state = C7
            if CF_state is None:
                Cq = Cs
            else:
                Cl_arr = [0] * len(Cs)
                CH_len = len(CF_state)
                for Cp in range(len(Cs)):
                    Cl_arr[Cp] = fp_wz(Cs[Cp] + CF_state[Cp % CH_len])
                Cq = Cl_arr

        # XOR with C7 again (the JS does fp_ww(Cq, C7) which is XOR)
        Ct = fp_ww(Cq, C7)

        # Double substitution box
        Cn = fp_w0(Ct)
        Cn = fp_w0(Cn)

        # Append 64-byte block to output
        fp_w5(Cn, 0, CR_out, CW * 64 + 4, 64)

        # Update state for next block
        C7 = Cn

    # --- Encode CR_out as fp_w3 base64 (3-byte chunks) ---------------
    Cg = 3
    parts: List[str] = []
    Cj = 0
    while Cj < len(CR_out):
        if not (Cj + Cg <= len(CR_out)):
            parts.append(fp_w3(CR_out, Cj, len(CR_out) - Cj))
            break
        parts.append(fp_w3(CR_out, Cj, Cg))
        Cj += Cg
    CM = "".join(parts)

    return CM + ":" + str(C0)


# --- Production wrappers ---------------------------------------------
def _math_random_to_string_36(x: float) -> str:
    """Mimic JS Number.prototype.toString(36) for x in [0, 1).

    NOT used by the deterministic test path; only needed by `wR_get` /
    `get_fp` when we want a real random string. Matches V8 closely enough
    that the resulting fingerprint is server-acceptable, without trying
    to be byte-identical to V8 (which depends on the IEEE-754 rounding
    of intermediate multiplications and is platform-fragile).
    """
    if x == 0:
        return "0"
    if x < 0:
        return "-" + _math_random_to_string_36(-x)
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    int_part = int(x)
    frac = x - int_part
    out = str(int_part) if int_part else "0"
    if frac > 0:
        out += "."
        for _ in range(11):  # JS typically emits ~11-12 fractional digits
            frac *= 36
            digit = int(frac)
            out += chars[digit]
            frac -= digit
            if frac == 0:
                break
    return out


def _current_tz_offset_min() -> int:
    """Minutes WEST of UTC, matching JS Date.prototype.getTimezoneOffset."""
    offset = _dt.datetime.now().astimezone().utcoffset()
    if offset is None:
        return 0
    return -int(offset.total_seconds() // 60)


def get_fp(fp_h: str, ua: str) -> str:
    """Production entry point. Pulls now/random/timezone live."""
    now_ms = int(_time.time() * 1000)
    wm_a = wm(3)
    wm_b = wm(3)
    canvas_str = _math_random_to_string_36(_random.random())
    plugins_str = _math_random_to_string_36(_random.random())
    c4_bytes = [fp_wz(int(_random.random() * 256)) for _ in range(4)]
    tz_offset = _current_tz_offset_min()
    return _get_fp_with_inputs(
        fp_h, ua,
        now_ms=now_ms,
        wm_str_a=wm_a, wm_str_b=wm_b,
        c4_bytes=c4_bytes,
        canvas_str=canvas_str, plugins_str=plugins_str,
        tz_offset_min=tz_offset,
    )
