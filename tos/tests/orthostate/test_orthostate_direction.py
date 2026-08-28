"""Conservative-direction rule — weak can't reduce, increase never blocked (§6.1).

Each of the five local weak bases individually fails to reduce conservatism; a strong
basis succeeds; increasing conservatism is never blocked (even under a None basis); the
local WEAK_BASES is wider than rcl's (LOCAL_CACHE / RECOVERY_RECONNECT cannot reduce);
and the Capacity dimension delegates to rcl.transition_allowed. Off-dimension coordinates
fail closed. [STATE-EV-002 substrate — EV not claimed; EV-L2/L3 fault injection deferred]
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.orthostate import (
    WEAK_BASES,
    BrokerOrderState,
    ConservatismBasis,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
    conservative_direction_ok,
)
from tos.rcl import CapacityState, TransitionCause

_STRONG_BASES = sorted(set(ConservatismBasis) - WEAK_BASES)

# A clear conservatism reduction per local dimension (from more- to less-conservative).
_REDUCTIONS = [
    (
        StateDimension.BROKER_ORDER,
        BrokerOrderState.UNKNOWN,
        BrokerOrderState.NONE_OBSERVED,
    ),
    (StateDimension.KNOWLEDGE, KnowledgeState.CONFLICTED, KnowledgeState.RECONCILED),
    (
        StateDimension.TRANSMISSION_ATTEMPT,
        TransmissionAttemptState.SENT_UNCONFIRMED,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
    ),
    (StateDimension.INTENT, IntentState.PROPOSED, IntentState.APPROVED),
]

# A clear conservatism increase per local dimension (from less- to more-conservative).
_INCREASES = [
    (
        StateDimension.BROKER_ORDER,
        BrokerOrderState.NONE_OBSERVED,
        BrokerOrderState.UNKNOWN,
    ),
    (StateDimension.KNOWLEDGE, KnowledgeState.RECONCILED, KnowledgeState.CONFLICTED),
    (
        StateDimension.TRANSMISSION_ATTEMPT,
        TransmissionAttemptState.SEND_FAILED_PROVEN,
        TransmissionAttemptState.SEND_STARTED,
    ),
    (StateDimension.INTENT, IntentState.APPROVED, IntentState.DENIED),
]


@pytest.mark.parametrize(
    "dimension,frm,to", _REDUCTIONS, ids=lambda x: getattr(x, "value", x)
)
@pytest.mark.parametrize("weak", sorted(WEAK_BASES))
def test_weak_basis_cannot_reduce_conservatism(
    dimension: StateDimension, frm: object, to: object, weak: ConservatismBasis
) -> None:
    """(canary §11) None of the five weak bases may reduce conservatism on any dimension."""
    assert conservative_direction_ok(dimension, frm, to, weak) is False


@pytest.mark.parametrize("dimension,frm,to", _REDUCTIONS)
def test_none_basis_cannot_reduce_conservatism(
    dimension: StateDimension, frm: object, to: object
) -> None:
    """(canary fail-closed) A None basis is treated as weak — it cannot reduce conservatism."""
    assert conservative_direction_ok(dimension, frm, to, None) is False


@pytest.mark.parametrize("dimension,frm,to", _REDUCTIONS)
def test_strong_basis_may_reduce_conservatism(
    dimension: StateDimension, frm: object, to: object
) -> None:
    """(guard True side) A strong (non-weak) basis IS permitted to reduce conservatism."""
    assert (
        conservative_direction_ok(
            dimension, frm, to, ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE
        )
        is True
    )


@pytest.mark.parametrize("dimension,frm,to", _INCREASES)
@pytest.mark.parametrize(
    "basis",
    [
        None,
        ConservatismBasis.TIMEOUT,
        ConservatismBasis.LOCAL_CACHE,
        ConservatismBasis.AUTHORITY_DECISION,
    ],
)
def test_increasing_conservatism_never_blocked(
    dimension: StateDimension, frm: object, to: object, basis
) -> None:
    """(§11 line 177) Increasing conservatism is always permitted — even under weak / None basis."""
    assert conservative_direction_ok(dimension, frm, to, basis) is True


def test_local_cache_and_recovery_reconnect_cannot_reduce() -> None:
    """(canary §0.4c) The two bases rcl lacks (LOCAL_CACHE / RECOVERY_RECONNECT) cannot reduce."""
    for weak in (ConservatismBasis.LOCAL_CACHE, ConservatismBasis.RECOVERY_RECONNECT):
        assert (
            conservative_direction_ok(
                StateDimension.BROKER_ORDER,
                BrokerOrderState.UNKNOWN,
                BrokerOrderState.NONE_OBSERVED,
                weak,
            )
            is False
        )


def test_collapse_unknown_to_none_observed_blocked_under_weak() -> None:
    """(canary §11 line 173) Collapsing Broker UNKNOWN -> NONE_OBSERVED under weak basis is blocked."""
    assert (
        conservative_direction_ok(
            StateDimension.BROKER_ORDER,
            BrokerOrderState.UNKNOWN,
            BrokerOrderState.NONE_OBSERVED,
            ConservatismBasis.ABSENCE,
        )
        is False
    )


# ---------------------------------------------------------------------------
# Capacity delegates to rcl.transition_allowed
# ---------------------------------------------------------------------------


def test_capacity_delegates_to_rcl_transition_allowed() -> None:
    """(§6.1b) Capacity conservatism is the rcl lattice: RELEASED only under FINAL_QUANTITY_PROOF."""
    assert (
        conservative_direction_ok(
            StateDimension.CAPACITY,
            CapacityState.POSITION_CONSUMED,
            CapacityState.RELEASED,
            TransitionCause.TIMEOUT,
        )
        is False
    )
    assert (
        conservative_direction_ok(
            StateDimension.CAPACITY,
            CapacityState.POSITION_CONSUMED,
            CapacityState.RELEASED,
            TransitionCause.FINAL_QUANTITY_PROOF,
        )
        is True
    )


def test_capacity_requires_rcl_transition_cause() -> None:
    """(fail-closed) Capacity with a non-TransitionCause basis (None / ConservatismBasis) is False."""
    assert (
        conservative_direction_ok(
            StateDimension.CAPACITY,
            CapacityState.QUARANTINED_UNKNOWN,
            CapacityState.POTENTIALLY_LIVE,
            None,
        )
        is False
    )
    assert (
        conservative_direction_ok(
            StateDimension.CAPACITY,
            CapacityState.QUARANTINED_UNKNOWN,
            CapacityState.POTENTIALLY_LIVE,
            ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE,
        )
        is False
    )


def test_off_dimension_coordinate_fails_closed() -> None:
    """(fail-closed) A coordinate not belonging to the dimension is rejected."""
    assert (
        conservative_direction_ok(
            StateDimension.BROKER_ORDER,
            IntentState.PROPOSED,  # wrong dimension's value
            BrokerOrderState.UNKNOWN,
            ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE,
        )
        is False
    )


@given(
    frm=st.sampled_from(list(BrokerOrderState)),
    to=st.sampled_from(list(BrokerOrderState)),
    basis=st.sampled_from(sorted(WEAK_BASES)),
)
def test_property_weak_never_reduces_broker(frm, to, basis) -> None:
    """(property) On Broker, a weak basis is allowed iff the move does not reduce conservatism."""
    from tos.orthostate.predicates import _BROKER_CONSERVATISM_RANK as rank

    allowed = conservative_direction_ok(StateDimension.BROKER_ORDER, frm, to, basis)
    is_increase_or_hold = rank[to] >= rank[frm]
    assert allowed is is_increase_or_hold
