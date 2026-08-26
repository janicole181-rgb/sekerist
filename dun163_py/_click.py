"""
dun163_py._click
================

`get_click_check_data` and `get_color_click_check_data` ported from
dun163.js. These functions simulate mouse-trace data for click and
color-click captchas, encrypt each entry under the image token, and
package the result as a JSON blob with `d`, `m`, `p`, `ext` fields.

Helpers ported here:

    check_w8_T(bytes)               -- custom base64 (alphabet "i/x1Xg...")
    check_w8(imageToken, moveRadio) -- XOR + check_w8_T
    sample(arr, n)                  -- evenly-spaced subsample
    unique2DArray(arr, idx=0)       -- dedupe rows by column

Top-level (random + time dependent):

    get_click_check_data(clickPoints, token)
    get_color_click_check_data(clickPoint, token)

Deterministic test variants:

    _get_click_check_data_with_inputs(
        clickPoints, token, *, now_ms, math_random_seq, encryUuid_salts)
    _get_color_click_check_data_with_inputs(
        clickPoint, token, *, now_ms, math_random_seq, encryUuid_salts)

JSON output format follows JSON.stringify with the JS key order
('d', 'm', 'p', 'ext'). We use json.dumps with separators=(', ', ': ')
to match `JSON.stringify(obj)` (which uses no spaces by default --
NOTE: actually JS JSON.stringify uses no separators; see notes inline).
"""

from __future__ import annotations

import json
import math as _math
import random as _random
import time as _time
from typing import Iterator, List, Mapping, Optional, Sequence, Tuple

from ._b64 import k_A
from ._cipher import T as _xor_cyclic
from ._helpers import wK_O
from ._api import _encryUuid_with_salt, encryUuid


# --- check_w8 / check_w8_T --------------------------------------------
_CHECK_W8_ALPHABET = [
    "i", "/", "x", "1", "X", "g", "U", "0", "z", "7", "k", "8", "N", "+",
    "l", "C", "p", "O", "n", "P", "r", "v", "6", "\\", "q", "u", "2", "G",
    "j", "9", "H", "R", "c", "w", "T", "Y", "Z", "4", "b", "f", "S", "J",
    "B", "h", "a", "W", "s", "t", "A", "e", "o", "M", "I", "E", "Q", "5",
    "m", "D", "d", "V", "F", "L", "K", "y",
]
_CHECK_W8_PAD = "3"


def check_w8_T(q: Sequence[int]) -> str:
    return k_A(q, _CHECK_W8_ALPHABET, _CHECK_W8_PAD)


def check_w8(imageToken: str, moveRadio: str) -> str:
    wp = wK_O(moveRadio)
    wo = wK_O(imageToken)
    return check_w8_T(_xor_cyclic(wp, wo))


# --- sample(arr, n) ---------------------------------------------------
def sample(W: Sequence, y: int) -> list:
    K = len(W)
    if K <= y:
        return list(W)
    out = []
    m = 0
    for A in range(K):
        if A >= m * (K - 1) / (y - 1):
            out.append(W[A])
            m += 1
    return out


# --- unique2DArray(y, K=0) --------------------------------------------
def unique2DArray(y: Sequence, K: int = 0) -> list:
    if not isinstance(y, (list, tuple)):
        return y  # JS: returns y as-is for non-arrays
    seen = {}
    out = []
    for row in y:
        if row is None:
            continue
        key = row[K] if K < len(row) else None
        if key is None:
            continue
        if key not in seen:
            seen[key] = True
            out.append(row)
    return out


