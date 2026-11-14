"""Capsule base shim + capsule-local blocks (design #4 §3.1 PROMOTE)."""

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
    """Snapshot authority block — every flag forced ``false`` (design §4.4)."""

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
    """Capsule authority block (adds ``permits_automatic_rearm``; design §4.4)."""

    permits_automatic_rearm: bool = False


class PolicyRef(FrozenModel):
    """Reference to a governing Critical Input Policy (design §2.6/§2.7)."""

    policy_id: str | None = None
    policy_generation: int | None = None
    canonical_digest: str | None = None
