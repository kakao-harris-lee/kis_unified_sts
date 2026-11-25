"""Authority-effect blocks + non-authoritative grant/decision reference (§4.1)."""

from __future__ import annotations

from tos.rcl._base import AllFalseAuthority, FrozenModel


class RclAuthorityEffect(AllFalseAuthority):
    """Authority effect of a grant / decision / capability / snapshot — all false."""

    creates_capacity: bool = False
    may_mutate_live_state: bool = False
    may_release_capacity: bool = False
    permits_broker_transmission: bool = False
    may_rearm: bool = False


class GrantDecisionRef(FrozenModel):
    """Non-authoritative Aggregate Risk / Action Flow decision reference (§4.1)."""

    decision_id: str | None = None
    decision_generation: int | None = None
    canonical_decision_digest: str | None = None
    bound_reservation_revision: int | None = None
    bound_reservation_digest: str | None = None
    bound_generation: int | None = None
    authority_effect: RclAuthorityEffect = RclAuthorityEffect()
