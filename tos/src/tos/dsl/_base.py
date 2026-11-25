"""DSL-local base classes (design 2026-07-21-tos-strategy-dsl-design §2.5)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IdDerivedArtifact,
    IndependentIdArtifact,
    derive_id,
)

__all__ = [
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DecisionContextCapsuleRef",
    "DigestBoundArtifact",
    "FrozenModel",
    "IdDerivedArtifact",
    "IndependentIdArtifact",
    "derive_id",
]


_AUTHORITY_FLAGS: tuple[str, ...] = (
    "grants_approval",
    "creates_intent",
    "mutates_capacity",
    "creates_live_authorization",
    "creates_protective_classification",
    "creates_transmission_capability",
    "permits_broker_transmission",
    "clears_halt",
    "permits_rearm",
    "permits_automatic_rearm",
)


class AllFalseAuthority(FrozenModel):
    """Authored-artifact authority block — every flag forced ``false`` (design §2.5)."""

    grants_approval: bool = False
    creates_intent: bool = False
    mutates_capacity: bool = False
    creates_live_authorization: bool = False
    creates_protective_classification: bool = False
    creates_transmission_capability: bool = False
    permits_broker_transmission: bool = False
    clears_halt: bool = False
    permits_rearm: bool = False
    permits_automatic_rearm: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (SOS-INV-005)."""
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — an authored "
                    "artifact is a candidate only, it grants no authority "
                    "(RFC-008 §8/§11; SOS-INV-005)"
                )
        return self


class DecisionContextCapsuleRef(FrozenModel):
    """Content-addressed bind to the consumed Decision Context Capsule (design §2.2)."""

    capsule_id: str | None = None
    canonical_digest: str | None = None
