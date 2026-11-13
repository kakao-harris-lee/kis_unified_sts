"""venue-local base re-export shim + all-false venue-gate authority (design #19 §2 / §3.1)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "VenueGateAuthorityEffect",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class VenueGateAuthorityEffect(FrozenModel):
    """Authority effect of a venue-gate artifact — every flag forced ``false`` (VTG-INV-011)."""

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> VenueGateAuthorityEffect:
        """Reject construction if any authority flag is ``True`` (VTG-INV-011 line 189)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(admissibility != authority — VTG-INV-011 line 189; a Venue Constraint "
                    "Gate cannot approve, mutate capacity, issue authority, classify "
                    "protection, transmit, clear HALT, or re-arm — an Order Admissibility "
                    "Decision is a safety fact, not permission, §1 line 21-23)"
                )
        return self
