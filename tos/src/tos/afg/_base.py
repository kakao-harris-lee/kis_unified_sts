"""afg-local base re-export shim + all-false governor authority (design #16 §0.4e)."""

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
    "AllFalseActionFlowAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseActionFlowAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #16 §0.4e)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseActionFlowAuthority:
        """Reject construction if any authority flag is ``True`` (AFG-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(decision != authority — AFG-INV-011; a GRANT is not capacity or "
                    "permission to send, and a permit is not a Transmission Capability)"
                )
        return self
