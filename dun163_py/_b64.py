"""
dun163_py._b64
==============

Custom base64 encoder ported from dun163.js. Differs from RFC 4648 in
two ways:

* Uses an obfuscated 64-char alphabet
  ("MB.CfHUzEeJpsuGkgNwhqiSaI4Fd9L6jYKZAxn1/Vml0c5rbXRP+8tD3QTO2vWyo")
  instead of "A-Za-z0-9+/".
* Pads with the literal character "7" instead of "=".

Otherwise the bit-packing is identical to standard base64.

Public:
    F_ka(q, H, M)  -- encode 1..3 bytes into 4 chars (with padding).
    k_A(q, H, M)   -- chunked driver over an arbitrarily sized byte list.
    A_wL(q, H=None, M=None) -- top-level wrapper with default alphabet/pad.

The byte inputs may be signed (-128..127); the encoder masks each value
with 0xFF before shifting to match JS unsigned shift semantics.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

DEFAULT_ALPHABET = list(
    "MB.CfHUzEeJpsuGkgNwhqiSaI4Fd9L6jYKZAxn1/Vml0c5rbXRP+8tD3QTO2vWyo"
)
DEFAULT_PADDING = "7"


def F_ka(q, H, M) -> str:
    """Encode 1..3 bytes into 4 alphabet chars, padding to 4 with M.

    Returns "" for any other input length (matches the JS default branch).
    """
    n = len(q)
    if n == 1:
        j = int(q[0]) & 0xFF
        N = X = 0
        return (
            H[(j >> 2) & 0x3F]
            + H[((j << 4) & 0x30) + ((N >> 4) & 0x0F)]
            + M
            + M
        )
    if n == 2:
        j = int(q[0]) & 0xFF
        N = int(q[1]) & 0xFF
        X = 0
        return (
            H[(j >> 2) & 0x3F]
            + H[((j << 4) & 0x30) + ((N >> 4) & 0x0F)]
            + H[((N << 2) & 0x3C) + ((X >> 6) & 0x03)]
            + M
        )
    if n == 3:
        j = int(q[0]) & 0xFF
        N = int(q[1]) & 0xFF
        X = int(q[2]) & 0xFF
        return (
            H[(j >> 2) & 0x3F]
            + H[((j << 4) & 0x30) + ((N >> 4) & 0x0F)]
            + H[((N << 2) & 0x3C) + ((X >> 6) & 0x03)]
            + H[X & 0x3F]
        )
    return ""


def k_A(q, H, M) -> str:
    """Walk `q` in 3-byte chunks; F_ka each; concatenate."""
    if not q:
        return ""
    out = []
    j = 0
    n = len(q)
    while j < n:
        if j + 3 > n:
            out.append(F_ka(q[j:], H, M))
            break
        out.append(F_ka(q[j:j + 3], H, M))
        j += 3
    return "".join(out)


def A_wL(q, H: Optional[Sequence[str]] = None, M: Optional[str] = None) -> str:
    alphabet = list(H) if H is not None else DEFAULT_ALPHABET
    padding = M if M is not None else DEFAULT_PADDING
    return k_A(q, alphabet, padding)
