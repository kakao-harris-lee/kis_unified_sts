"""Recon-local base re-export shim (design #9 §0.4d/§2.1).

The generic digest-binding substrate (``FrozenModel``, ``IndependentIdArtifact``,
``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED verbatim from
:mod:`tos.canonical` (design #9 §3.1 — "재정의 금지"). ``tos.recon`` authors **no**
new base class: its one digest-bound citizen — the append-only
``FieldReconciliationAssessment`` — is an :class:`~tos.canonical.IndependentIdArtifact`
(service-assigned identity, ``id != f(digest)``, so a same-id / different-bytes
re-submission of a reconciliation run stays a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``; design #9 §2.1/§3.1). This module is a
thin re-export shim (the ``tos.rcl._base`` / ``tos.dsl._base`` precedent — no new
sibling import edge), so ``from tos.recon._base import IndependentIdArtifact`` reads
locally while the definition stays single-sourced in the core.

Recon has **no** authority block (no ``AllFalseAuthority`` counterpart): recon
representation is confidence + bounds + proof bools, and it holds no capacity-mutation
or transition-authority flags at all (representation != mutation — design #9 §4.7).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no
sibling ``tos.*`` package (design #9 §0.3).
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
