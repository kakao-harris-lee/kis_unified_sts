"""Phase 3 wave 2 KW2-C2 — the ``engine/orthostate_projection.py`` adapter (plan §2.2).

``composite_state_for`` and ``result_transition_for`` are pure lookups over the engine's own
vocabulary and reservation projection, mapping onto ADR-002-005 §6-§8
:class:`~tos.orthostate.CompositeState` coordinates. This file proves two things a caller
needs, neither of which the adapter itself can assert about its own output:

1. every one of the eight :class:`~tos.engine.EgressResultKind` members maps to real, existing
   ``tos.orthostate`` dimension members (never a typo, never a phantom name);
2. running the mapped result through ``tos.orthostate.coupling_violations`` and
   ``tos.orthostate.may_transition`` — the whole point of authoring the mapping here — behaves
   as the ADR-002-005 CPL invariants require: the canonical pairs this adapter produces are
   clean, and the CPL-2 / CPL-4 *violating* pairs the plan names explicitly (e.g. Capacity
   ``RELEASED`` with Knowledge ``UNOBSERVED``) are caught.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine import (
    EgressKnowledge,
    EgressResultKind,
    InstrumentKey,
    ProvisionalReservation,
    composite_state_for,
    result_transition_for,
)
from tos.orthostate import (
    BrokerOrderState,
    CouplingSideConditions,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    coupling_violations,
)
from tos.rcl import CapacityState


def _key() -> InstrumentKey:
    return InstrumentKey(account="acct-orthostate", instrument="ES")


# ---------------------------------------------------------------------------
# result_transition_for — every member maps to real orthostate coordinates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(EgressResultKind))
def test_every_result_kind_maps_to_real_orthostate_members(kind) -> None:
    """(§2.2) The triple's three members are all real, existing enum members."""
    attempt, broker, knowledge = result_transition_for(kind)
    assert attempt in set(TransmissionAttemptState)
    assert broker in set(BrokerOrderState)
    assert knowledge in set(KnowledgeState)


def test_ack_maps_to_ack_observed_working_consistent() -> None:
    """(module docstring's own worked example) ACK -> (ACK_OBSERVED, WORKING, CONSISTENT)."""
    assert result_transition_for(EgressResultKind.ACK) == (
        TransmissionAttemptState.ACK_OBSERVED,
        BrokerOrderState.WORKING,
        KnowledgeState.CONSISTENT,
    )


def test_full_fill_maps_to_filled() -> None:
    attempt, broker, knowledge = result_transition_for(EgressResultKind.FULL_FILL)
    assert broker is BrokerOrderState.FILLED
    assert knowledge is KnowledgeState.CONSISTENT


def test_partial_fill_maps_to_partially_filled() -> None:
    attempt, broker, knowledge = result_transition_for(EgressResultKind.PARTIAL_FILL)
    assert broker is BrokerOrderState.PARTIALLY_FILLED


def test_reject_maps_to_send_failed_proven_and_rejected() -> None:
    attempt, broker, knowledge = result_transition_for(EgressResultKind.REJECT)
    assert attempt is TransmissionAttemptState.SEND_FAILED_PROVEN
    assert broker is BrokerOrderState.REJECTED


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_unknown_and_timeout_map_to_unknown_broker_state(kind) -> None:
    """(module docstring) Neither result kind carries conflicting evidence, only absent —
    Knowledge is ``UNOBSERVED``, and ``KnowledgeState`` has no dedicated UNKNOWN member.
    """
    attempt, broker, knowledge = result_transition_for(kind)
    assert broker is BrokerOrderState.UNKNOWN
    assert knowledge is KnowledgeState.UNOBSERVED
    assert attempt is TransmissionAttemptState.SENT_UNCONFIRMED


