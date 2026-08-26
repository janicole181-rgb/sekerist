"""
dun163_py: Pure-Python port of dun163.js.

This package mirrors the JS function names used by `mlbb_async_new.py`
(`get_fp`, `get_cb`, `get_click_check_data`, `get_color_click_check_data`,
`do_onVerify`) so it can be a drop-in replacement for the
`execjs.compile(open('dun163.js').read())` context.

The port is built bottom-up; submodules are organized as:

    _constants  -- auto-generated lookup tables (m, K, X, wX)
    _helpers    -- low-level byte / hex / CRC helpers (F, A, wK_O, Y, I,
                   _m, _qN, j_wR, Z, wz_H, _K)
    _cipher     -- block cipher primitives (T, W, q, H, M, func_X,
                   w0..w6, J jbox)                              -- WIP
    _b64        -- custom base64 (A_wL, F_ka, k_A)              -- WIP
    _api        -- public entry points (get_cb, get_fp, ...)    -- WIP

Every public name re-exported here matches the JS function name
exactly so `test_dun163_port.py` can call them by string.
"""
from ._helpers import (
    F,
    A,
    wK_O,
    Y,
    I,
    _m,
    _qN,
    j_wR,
    Z,
    _K_arr,  # JS `_K`
    wz_H,
)
from ._cipher import (
    func_K,
    kk,
    wW,
    T,
    W,
    M,
    q,
    H,
    func_X,
    w0, w1, w2, w3, w4, w5,
    V_ws,
    w6,
    J_jbox,  # JS `J`
)
from ._b64 import F_ka, k_A, A_wL
from ._api import (
    getUuid,
    w7,
    encryUuid,
    get_cb,
    do_onVerify,
    _getUuid_with_rng,
    _w7_with_salt,
    _encryUuid_with_salt,
    _do_onVerify_with_salt,
)
from ._fp import (
    fp_wk,
    fp_wz,
    fp_wC,
    fp_wQ,
    fp_ww,
    fp_w0,
    fp_w1,
    fp_w2,
    fp_w3,
    fp_w5,
    fp_w6,
    fp_w7,
    fp_w8,
    fp_w9,
    fp_wd,
    fp_ws,
    wF,
    wl,
)
from ._get_fp import (
    wm,
    wR_get,
    get_fp,
    _wR_get_with_inputs,
    _get_fp_with_inputs,
    _math_random_to_string_36,
)
from ._click import (
    check_w8,
    check_w8_T,
    sample,
    unique2DArray,
    get_click_check_data,
    get_color_click_check_data,
    _get_click_check_data_with_inputs,
    _get_color_click_check_data_with_inputs,
)

__all__ = [
    # helpers
    "F", "A", "wK_O", "Y", "I", "_m", "_qN", "j_wR", "Z", "_K_arr", "wz_H",
    # cipher
    "func_K", "kk", "wW", "T", "W", "M", "q", "H", "func_X",
    "w0", "w1", "w2", "w3", "w4", "w5", "V_ws", "w6", "J_jbox",
    # b64
    "F_ka", "k_A", "A_wL",
    # public API
    "getUuid", "w7", "encryUuid", "get_cb", "do_onVerify",
    # fp helpers
    "fp_wk", "fp_wz", "fp_wC", "fp_wQ", "fp_ww",
    "fp_w0", "fp_w1", "fp_w2", "fp_w3", "fp_w5",
    "fp_w6", "fp_w7", "fp_w8", "fp_w9", "fp_wd", "fp_ws",
    "wF", "wl",
    # get_fp pipeline
    "wm", "wR_get", "get_fp",
    # click pipeline
    "check_w8", "check_w8_T", "sample", "unique2DArray",
    "get_click_check_data", "get_color_click_check_data",
]
