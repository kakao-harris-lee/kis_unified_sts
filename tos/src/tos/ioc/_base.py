"""ioc-local base re-export shim + all-false construction-authority base (design #14 §0.4d)."""

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
    "AllFalseConstructionAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseConstructionAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design #14 §0.4d)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseConstructionAuthority:
        """Reject construction if any authority flag is ``True`` (IOC-INV-011)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(construction != authority — IOC-INV-011; order construction cannot "
                    "approve, mutate capacity, issue authority, classify protection, choose "
                    "admissibility, transmit, clear HALT, or re-arm)"
                )
        return self
