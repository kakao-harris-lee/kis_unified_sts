"""iap-local base re-export shim + all-false approval-authority base (design #15 §2.1)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)

__all__ = [
    "AllFalseApprovalAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseApprovalAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #15 §2.1 / §7)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseApprovalAuthority:
        """Reject construction if any authority flag is ``True`` (IAP-INV-005 line 150)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(approval != authority — IAP-INV-005; Independent Approval cannot "
                    "mutate capacity, create headroom, issue authority, classify protection, "
                    "transmit, clear HALT, or re-arm)"
                )
        return self
