"""Orthostate-local base classes (design #8 §2, §2.1; ADR-002-005 §1/§14).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #8 §0.4d/§3.1 — "재정의 금지"; **PROMOTE
0건**: ``IndependentIdArtifact`` is already core from design #6). This module is a
**thin re-export shim** (the ``tos.rcl._base`` / ``tos.liveauth._base`` /
``tos.dsl._base`` pattern — no new sibling import edge) so
``from tos.orthostate._base import ...`` paths resolve without re-defining anything.

Unlike the authority / capacity / live-authorization packages, orthostate defines
**no** ``AllFalseAuthority`` block: a :class:`CompositeState` / transition record is a
non-transmitting *state observation*, not an authority artifact. The
"representation ≠ effect" invariant (design #8 §4.6; ADR-002-005 §12 line 191 "Cross-
dimension effects occur only through the owning authority's defined transition") is
realized by the **structural absence** of any dimension-mutation method on the records,
not by an authority-flag block — so no all-false layer is needed here.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no
``tos.rcl`` beyond the sibling capacity edge in ``records`` / ``predicates`` (design
#8 §0.3).
"""

from __future__ import annotations

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]
