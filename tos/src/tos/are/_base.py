"""are-local base re-export shim + all-false authority base (design #13 §0.4d)."""

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
    "AllFalseAggregateAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseAggregateAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #13 §0.4d)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAggregateAuthority:
        """Reject construction if any authority flag is ``True`` (ARE-INV-009)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(capacity != authority — ARE-INV-009; a GRANT is not capacity, "
                    "Live Authorization, a Transmission Capability, or broker permission)"
                )
        return self
