"""Capsule base shim + capsule-local blocks (design #4 §3.1 PROMOTE).

The generic digest-binding substrate (``FrozenModel``, ``ArtifactStatus``,
``derive_id``, the digest/id-verification base classes, and the integrity-error
type) was promoted to :mod:`tos.canonical` so ``tos.capsule`` and ``tos.evidence``
share it without importing each other (design #4 §0.4/§3.1). This module:

* re-exports the promoted substrate so existing ``from tos.capsule._base import
  ...`` paths are unchanged;
* aliases ``CapsuleIntegrityError = ArtifactIntegrityError`` (design #4 §9.1 —
  the rename is generalized in ``tos.canonical``; the capsule name is preserved);
* keeps the **capsule-local** authority / policy-reference blocks
  (``SnapshotAuthority`` / ``CapsuleAuthority`` / ``PolicyRef``), which are
  capsule-specific and stay here (design #4 §3.1 "잔류").

Capsule and snapshot are immutable content-addressed artifacts, so they inherit
:class:`~tos.canonical.IdDerivedArtifact` (``id = f(digest)``).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IdDerivedArtifact,
    derive_id,
)

#: Capsule-scoped alias for the promoted integrity error (design #4 §9.1). The
#: rename to ``ArtifactIntegrityError`` is generalized in ``tos.canonical``; the
#: capsule name is preserved so existing imports and semantics are unchanged.
CapsuleIntegrityError = ArtifactIntegrityError

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CapsuleAuthority",
    "CapsuleIntegrityError",
    "DigestBoundArtifact",
    "FrozenModel",
    "IdDerivedArtifact",
    "PolicyRef",
    "SnapshotAuthority",
    "derive_id",
]


class SnapshotAuthority(FrozenModel):
    """Snapshot authority block — every flag forced ``false`` (design §4.4).

    Matches ``CRITICAL-INPUT-SNAPSHOT-template.yaml`` lines 44-50. The pure-model
    realization of CII-INV-011: this kernel grants no authority. A ``True`` value
    makes the artifact unconstructable (the full "no authority path anywhere"
    proof is EV-L2/L3, design §0.2/§4.4).
    """

    grants_approval: bool = False
    creates_capacity: bool = False
    creates_live_authorization: bool = False
    creates_protective_classification: bool = False
    permits_broker_transmission: bool = False
    permits_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> SnapshotAuthority:
        """Reject construction if any authority flag is ``True`` (CII-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise CapsuleIntegrityError(
                    f"{type(self).__name__}.{name} must be false (CII-INV-011)"
                )
        return self


class CapsuleAuthority(SnapshotAuthority):
    """Capsule authority block (adds ``permits_automatic_rearm``; design §4.4).

    Matches ``DECISION-CONTEXT-CAPSULE-template.yaml`` lines 75-82.
    """

    permits_automatic_rearm: bool = False


class PolicyRef(FrozenModel):
    """Reference to a governing Critical Input Policy (design §2.6/§2.7).

    Matches the ``critical_input_policy`` block in both templates: a content
    reference only (id + generation + digest), never the policy body.
    """

    policy_id: str | None = None
    policy_generation: int | None = None
    canonical_digest: str | None = None
