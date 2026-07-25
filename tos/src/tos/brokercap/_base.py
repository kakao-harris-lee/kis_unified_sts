"""Brokercap-local base re-export shim (design #10 §0.4d/§2.1/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``IndependentIdArtifact``,
``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED verbatim from
:mod:`tos.canonical` (design #10 §3.1 — "재정의 금지"). ``tos.brokercap`` authors **no**
new base class: its one digest-bound citizen — the append-only, version-immutable
``BrokerCapabilityProfile`` — is an :class:`~tos.canonical.IndependentIdArtifact`
(governance-assigned identity, ``id != f(digest)``, so a same-id / different-bytes
re-issuance / forgery of a profile version stays a detectable ``classify_record_pair``
``CRITICAL_CONFLICT``; design #10 §2.1/§2.3/§3.1). This module is a thin re-export shim
(the ``tos.recon._base`` / ``tos.liveauth._base`` / ``tos.rcl._base`` precedent — **no**
new sibling import edge), so ``from tos.brokercap._base import IndependentIdArtifact``
reads locally while the definition stays single-sourced in the core.

Brokercap has **no** authority block (no ``AllFalseAuthority`` counterpart): a profile /
declaration / admissibility verdict is a **non-transmitting, non-enforcing
representation** (design #10 §4.5). It holds no egress / capacity-mutation /
authorization-issue / KnowledgeState-set flag at all — representation != enforcement (ADR
§19/§27; §17.5 line 947 "supplies evidence and constraints but creates no action-flow
capacity").

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no other
sibling ``tos.*`` package (design #10 §0.3).
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
