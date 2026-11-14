"""RCL-local base classes (RCL design §2, §3.1, §4.1)."""

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
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.1)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (RCLP-INV-001)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(capacity != authority — RCLP-INV-001/012; only a committed "
                    "RCL transition may mutate capacity)"
                )
        return self
