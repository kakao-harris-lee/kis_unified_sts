"""Conservative restart reconstruction — never RECONCILED; monotone conservatism (§6.3; §13).

Attempt at SEND_STARTED+ forces Capacity to at least POTENTIALLY_LIVE (preserving a
more-conservative value); a non-terminal Broker becomes UNKNOWN; Knowledge is re-derived
so RECONCILED is structurally unreachable in the output — over ARBITRARY inputs the
projection never yields RECONCILED and never yields a less-conservative composite.
[STATE-EV-004 substrate — real durable reload / Recovery Barrier are EV-L3, deferred]
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.orthostate import (
    BrokerOrderState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.orthostate.predicates import (
    _ATTEMPT_CONSERVATISM_RANK,
    _BROKER_CONSERVATISM_RANK,
    _KNOWLEDGE_CONSERVATISM_RANK,
)
from tos.rcl import CapacityState, capacity_at_least_as_conservative

from ._orthostate_strategies import composites, issue_composite

_A = TransmissionAttemptState
_B = BrokerOrderState
_K = KnowledgeState


def _pre(**dims: object):
    base: dict[str, object] = {
        "intent_state": IntentState.ACTIVE,
        "transmission_attempt_state": _A.CAPABILITY_ISSUED,
        "broker_order_state": _B.WORKING,
        "knowledge_state": _K.CONSISTENT,
        "capacity_state": CapacityState.ATTEMPT_BOUND,
    }
    base.update(dims)
    return issue_composite(**base)


@pytest.mark.parametrize(
    "attempt",
    [_A.SEND_STARTED, _A.SENT_UNCONFIRMED, _A.ACK_OBSERVED, _A.SUPERSEDED],
)
def test_send_started_forces_potentially_live(
    attempt: TransmissionAttemptState,
) -> None:
    """(§13 line 198) An attempt that reached SEND_STARTED forces Capacity >= POTENTIALLY_LIVE."""
    post = reconstruct_conservative(
        _pre(
            transmission_attempt_state=attempt,
            capacity_state=CapacityState.ATTEMPT_BOUND,
        )
    )
    assert capacity_at_least_as_conservative(
        post.capacity_state, CapacityState.POTENTIALLY_LIVE
    )


def test_more_conservative_capacity_is_preserved() -> None:
    """(§13) A capacity already more conservative than POTENTIALLY_LIVE is preserved, not lowered."""
    post = reconstruct_conservative(
        _pre(
            transmission_attempt_state=_A.SEND_STARTED,
            capacity_state=CapacityState.QUARANTINED_UNKNOWN,
        )
    )
    assert post.capacity_state is CapacityState.QUARANTINED_UNKNOWN


def test_send_failed_proven_does_not_force_potentially_live() -> None:
    """(§13) SEND_FAILED_PROVEN is proven-not-live and does not force POTENTIALLY_LIVE."""
    post = reconstruct_conservative(
        _pre(
            transmission_attempt_state=_A.SEND_FAILED_PROVEN,
            capacity_state=CapacityState.ATTEMPT_BOUND,
        )
    )
    assert post.capacity_state is CapacityState.ATTEMPT_BOUND


@pytest.mark.parametrize(
    "broker", [_B.NONE_OBSERVED, _B.WORKING, _B.PARTIALLY_FILLED, _B.CANCEL_PENDING]
)
def test_non_terminal_broker_becomes_unknown(broker: BrokerOrderState) -> None:
    """(§13 line 198) A non-terminal Broker order is reconstructed as UNKNOWN."""
    post = reconstruct_conservative(_pre(broker_order_state=broker))
    assert post.broker_order_state is _B.UNKNOWN


@pytest.mark.parametrize("broker", [_B.FILLED, _B.CANCELLED, _B.REJECTED, _B.EXPIRED])
def test_terminal_broker_is_preserved(broker: BrokerOrderState) -> None:
    """(§13) A structurally terminal Broker order is preserved across restart."""
    # Use ACK_OBSERVED + a matching capacity so no unrelated dimension changes the point.
    post = reconstruct_conservative(
        _pre(transmission_attempt_state=_A.ACK_OBSERVED, broker_order_state=broker)
    )
    assert post.broker_order_state is broker


def test_reconciled_knowledge_is_downgraded() -> None:
    """(canary §13 line 199) A RECONCILED input never survives — it is re-derived to CONFLICTED."""
    post = reconstruct_conservative(_pre(knowledge_state=_K.RECONCILED))
    assert post.knowledge_state is _K.CONFLICTED
    assert post.knowledge_state is not _K.RECONCILED


def test_consistent_knowledge_is_downgraded() -> None:
    """(§13 §11 line 175) Positive CONSISTENT knowledge is not carried across a restart."""
    post = reconstruct_conservative(_pre(knowledge_state=_K.CONSISTENT))
    assert post.knowledge_state is _K.CONFLICTED


def test_intent_and_attempt_preserved() -> None:
    """(§13) Restart re-derives Broker / Knowledge / Capacity; Intent and Attempt are preserved."""
    post = reconstruct_conservative(
        _pre(
            intent_state=IntentState.ACTIVE,
            transmission_attempt_state=_A.SENT_UNCONFIRMED,
        )
    )
    assert post.intent_state is IntentState.ACTIVE
    assert post.transmission_attempt_state is _A.SENT_UNCONFIRMED


@given(pre=composites())
def test_reconstruct_never_outputs_reconciled(pre) -> None:
    """(canary property §6.3) Over arbitrary inputs, the output Knowledge is never RECONCILED."""
    post = reconstruct_conservative(pre)
    assert post.knowledge_state is not KnowledgeState.RECONCILED


@given(pre=composites())
def test_reconstruct_is_monotone_conservative(pre) -> None:
    """(property §6.3) The projection never yields a less-conservative composite on any dimension."""
    post = reconstruct_conservative(pre)
    # Capacity: rcl comparator.
    assert capacity_at_least_as_conservative(post.capacity_state, pre.capacity_state)
    # Broker / Knowledge: per-dimension conservatism rank never decreases.
    assert (
        _BROKER_CONSERVATISM_RANK[post.broker_order_state]
        >= _BROKER_CONSERVATISM_RANK[pre.broker_order_state]
    )
    assert (
        _KNOWLEDGE_CONSERVATISM_RANK[post.knowledge_state]
        >= _KNOWLEDGE_CONSERVATISM_RANK[pre.knowledge_state]
    )
    # Attempt is preserved (rank unchanged).
    assert (
        _ATTEMPT_CONSERVATISM_RANK[post.transmission_attempt_state]
        == _ATTEMPT_CONSERVATISM_RANK[pre.transmission_attempt_state]
    )