def test_cancel_ack_maps_to_cancel_pending_not_cancelled() -> None:
    """(recorded decision — plan §2.2 "read §7 and choose") ADR-002-002 §16.2 verbatim.

    "Cancel Acknowledgement moves the reservation to RELEASE_PENDING_PROOF" is stated for a
    *bare* acknowledgement; the fully proven ``CANCELLED`` state is a stronger claim this
    adapter never makes from a bare ACK alone.
    """
    attempt, broker, knowledge = result_transition_for(EgressResultKind.CANCEL_ACK)
    assert broker is BrokerOrderState.CANCEL_PENDING
    assert broker is not BrokerOrderState.CANCELLED


def test_expired_maps_to_expired() -> None:
    attempt, broker, knowledge = result_transition_for(EgressResultKind.EXPIRED)
    assert broker is BrokerOrderState.EXPIRED


def test_cancel_ack_and_expired_project_attempt_as_ack_observed_not_superseded() -> (
    None
):
    """(recorded decision) Neither is a *different* attempt superseding this one."""
    for kind in (EgressResultKind.CANCEL_ACK, EgressResultKind.EXPIRED):
        attempt, _, _ = result_transition_for(kind)
        assert attempt is TransmissionAttemptState.ACK_OBSERVED
        assert attempt is not TransmissionAttemptState.SUPERSEDED


def test_no_result_kind_ever_claims_reconciled() -> None:
    """(recorded decision) A bare/synthetic result never claims ADR-002-005 §8 RECONCILED —
    that requires positive corroboration *and* Final Quantity Proof this adapter never has.
    """
    for kind in EgressResultKind:
        _, _, knowledge = result_transition_for(kind)
        assert knowledge is not KnowledgeState.RECONCILED


# ---------------------------------------------------------------------------
# composite_state_for — builds a real CompositeState from the engine's own projection
# ---------------------------------------------------------------------------


def test_composite_state_for_reuses_capacity_directly() -> None:
    """(§3.4 REUSE) The Capacity dimension is not converted — it is the same value."""
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        knowledge=EgressKnowledge.SENT_UNCONFIRMED,
        proposal_id="prop-1",
    )
    composite = composite_state_for(
        projection,
        intent_state=IntentState.ACTIVE,
        attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
    )
    assert composite.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert composite.intent_identity == "prop-1"
    assert composite.intent_state is IntentState.ACTIVE
    assert (
        composite.transmission_attempt_state
        is TransmissionAttemptState.SENT_UNCONFIRMED
    )


def test_composite_state_for_derives_broker_and_knowledge_from_projection_knowledge() -> (
    None
):
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.POSITION_CONSUMED,
        knowledge=EgressKnowledge.FILLED,
        proposal_id="prop-2",
        attempt_id="attempt-2",
        filled_quantity=Decimal("2"),
        remaining_quantity=Decimal("0"),
    )
    composite = composite_state_for(
        projection,
        intent_state=IntentState.ACTIVE,
        attempt_state=TransmissionAttemptState.ACK_OBSERVED,
    )
    assert composite.broker_order_state is BrokerOrderState.FILLED
    assert composite.knowledge_state is KnowledgeState.CONSISTENT


def test_composite_state_for_tolerates_an_unbound_proposal_id() -> None:
    """(DRAFT-status deferral) A ``None`` proposal_id does not make the composite unconstructable."""
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.COMMITTED_UNBOUND,
        knowledge=EgressKnowledge.NOT_SENT,
    )
    composite = composite_state_for(
        projection,
        intent_state=IntentState.PROPOSED,
        attempt_state=TransmissionAttemptState.NONE,
    )
    assert composite.intent_identity is None
    assert composite.broker_order_state is BrokerOrderState.NONE_OBSERVED
    assert composite.knowledge_state is KnowledgeState.UNOBSERVED


# ---------------------------------------------------------------------------
# integration with tos.orthostate.coupling_violations — the whole point of the adapter
# ---------------------------------------------------------------------------


