"""
dun163_py._api
==============

Public entry points exposed to mlbb_async_new.py:

    get_cb()                 -- random callback id
    encryUuid(uuid)          -- encrypt a UUID (random salt every call)
    getUuid(y, K=None)       -- 62-alphabet random string of length y
                                (or RFC4122-shaped UUIDv4 when y is 0/None)

Internal deterministic helpers (used by tests to bypass the RNG so we
can byte-match the JS implementation):

    _encryUuid_with_salt(uuid, salt)
    _w7_with_salt(salt)
    _getUuid_with_rng(y, K, rng)
"""

from __future__ import annotations

import random as _random
from typing import List, Optional, Sequence, Tuple

from ._b64 import A_wL
from ._cipher import H, J_jbox, T, W, func_X, q, w6
from ._helpers import F, Z, _K_arr, j_wR, wK_O, wz_H


# Public-facing alphabets / constants
_GETUUID_ALPHABET = list(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
_W7_KEY_HEX = "fd6a43ae25f74398b61c03c83be37449"


# --- getUuid -----------------------------------------------------------
def _getUuid_with_rng(y: Optional[int], K: Optional[int], rng) -> str:
    """RNG-injectable variant. `rng` is anything with a `random()` method
    returning a float in [0, 1) -- e.g. a `random.Random` instance.
    """
    T_alpha = _GETUUID_ALPHABET
    if not K:
        K = len(T_alpha)
    if y:
        return "".join(T_alpha[int(rng.random() * K)] for _ in range(int(y)))

    # UUIDv4 layout: y==0 / None
    m: List[str] = [""] * 36
    m[8] = m[13] = m[18] = m[23] = "-"
    m[14] = "4"
    for A in range(36):
        if not m[A]:
            O = int(16 * rng.random())
            m[A] = T_alpha[(3 & O) | 8] if A == 19 else T_alpha[O]
    return "".join(m)


def getUuid(y: Optional[int] = None, K: Optional[int] = None) -> str:
    return _getUuid_with_rng(y, K, _random)


# --- w7 (key derivation block) ----------------------------------------
def _w7_with_salt(salt: Sequence[int]) -> Tuple[List[int], List[int]]:
    """w7 minus the Z() randomness: the salt is supplied by the caller."""
    wq = wK_O(_W7_KEY_HEX)
    wH = list(salt)
    wq = q(wq)              # pad WI key to 64 bytes
    wq = T(wq, q(list(wH))) # XOR with cycled salt
    wq = q(wq)              # final 64-byte derived key
    return wq, wH


def w7() -> List:
    """JS w7(): returns [derived_key (64 bytes), salt (4 bytes)]."""
    wn, wM = _w7_with_salt(Z())
    return [wn, wM]


# --- encryUuid ---------------------------------------------------------
def _encryUuid_with_salt(uuid: str, salt: Sequence[int]) -> str:
    """Deterministic core of encryUuid -- caller supplies the 4-byte salt
    that JS would normally pull from Math.random() via Z().
    """
    wH = wK_O(uuid)
    wn, wM = _w7_with_salt(salt)
    wg = wK_O(j_wR(wH))
    wj = H(_K_arr(wH) + _K_arr(wg))
    wN = func_X(wj)
    we = _K_arr(wM)  # salt prefix; we'll grow it as we go
    wX = wn

    for wJ in range(len(wN)):
        wh = T(w6(wN[wJ]), wn)
        wB = W(wh, wX)
        wh = T(wB, wX)
        wX = J_jbox(J_jbox(wh))
        # JS: wz_H(wX, 0, we, 64 * wJ + 4, 64). The destination index
        # 4..67 (then 68..131, ...) is past the current length on the
        # first call, so we grow `we` ahead of time -- mirroring JS's
        # tolerant `array[index] = value`.
        target_len = 64 * wJ + 4 + 64
        if len(we) < target_len:
            we.extend([0] * (target_len - len(we)))
        wz_H(wX, 0, we, 64 * wJ + 4, 64)

    return A_wL(we)


def encryUuid(uuid: str) -> str:
    return _encryUuid_with_salt(uuid, Z())


# --- get_cb ------------------------------------------------------------
def get_cb() -> str:
    return encryUuid(getUuid(32))


# --- do_onVerify -------------------------------------------------------
# JS: zs = encryUuid(nl + "::" + fp)
#     nU = zs replace { '\\'->'-', '/'->'_', '+'->'*' }
#     return "CN31_" + nU + "_v_i_1"
_DOONVERIFY_PREFIX = "CN31"
_DOONVERIFY_SUFFIX = "_v_i_1"
_DOONVERIFY_TRANS = str.maketrans({"\\": "-", "/": "_", "+": "*"})


def _d_exports(p: str) -> str:
    return p.translate(_DOONVERIFY_TRANS)


def _do_onVerify_with_salt(nl: str, fp: str, salt: Sequence[int]) -> str:
    """Deterministic do_onVerify: caller supplies the encryUuid salt."""
    zs = _encryUuid_with_salt(nl + "::" + fp, salt)
    nU = _d_exports(zs)
    return f"{_DOONVERIFY_PREFIX}_{nU}{_DOONVERIFY_SUFFIX}"


def do_onVerify(nl: str, fp: str) -> str:
    return _do_onVerify_with_salt(nl, fp, Z())
