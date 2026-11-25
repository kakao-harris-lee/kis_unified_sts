"""egressgw-local base — reused canonical substrate + the two all-false authority blocks."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    IndependentIdArtifact,
    derive_id,
    get_scheme,
)

__all__ = [
    "CONSTRUCTION_SHALL_NOT_FLAGS",
    "EV_L1_PROVISIONAL_VERSION",
    "GATEWAY_SHALL_NOT_FLAGS",
    "AllFalseConstructionCoordinatorAuthority",
    "AllFalseGatewayAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "FrozenModel",
    "IndependentIdArtifact",
    "derive_id",
    "get_scheme",
]


def _positive(flag: bool | None) -> bool:
    """Positive-polarity read of an injected stand-in flag (``None`` / ``False`` ⇒ not admitted)."""
    return flag is True


CONSTRUCTION_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "approves",
    "mutates_capacity",
    "classifies_protection",
    "issues_authority",
    "transmits",
    "arms_live_scope",
)

GATEWAY_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "approves",
    "mutates_capacity",
    "issues_authority",
    "classifies_protection",
    "chooses_admissibility",
    "arms_live_scope",
    "clears_halt",
    "rearms",
    "widens_authority",
)


class AllFalseConstructionCoordinatorAuthority(FrozenModel):
    """Order Construction authority block — every flag forced ``false`` (design #34 §3.3)."""

    approves: bool = False
    mutates_capacity: bool = False
    classifies_protection: bool = False
    issues_authority: bool = False
    transmits: bool = False
    arms_live_scope: bool = False

    @model_validator(mode="after")
    def _all_construction_authority_false(
        self,
    ) -> AllFalseConstructionCoordinatorAuthority:
        """Reject construction if any RFC-002 §9.1:553 flag is ``True``."""
        for name in CONSTRUCTION_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Order Construction "
                    "Service approves nothing, mutates no capacity, classifies no protection, "
                    "issues no authority, transmits nothing, and arms no live scope "
                    "(RFC-002 §9.1:553; design #34 §3.3)"
                )
        return self


class AllFalseGatewayAuthority(FrozenModel):
    """Broker Egress Gateway authority block — every flag forced ``false`` (design #34 §4)."""

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    chooses_admissibility: bool = False
    arms_live_scope: bool = False
    clears_halt: bool = False
    rearms: bool = False
    widens_authority: bool = False

    @model_validator(mode="after")
    def _all_gateway_authority_false(self) -> AllFalseGatewayAuthority:
        """Reject construction if any gateway ``SHALL NOT`` flag is ``True``."""
        for name in GATEWAY_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Broker Egress Gateway "
                    "is a final enforcement point, not an authority: it approves nothing, "
                    "mutates no capacity, issues no authority, and re-arms nothing "
                    "(ADR-002-013 §1; RFC-005 §12:352-373; design #34 §4)"
                )
        return self
