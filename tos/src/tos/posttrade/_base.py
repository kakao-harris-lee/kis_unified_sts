"""posttrade-local base re-export shim + all-false consequence (design #24 §0.4f/§3.1)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    FrozenModel,
    IndependentIdArtifact,
)

__all__ = [
    "AllFalsePostTradeConsequence",
    "ArtifactStatus",
    "FrozenModel",
    "IndependentIdArtifact",
]


class AllFalsePostTradeConsequence(FrozenModel):
    """Consequence of any post-trade label / record / proof — every flag false (§4.7)."""

    releases_capacity: bool = False
    makes_cash_available: bool = False
    proves_legal_title: bool = False
    grants_permission: bool = False
    authorizes_transmission: bool = False

    @model_validator(mode="after")
    def _all_consequences_false(self) -> AllFalsePostTradeConsequence:
        """Reject construction if any consequence flag is ``True`` (§10 line 312)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(finality proves the LEG, not the CONSEQUENCE — ADR-002-030 §10 "
                    "line 312: no lifecycle state creates capacity release, available "
                    "cash, legal title, or permission)"
                )
        return self