# --- JSON output -- match JS JSON.stringify default (no spaces) -------
def _js_stringify(obj) -> str:
    """Mimic JSON.stringify(obj) with default options. JS uses no
    separators; Python's json.dumps with separators=(',', ':') matches."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


# --- click pipeline (shared between click and color-click) ------------
_EMPTY_RESULT = '{"d":"","m":"","p":"","ext":""}'


def _math_random_iter(seq: Sequence[float]) -> Iterator[float]:
    """Iterator over a fixed Math.random sequence (for deterministic
    tests). Real callers pass an iterator that wraps random.random().
    """
    for v in seq:
        yield v


def _real_math_random_iter() -> Iterator[float]:
    while True:
        yield _random.random()


def _encryUuid_iter(salts: Optional[Sequence[Sequence[int]]]) -> Iterator:
    """Iterator over fixed Z()-salt arrays. None means "use real Z()"."""
    if salts is None:
        while True:
            yield None
    else:
        for s in salts:
            yield s


def _enc(s: str, it_salts) -> str:
    salt = next(it_salts)
    if salt is None:
        return encryUuid(s)
    return _encryUuid_with_salt(s, salt)


def _get_click_check_data_core(
    click_points: Sequence[Mapping],
    token: str,
    *,
    now_ms: int,
    rand_iter: Iterator[float],
    salts_iter: Iterator,
) -> str:
    if not click_points or not isinstance(click_points, (list, tuple)) \
            or len(click_points) == 0:
        return _EMPTY_RESULT
    if not token:
        return _EMPTY_RESULT

    trace_data: List[str] = []
    points_coords: List[str] = []
    click_counts = len(click_points)

    current_x = 160
    current_y = 100

    # Per-click move trace
    for i, cp in enumerate(click_points):
        target_x = cp["x"]
        target_y = cp["y"]

        distance = _math.sqrt((target_x - current_x) ** 2
                              + (target_y - current_y) ** 2)
        steps = max(3, int(_math.floor(distance / 15)))

        for j in range(steps):
            progress = (j + 1) / steps
            smooth = 1 - (1 - progress) ** 2

            move_x = int(_math.floor(current_x + (target_x - current_x) * smooth))
            move_y = int(_math.floor(current_y + (target_y - current_y) * smooth))

            move_x += int(_math.floor((next(rand_iter) - 0.5) * 4))
            move_y += int(_math.floor((next(rand_iter) - 0.5) * 4))

            move_x = max(0, min(move_x, 320))
            move_y = max(0, min(move_y, 200))

            move_time = (i * 1200) + (j * 80) + int(_math.floor(next(rand_iter) * 50))

            entry = check_w8(token, f"{move_x},{move_y},{move_time}")
            trace_data.append(entry)

        current_x = target_x
        current_y = target_y

    # Click coordinates
    for k, cp in enumerate(click_points):
        click_x = int(round(cp["x"]))
        click_y = int(round(cp["y"]))
        click_time = (k + 1) * 1200 + int(_math.floor(next(rand_iter) * 200))
        entry = check_w8(token, f"{click_x},{click_y},{click_time}")
        points_coords.append(entry)

    # Sample (Vue.js shouldVerifyCaptcha sample step)
    sampled = sample(trace_data, 50)

    result = {
        "d": "",
        "m": _enc(":".join(sampled), salts_iter),
        "p": _enc(":".join(points_coords), salts_iter),
        "ext": _enc(check_w8(token, f"{click_counts},{len(trace_data)}"),
                    salts_iter),
    }
    return _js_stringify(result)


def _get_color_click_check_data_core(
    click_point: Mapping,
    token: str,
    *,
    now_ms: int,
    rand_iter: Iterator[float],
    salts_iter: Iterator,
) -> str:
    if (not click_point or "x" not in click_point or "y" not in click_point):
        return _EMPTY_RESULT
    if not token:
        return _EMPTY_RESULT

    trace_data: List[str] = []
    points_coords: List[str] = []
    click_counts = 1

    current_x, current_y = 160, 100
    target_x = click_point["x"]
    target_y = click_point["y"]

    distance = _math.sqrt((target_x - current_x) ** 2
                          + (target_y - current_y) ** 2)
    steps = max(8, int(_math.floor(distance / 12)))

    for j in range(steps):
        progress = (j + 1) / steps
        smooth = 1 - (1 - progress) ** 2

        move_x = int(_math.floor(current_x + (target_x - current_x) * smooth))
        move_y = int(_math.floor(current_y + (target_y - current_y) * smooth))

        move_x += int(_math.floor((next(rand_iter) - 0.5) * 3))
        move_y += int(_math.floor((next(rand_iter) - 0.5) * 3))

        move_x = max(0, min(move_x, 320))
        move_y = max(0, min(move_y, 200))

        move_time = j * 90 + int(_math.floor(next(rand_iter) * 40))

        entry = check_w8(token, f"{move_x},{move_y},{move_time}")
        trace_data.append(entry)

    click_x = int(round(click_point["x"]))
    click_y = int(round(click_point["y"]))
    click_time = steps * 90 + 200 + int(_math.floor(next(rand_iter) * 100))
    entry = check_w8(token, f"{click_x},{click_y},{click_time}")
    points_coords.append(entry)

    sampled = sample(trace_data, 50)

    result = {
        "d": "",
        "m": _enc(":".join(sampled), salts_iter),
        "p": _enc(":".join(points_coords), salts_iter),
        "ext": _enc(check_w8(token, f"{click_counts},{len(trace_data)}"),
                    salts_iter),
    }
    return _js_stringify(result)


# --- Public deterministic test variants -------------------------------
def _get_click_check_data_with_inputs(
    click_points: Sequence[Mapping],
    token: str,
    *,
    now_ms: int,
    math_random_seq: Sequence[float],
    encryUuid_salts: Sequence[Sequence[int]],
) -> str:
    return _get_click_check_data_core(
        click_points, token,
        now_ms=now_ms,
        rand_iter=_math_random_iter(math_random_seq),
        salts_iter=_encryUuid_iter(encryUuid_salts),
    )


def _get_color_click_check_data_with_inputs(
    click_point: Mapping,
    token: str,
    *,
    now_ms: int,
    math_random_seq: Sequence[float],
    encryUuid_salts: Sequence[Sequence[int]],
) -> str:
    return _get_color_click_check_data_core(
        click_point, token,
        now_ms=now_ms,
        rand_iter=_math_random_iter(math_random_seq),
        salts_iter=_encryUuid_iter(encryUuid_salts),
    )


# --- Production wrappers ---------------------------------------------
def get_click_check_data(click_points: Sequence[Mapping], token: str) -> str:
    try:
        return _get_click_check_data_core(
            click_points, token,
            now_ms=int(_time.time() * 1000) - 3000,
            rand_iter=_real_math_random_iter(),
            salts_iter=_encryUuid_iter(None),
        )
    except Exception:
        return _EMPTY_RESULT


def get_color_click_check_data(click_point: Mapping, token: str) -> str:
    try:
        return _get_color_click_check_data_core(
            click_point, token,
            now_ms=int(_time.time() * 1000) - 3000,
            rand_iter=_real_math_random_iter(),
            salts_iter=_encryUuid_iter(None),
        )
    except Exception:
        return _EMPTY_RESULT