def test_a_full_fill_mapped_composite_has_no_coupling_violation() -> None:
    """(canonical pair, clean) FULL_FILL's mapped composite passes every CPL invariant."""
    attempt, broker, knowledge = result_transition_for(EgressResultKind.FULL_FILL)
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.POSITION_CONSUMED,
        knowledge=EgressKnowledge.FILLED,
        proposal_id="prop-3",
    )
    composite = composite_state_for(
        projection, intent_state=IntentState.ACTIVE, attempt_state=attempt
    )
    assert composite.broker_order_state is broker
    assert composite.knowledge_state is knowledge
    assert (
        coupling_violations(
            composite, CouplingSideConditions(authority_epoch_current=True)
        )
        == frozenset()
    )


def test_a_sent_unconfirmed_composite_at_potentially_live_has_no_violation() -> None:
    """(CPL-1 satisfied) SENT_UNCONFIRMED + POTENTIALLY_LIVE is exactly what CPL-1 requires."""
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        knowledge=EgressKnowledge.SENT_UNCONFIRMED,
        proposal_id="prop-4",
    )
    composite = composite_state_for(
        projection,
        intent_state=IntentState.ACTIVE,
        attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
    )
    assert (
        coupling_violations(
            composite, CouplingSideConditions(authority_epoch_current=True)
        )
        == frozenset()
    )


def test_cpl1_violation_sent_unconfirmed_but_capacity_committed_unbound() -> None:
    """(CPL-1 violated) A potentially-live Attempt with a capacity state that is NOT at least
    as conservative as POTENTIALLY_LIVE must be caught."""
    projection = ProvisionalReservation(
        instrument_key=_key(),
        capacity_state=CapacityState.COMMITTED_UNBOUND,
        knowledge=EgressKnowledge.SENT_UNCONFIRMED,
        proposal_id="prop-5",
    )
    composite = composite_state_for(
        projection,
        intent_state=IntentState.ACTIVE,
        attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
    )
    assert "CPL-1" in coupling_violations(composite)


def test_cpl2_violation_released_with_unobserved_knowledge_and_no_proof() -> None:
    """(plan §2.2's own named example) Capacity RELEASED with Knowledge UNOBSERVED is illegal.

    This projection can never itself produce ``RELEASED`` (module docstring — "this projection
    cannot release"), so the composite is built directly to exercise the orthostate predicate
    the way a real RCL-backed runtime eventually would.
    """
    from tos.orthostate import CompositeState

    composite = CompositeState(
        intent_identity="prop-6",
        intent_state=IntentState.CLOSED,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.CANCELLED,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.RELEASED,
    )
    violations = coupling_violations(composite, CouplingSideConditions())
    assert "CPL-2" in violations


def test_cpl4_violation_cancel_pending_capacity_prematurely_released() -> None:
    """(CPL-4 "cancel is not release") A CANCEL_ACK-mapped composite whose capacity somehow
    reached RELEASED (never produced by this engine's own projection, but exercised here
    directly) is a CPL-4 violation."""
    from tos.orthostate import CompositeState

    _, broker, knowledge = result_transition_for(EgressResultKind.CANCEL_ACK)
    composite = CompositeState(
        intent_identity="prop-7",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=broker,
        knowledge_state=knowledge,
        capacity_state=CapacityState.RELEASED,
    )
    violations = coupling_violations(composite, CouplingSideConditions())
    assert "CPL-4" in violations


def test_mutation_swapping_cancel_ack_to_cancelled_would_still_be_caught_by_cpl4() -> (
    None
):
    """Mutation-style guard: even the *stronger* (and wrong-for-a-bare-ack) ``CANCELLED``
    broker state does not excuse a prematurely ``RELEASED`` capacity — CPL-4 still fires. This
    demonstrates the recorded decision (CANCEL_PENDING, not CANCELLED) is not load-bearing for
    CPL-4 safety; it is load-bearing for honesty about what a bare ack proves (ADR-002-002
    §16.2), which is the property the other CANCEL_ACK tests in this file check instead.
    """
    from tos.orthostate import CompositeState

    composite = CompositeState(
        intent_identity="prop-8",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.CANCELLED,
        knowledge_state=KnowledgeState.CONSISTENT,
        capacity_state=CapacityState.RELEASED,
    )
    violations = coupling_violations(composite, CouplingSideConditions())
    assert "CPL-4" in violations
