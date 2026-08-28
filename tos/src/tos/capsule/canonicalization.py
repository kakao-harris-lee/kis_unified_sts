"""Re-export shim: canonicalization promoted to :mod:`tos.canonical` (design #4 §3.1).

The canonicalization + digest contract was promoted to ``tos.canonical`` so that
``tos.capsule`` and ``tos.evidence`` share one digest-binding substrate without
importing each other (design #4 §0.4/§3.1). This module preserves the existing
``from tos.capsule.canonicalization import ...`` import path (design #1 §3.4
re-export-shim precedent) — including the private ``_encode``/``_num_token``
helpers the property tests reference. It adds no behavior of its own.
"""

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
