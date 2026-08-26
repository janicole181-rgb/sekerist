"""
dun163_py._cipher
=================

Cipher primitives ported from dun163.js. Built on top of `_helpers`.

Naming sticks to the JS originals so test_dun163_port.py can call them
by string (`func_K`, `T`, `W`, `q`, `H`, `M`, `func_X`, `w0`..`w5`,
`V_ws`, `w6`). The dead-code function `G` is preserved as a stub that
raises -- it is never reached via `w6`'s magic-string dispatch table.

The `J` "jbox" function is exported as `J_jbox` (the JS name `J` clashes
with the Python convention against single-letter top-level identifiers).
"""

from __future__ import annotations

from typing import List

from ._helpers import F, A, _m


# --- func_K(N, X): JS ~629 -- XOR two signed bytes ---------------------
def func_K(N, X) -> int:
    return F(F(N) ^ F(X))


# --- kk(N, X): JS ~643 -- ADD two signed bytes -------------------------
def kk(N, X) -> int:
    return F(N + X)


# --- wW(N, X): JS ~761 -- ADD two signed bytes (alias of kk) -----------
def wW(N, X) -> int:
    return F(N + X)


# --- T(N, X): JS ~633 --------------------------------------------------
# Element-wise XOR of N with cyclically-extended X.
#
# Edge case: when X is empty in JS, `B % 0 == NaN`, `X[NaN] == undefined`,
# `func_K(N[B], undefined) == F(N[B] ^ 0) == F(N[B])`. We mirror that.
def T(N, X) -> List[int]:
    Z = len(X)
    if Z == 0:
        return [F(N[B]) for B in range(len(N))]
    return [func_K(N[B], X[B % Z]) for B in range(len(N))]


# --- W(N, X): JS ~647 --------------------------------------------------
# Element-wise ADD of N with cyclically-extended X.
def W(N, X) -> List[int]:
    Z = len(X)
    if Z == 0:
        # In JS this would produce NaNs. We never hit it from the real
        # callgraph; raise so a failing test would surface clearly.
        return [F(N[B] + 0) for B in range(len(N))]
    return [kk(N[B], X[B % Z]) for B in range(len(N))]


# --- M(N): JS ~609 -----------------------------------------------------
# Returns `typeof N`. For all numeric N this is the literal string
# `"number"`. Used as a sentinel by `q` and `H` for empty-input edge
# cases (the JS code happens to silently swallow that string downstream).
def M(N) -> str:
    return "number"


# --- q(wq): JS ~613 ----------------------------------------------------
# Pad/truncate `wq` to exactly 64 bytes:
#   - empty input  -> M(64) (the "number" sentinel string).
#   - len >= 64   -> splice first 64 (mutates wq in place, JS-style).
#   - else        -> cyclically extend.
def q(wq):
    if not wq:
        return M(64)
    if len(wq) >= 64:
        result = wq[:64]
        del wq[:64]  # JS Array.prototype.splice mutates the source
        return result
    n = len(wq)
    out = [0] * 64
    for wp in range(64):
        out[wp] = wq[wp % n]
    return out


# --- H(wq): JS ~725 ----------------------------------------------------
# Zero-pad `wq` to a multiple of 64 with the original length appended as
# 4 big-endian bytes in the last 4 slots.
def H(wq):
    if not wq:
        return M(64)
    wp = len(wq)
    if wp % 64 <= 60:
        wo = 64 - (wp % 64) - 4
    else:
        wo = 128 - (wp % 64) - 4

    target_len = wp + wo + 4
    wH = list(wq) + [0] * (target_len - wp)
    suffix = _m(wp)
    for i in range(4):
        wH[wp + wo + i] = suffix[i]
    return wH


# --- func_X(wq): JS ~748 -----------------------------------------------
# Chunk a multiple-of-64 byte array into 64-byte blocks; otherwise [].
def func_X(wq) -> List[List[int]]:
    if len(wq) % 64 != 0:
        return []
    n_blocks = len(wq) // 64
    out: List[List[int]] = []
    idx = 0
    for _ in range(n_blocks):
        block = [0] * 64
        for wM in range(64):
            block[wM] = wq[idx]
            idx += 1
        out.append(block)
    return out


