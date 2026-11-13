"""Re-export shim: canonicalization promoted to :mod:`tos.canonical` (design #4 §3.1)."""

from __future__ import annotations

from tos.canonical.canonicalization import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    DigestFactory,
    EVL1ProvisionalCanonicalizer,
    _encode,
    _num_token,
    get_scheme,
    register_scheme,
)

__all__ = [
    "EV_L1_PROVISIONAL_VERSION",
    "CanonicalizationScheme",
    "DigestFactory",
    "EVL1ProvisionalCanonicalizer",
    "_encode",
    "_num_token",
    "get_scheme",
    "register_scheme",
]
