"""cur-local base re-export shim + all-false currentness authority effect (design #23 §2/§3.1)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)

__all__ = [
    "AllFalseCurrentnessAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
]


class AllFalseCurrentnessAuthority(FrozenModel):
    """Authority effect of a currentness artifact — every flag forced ``false`` (CUR-INV-005; §6.13)."""

    approves: bool = False
    mutates_capacity: bool = False
    releases_capacity: bool = False
    issues_authority: bool = False
    issues_capability: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    re_arms: bool = False

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseCurrentnessAuthority:
        """Reject construction if any authority flag is ``True`` (CUR-INV-005; §6.13)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(currentness != authority — CUR-INV-005 / ADR-002-024 §1 line 21 / §6.13; a "
                    "Safety Currentness Vector / Egress Currentness Proof / Restrictive Fence "
                    "Record / Currentness Policy cannot approve, mutate or release capacity, issue "
                    "authority or capability, classify protection, transmit, clear a HALT, or "
                    "re-arm — it is verified ordering data, not permission)"
                )
        return self