# --- w0..w5: JS ~766+ -- single-round byte transforms ------------------
def w0(wq, wH):
    if not wq:
        return []
    wH = F(wH)
    out = []
    for v in wq:
        out.append(func_K(v, wH))
        wH += 1
    return out


def w1(wq, wH):
    if not wq:
        return []
    wH = F(wH)
    out = []
    for v in wq:
        out.append(func_K(v, wH))
        wH -= 1
    return out


def w2(wq, wH):
    if not wq:
        return []
    wH = F(wH)
    return [wW(v, wH) for v in wq]


def w3(wq, wH):
    if not wq:
        return []
    wH = F(wH)
    out = []
    for v in wq:
        out.append(wW(v, wH))
        wH += 1
    return out


def w4(wq, wH):
    if not wq:
        return []
    wH = F(wH)
    out = []
    for v in wq:
        out.append(wW(v, wH))
        wH -= 1
    return out


def w5(wq, wH=0):
    # JS guard `wH + 256 >= 0` is always true for any F()'d value, so this
    # is effectively the identity. Preserved verbatim for byte parity.
    return wq if (wH + 256 >= 0) else []


# --- G: JS ~776 (DEAD CODE) --------------------------------------------
# Calls an undefined `wu` -- would throw ReferenceError if invoked.
# `w6`'s magic-string dispatcher never selects index 1 (which is `G`),
# so this is unreachable. Kept as a stub for fidelity.
def G(wq, wH):  # pragma: no cover
    raise NotImplementedError(
        "dun163.js function G is dead code (calls undefined `wu`)"
    )


# --- V_ws(N): JS ~841 --------------------------------------------------
# 2-char hex string -> signed byte. Same arithmetic as A(s)[0].
def V_ws(N) -> int:
    s = "" + str(N)
    return F((int(s[0], 16) << 4) + int(s[1], 16))


# --- w6(wq): JS ~848 ---------------------------------------------------
# Composite cipher round driven by a 16-char hex magic string. For each
# 4-char chunk: high byte selects a handler index, low byte is the
# handler's second arg. The shipped magic happens to dispatch only to
# {w0, w4, w2, w1}; G is never invoked.
_W6_HANDLERS = [w5, G, w2, w0, w3, w1, w4]
_W6_MAGIC = "037606da0296055c"


def w6(wq):
    out = wq
    wo = 0
    while wo < len(_W6_MAGIC):
        wM = _W6_MAGIC[wo:wo + 4]
        wg = V_ws(wM[0:2])
        wj = V_ws(wM[2:4])
        out = _W6_HANDLERS[wg](out, wj)
        wo += 4
    return out


# --- J(wq) / "jbox": JS ~863 -------------------------------------------
# 256-entry signed-byte substitution table. The hex string below is
# A()-decoded once at import; thereafter J_jbox is a single-line lookup.
_J_HEX_TABLE = (
    "a7be3f3933fa8c5fcf86c4b6908b569ba1e26c1a6d7cfbf60ae4b00e074a194d"
    "ac4b73e7f898541159a39d08183b76eedee3ed341e6685d2357440158394b1ff"
    "03a9004cbbb5ca7dcb7f41489a16e03dcc9c71eb3c9796685b1d01b4d56193a6"
    "e1f1a2470445c191ae49c5d82765dc82c350f263387a24a502fcbf442e2dddaa"
    "d0e936d9ea22b89275307b42518fbc3a626ba806d4ecd6d725f50cc8c72fefa4"
    "551ccd6fc9b2b7ab954f815c7264c6e51f4eaf99885a79892b1b60a0b3526e57"
    "ba5d178d370958847eb9fd28f9ce0bc023f4148a2adfe632126769057043d3bd"
    "8eda0df7872629f3809ef05310e83113216afe202c460fc23e789f77d1addb5e"
)
_J_BOX = A(_J_HEX_TABLE)  # length 256


def J_jbox(wq) -> List[int]:
    return [_J_BOX[int(v) & 0xFF] for v in wq]
