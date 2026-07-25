"""spg-local base re-export shim (design #12 §0.4d/§2.1/§3.1).

The generic digest-binding substrate (``FrozenModel``, ``DigestBoundArtifact``,
``IndependentIdArtifact``, ``ArtifactStatus``, ``ArtifactIntegrityError``) is REUSED
verbatim from :mod:`tos.canonical` (design #12 §3.1 — "재정의 금지"). ``tos.spg`` authors
**no** new base class: its five digest-bound citizens — the append-only,
generation-immutable ``HardSafetyEnvelope`` / ``RuntimeSafetyProfile`` /
``SafetyConfigurationBundle`` / ``ActivationRecord`` / ``ConsumerCompatibilityManifest`` —
are each an :class:`~tos.canonical.IndependentIdArtifact` (governance-assigned identity,
``id != f(digest)``, so a same-id / different-bytes re-issuance / forgery of a generation
stays a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``; design #12 §2.1/§2.3/
§3.1). This module is a thin re-export shim (the ``tos.brokercap._base`` / ``tos.rcl._base``
/ ``tos.authority._base`` precedent — **no** new sibling import edge), so
``from tos.spg._base import IndependentIdArtifact`` reads locally while the definition
stays single-sourced in the core.

spg has **no** authority block: an envelope / profile / bundle / activation record /
validation verdict is a **non-transmitting, non-enforcing representation** (design #12
§4.5; SPG-INV-014 line 205 "Approval records, signatures, logs, diffs, dashboards, review
tickets, and replay evidence do not create activation, capacity, Live Authorization, or
transmission authority"). It holds no egress / capacity-mutation / authorization-issue /
activation-commit method at all — representation != enforcement.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``, no other
sibling ``tos.*`` package (design #12 §0.3).
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
