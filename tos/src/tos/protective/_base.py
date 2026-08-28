"""Protective-local base re-export shim (design #11 §0.4d/§2.1/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``IndependentIdArtifact``,
``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED verbatim from :mod:`tos.canonical`
(design #11 §3.1 — "재정의 금지"). ``tos.protective`` authors **no** new base class: its one
digest-bound citizen — the append-only, version-immutable ``ProtectiveCapacityProfile`` — is
an :class:`~tos.canonical.IndependentIdArtifact` (governance-assigned identity, ``id !=
f(digest)``, so a same-id / different-bytes re-issuance / forgery of a profile version stays a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; design #11 §2.1/§2.3/§3.1). This
module is a thin re-export shim (the ``tos.brokercap._base`` / ``tos.rcl._base`` /
``tos.authority._base`` precedent — **no** new sibling import edge), so ``from
tos.protective._base import IndependentIdArtifact`` reads locally while the definition stays
single-sourced in the core.

Protective has **no** authority / enforcement block: a profile / declaration / verdict is a
**non-transmitting, non-enforcing representation** (design #11 §4.5; ADR §5 line 241 "It SHALL
NOT enlarge aggregate authority, mutate the Risk Capacity Ledger outside its defined
transition interface, or transmit directly"). It holds no egress / capacity-mutation /
authorization-issue / mode-set / capacity-release method at all — representation !=
enforcement.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no other
sibling ``tos.*`` package (design #11 §0.3).
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
