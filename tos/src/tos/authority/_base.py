"""Authority-local base classes (Safety Authority design §2, §3.1, §4.1)."""

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
    "AuthorityEffect",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (design §4.1)."""

    @model_validator(mode="after")
    def _all_authority_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (SA-INV-003)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(authority != enforcement — SA-INV-003; a capability grants no "
                    "runtime effect, only egress independent verification can, §1/§8.1)"
                )
        return self


class AuthorityEffect(AllFalseAuthority):
    """Runtime effect of a Safety Authority artifact — all five flags false (§4.1)."""

    is_current_authority_by_possession: bool = False
    self_transmits: bool = False
    self_mutates_capacity: bool = False
    self_releases_capacity: bool = False
    self_rearms: bool = False
