"""Engine-local base — reused canonical substrate + the Coordinator all-false authority block."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    derive_id,
    get_scheme,
)

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "COORDINATOR_SHALL_NOT_FLAGS",
    "AllFalseCoordinatorAuthority",
    "FrozenModel",
    "derive_id",
    "get_scheme",
]


COORDINATOR_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "originates_approves_or_widens_authority",
    "mutates_risk_capacity_ledger",
    "constructs_broker_command",
    "issues_or_reuses_transmission_capability",
    "bypasses_currentness",
    "treats_timeout_as_rejection",
    "creates_aggregate_exposure_via_retry",
    "exceeds_action_flow_budget",
    "asserts_venue_or_session_state",
    "self_classifies_protective",
    "treats_tca_as_authority",
)


class AllFalseCoordinatorAuthority(FrozenModel):
    """Coordinator authority block — every flag forced ``false`` (design #31 §4.3)."""

    originates_approves_or_widens_authority: bool = False
    mutates_risk_capacity_ledger: bool = False
    constructs_broker_command: bool = False
    issues_or_reuses_transmission_capability: bool = False
    bypasses_currentness: bool = False
    treats_timeout_as_rejection: bool = False
    creates_aggregate_exposure_via_retry: bool = False
    exceeds_action_flow_budget: bool = False
    asserts_venue_or_session_state: bool = False
    self_classifies_protective: bool = False
    treats_tca_as_authority: bool = False

    @model_validator(mode="after")
    def _all_coordinator_authority_false(self) -> AllFalseCoordinatorAuthority:
        """Reject construction if any ``SHALL NOT`` flag is ``True`` (design #31 §4.3)."""
        for name in COORDINATOR_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Execution Coordinator is "
                    "a pure requester/sequencer and holds no authority (RFC-002 §9.1:557, "
                    "§10.7:722/:724; RFC-005 §12:346-377)"
                )
        return self
