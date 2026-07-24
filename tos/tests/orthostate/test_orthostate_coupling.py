"""Cross-dimension coupling CPL-1..7 — static detect-and-flag, never normalize (§5).

The three clean §14 fixtures pass under a positive side; the two coupling-negative §14
fixtures are BOTH constructible AND flag CPL-5 (the representable-but-coupling-flagged
class, design #8 §5.0 — two separate claims, not a contradiction). Each CPL fires on its
antecedent and clears when satisfied (both-ways). Satisfiable overlap: Broker=UNKNOWN ∧
Capacity=POTENTIALLY_LIVE is illegal (CPL-5 dominates via the rcl comparator). Contradictory
overlap: Knowledge=CONFLICTED ∧ trapped=True is illegal for ALL nine capacity values and
NO CPL is dropped. Side-flags fail closed. coupling_violations never mutates the composite.
[STATE-EV-003 slice — /3 runtime coupling enforcement deferred]
"""

from __future__ import annotations

import pytest
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    CouplingSideConditions,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    coupling_violations,
    no_coupling_violation,
)
from tos.rcl import CapacityState, capacity_at_least_as_conservative

from ._orthostate_strategies import (
    CLEAN_POSITIVE_FIXTURES,
    COMPOSITE_14_2_SENT_UNKNOWN,
    COMPOSITE_14_4_SUPERSEDED_CANCEL,
    COUPLING_NEGATIVE_FIXTURES,
    clean_side,
    fail_closed_side,
    issue_composite,
)


def _c(**dims: object) -> CompositeState:
    """A composite with sensible non-triggering defaults, overriding named dimensions."""
    base: dict[str, object] = {
        "intent_state": IntentState.ACTIVE,
        "transmission_attempt_state": TransmissionAttemptState.NONE,
        "broker_order_state": BrokerOrderState.WORKING,
        "knowledge_state": KnowledgeState.CONSISTENT,
        "capacity_state": CapacityState.POTENTIALLY_LIVE,
    }
    base.update(dims)
    return issue_composite(**base)


# ---------------------------------------------------------------------------
# §14 fixtures: three clean positives + two representable-but-coupling-flagged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", CLEAN_POSITIVE_FIXTURES, ids=lambda c: c.composite_state_id
)
def test_clean_positive_fixtures_have_no_violation(fixture: CompositeState) -> None:
    """(guard True side) 14_1 / 14_3 / 14_5 are coupling-clean under a positive side."""
    assert no_coupling_violation(fixture, clean_side()) is True
    assert coupling_violations(fixture, clean_side()) == frozenset()


@pytest.mark.parametrize(
    "fixture", COUPLING_NEGATIVE_FIXTURES, ids=lambda c: c.composite_state_id
)
def test_coupling_negative_fixtures_are_representable_and_flagged(
    fixture: CompositeState,
) -> None:
    """(C1 representable-but-coupling-flagged) 14_2 / 14_4 construct AND flag CPL-5.

    Two separate claims hold simultaneously (design #8 §5.0): the composite is
    constructible (STATE-EV-001 representability) AND its coupling violation set includes
    CPL-5 (STATE-EV-003) — regardless of the injected side (the flag is inherent, not a
    side artifact). It is HELD and flagged, never silently normalized.
    """
    # Claim 1: representable (a real issued frozen product).
    assert fixture.canonical_digest is not None
    # Claim 2: coupling-flagged with CPL-5, under BOTH the positive and fail-closed sides.
    assert "CPL-5" in coupling_violations(fixture, clean_side())
    assert "CPL-5" in coupling_violations(fixture, fail_closed_side())


# ---------------------------------------------------------------------------
# CPL-1 — potential effect => capacity at least POTENTIALLY_LIVE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attempt",
    [TransmissionAttemptState.SEND_STARTED, TransmissionAttemptState.SENT_UNCONFIRMED],
)
def test_cpl1_fires_when_potentially_live_but_capacity_too_weak(attempt) -> None:
    """(CPL-1 fires) A live-send attempt with Capacity below POTENTIALLY_LIVE violates CPL-1."""
    c = _c(
        transmission_attempt_state=attempt, capacity_state=CapacityState.ATTEMPT_BOUND
    )
    assert "CPL-1" in coupling_violations(c, clean_side())


def test_cpl1_clears_when_capacity_conservative_enough() -> None:
    """(CPL-1 clears) At POTENTIALLY_LIVE (or more conservative) CPL-1 does not fire."""
    c = _c(
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        capacity_state=CapacityState.PARTIALLY_CONSUMED,
    )
    assert "CPL-1" not in coupling_violations(c, clean_side())


# ---------------------------------------------------------------------------
# CPL-2 — no release without proof (fail-closed on side flags)
# ---------------------------------------------------------------------------


def test_cpl2_fires_on_release_without_proof() -> None:
    """(CPL-2 fires, fail-closed) RELEASED with all side proofs None violates CPL-2."""
    c = _c(
        broker_order_state=BrokerOrderState.FILLED,
        knowledge_state=KnowledgeState.RECONCILED,
        capacity_state=CapacityState.RELEASED,
    )
    assert "CPL-2" in coupling_violations(c, fail_closed_side())


def test_cpl2_clears_with_reconciled_terminal_and_fqp() -> None:
    """(CPL-2 clears) RELEASED with Knowledge=RECONCILED, terminal Broker, and FQP is clean."""
    c = _c(
        broker_order_state=BrokerOrderState.FILLED,
        knowledge_state=KnowledgeState.RECONCILED,
        capacity_state=CapacityState.RELEASED,
    )
    assert "CPL-2" not in coupling_violations(c, clean_side())


def test_cpl2_consistent_release_needs_proof_rule() -> None:
    """(CPL-2) A CONSISTENT release is clean only with the applicable proof rule flag."""
    c = _c(
        broker_order_state=BrokerOrderState.CANCELLED,
        knowledge_state=KnowledgeState.CONSISTENT,
        capacity_state=CapacityState.RELEASED,
    )
    without = CouplingSideConditions(final_quantity_proof=True)
    assert "CPL-2" in coupling_violations(c, without)
    with_rule = CouplingSideConditions(
        final_quantity_proof=True, consistent_release_proof_rule=True
    )
    assert "CPL-2" not in coupling_violations(c, with_rule)


# ---------------------------------------------------------------------------
# CPL-3 — fill => consumed capacity (static consistency)
# ---------------------------------------------------------------------------


def test_cpl3_filled_requires_position_consumed() -> None:
    """(CPL-3) Broker=FILLED requires Capacity=POSITION_CONSUMED."""
    bad = _c(
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.FILLED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )
    assert "CPL-3" in coupling_violations(bad, clean_side())
    good = _c(
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.FILLED,
        capacity_state=CapacityState.POSITION_CONSUMED,
    )
    assert "CPL-3" not in coupling_violations(good, clean_side())


def test_cpl3_partially_filled_requires_partially_consumed() -> None:
    """(CPL-3) Broker=PARTIALLY_FILLED requires Capacity=PARTIALLY_CONSUMED."""
    bad = _c(
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.PARTIALLY_FILLED,
        capacity_state=CapacityState.POSITION_CONSUMED,
    )
    assert "CPL-3" in coupling_violations(bad, clean_side())


# ---------------------------------------------------------------------------
# CPL-4 — cancel is not release (subsumed by CPL-2 in the static view)
# ---------------------------------------------------------------------------


def test_cpl4_cancel_pending_blocks_release() -> None:
    """(CPL-4) Broker=CANCEL_PENDING with Capacity=RELEASED violates CPL-4."""
    c = _c(
        broker_order_state=BrokerOrderState.CANCEL_PENDING,
        capacity_state=CapacityState.RELEASED,
    )
    assert "CPL-4" in coupling_violations(c, clean_side())


def test_cpl4_bare_cancel_ack_blocks_release() -> None:
    """(CPL-4) A bare cancel-ACK (CANCELLED with no FQP) with RELEASED violates CPL-4."""
    c = _c(
        broker_order_state=BrokerOrderState.CANCELLED,
        capacity_state=CapacityState.RELEASED,
    )
    bare = CouplingSideConditions(final_quantity_proof=None)
    assert "CPL-4" in coupling_violations(c, bare)


# ---------------------------------------------------------------------------
# CPL-5 — unknown quarantine (exact value)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "trigger",
    [
        {"broker_order_state": BrokerOrderState.UNKNOWN},
        {"knowledge_state": KnowledgeState.CONFLICTED},
        {"knowledge_state": KnowledgeState.QUARANTINED},
    ],
)
def test_cpl5_fires_unless_quarantined_unknown(trigger: dict) -> None:
    """(CPL-5) UNKNOWN broker or CONFLICTED/QUARANTINED knowledge requires QUARANTINED_UNKNOWN."""
    bad = _c(capacity_state=CapacityState.POTENTIALLY_LIVE, **trigger)
    assert "CPL-5" in coupling_violations(bad, clean_side())
    good = _c(capacity_state=CapacityState.QUARANTINED_UNKNOWN, **trigger)
    assert "CPL-5" not in coupling_violations(good, clean_side())


# ---------------------------------------------------------------------------
# CPL-6 — authority gate on transmission (fail-closed)
# ---------------------------------------------------------------------------


def test_cpl6_requires_current_epoch_for_send_started_plus() -> None:
    """(CPL-6, fail-closed) An attempt at SEND_STARTED+ with epoch None/False violates CPL-6."""
    c = _c(
        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )
    assert "CPL-6" in coupling_violations(c, CouplingSideConditions())
    assert "CPL-6" in coupling_violations(
        c, CouplingSideConditions(authority_epoch_current=False)
    )
    assert "CPL-6" not in coupling_violations(
        c, CouplingSideConditions(authority_epoch_current=True)
    )


def test_cpl6_absent_before_send_started() -> None:
    """(CPL-6) A pre-send attempt (CAPABILITY_ISSUED) never triggers CPL-6."""
    c = _c(transmission_attempt_state=TransmissionAttemptState.CAPABILITY_ISSUED)
    assert "CPL-6" not in coupling_violations(c, fail_closed_side())


# ---------------------------------------------------------------------------
# CPL-7 — trapped exposure (exact value)
# ---------------------------------------------------------------------------


def test_cpl7_requires_trapped_consumed() -> None:
    """(CPL-7) non_reducible_exposure=True requires Capacity=TRAPPED_CONSUMED exactly."""
    side = CouplingSideConditions(
        non_reducible_exposure=True, authority_epoch_current=True
    )
    bad = _c(capacity_state=CapacityState.POSITION_CONSUMED)
    assert "CPL-7" in coupling_violations(bad, side)
    good = _c(capacity_state=CapacityState.TRAPPED_CONSUMED)
    assert "CPL-7" not in coupling_violations(good, side)


def test_cpl7_pending_exit_intent_cannot_reduce_it() -> None:
    """(CPL-7) A pending exit Intent (WITHDRAWN/ACTIVE) does not clear the trapped obligation."""
    side = CouplingSideConditions(
        non_reducible_exposure=True, authority_epoch_current=True
    )
    c = _c(
        intent_state=IntentState.ACTIVE, capacity_state=CapacityState.POSITION_CONSUMED
    )
    assert "CPL-7" in coupling_violations(c, side)


# ---------------------------------------------------------------------------
# §5.3a satisfiable overlap — CPL-1 ∧ CPL-5 (more-conservative exact dominates)
# ---------------------------------------------------------------------------


def test_cpl1_cpl5_dominance_potentially_live_is_illegal() -> None:
    """(canary §5.3a) Broker=UNKNOWN ∧ Capacity=POTENTIALLY_LIVE is illegal (CPL-5 dominates)."""
    c = _c(
        broker_order_state=BrokerOrderState.UNKNOWN,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )
    violations = coupling_violations(c, clean_side())
    assert "CPL-5" in violations  # CPL-1 alone would admit it; CPL-5 forbids it


def test_cpl1_cpl5_dominance_quarantined_unknown_is_clean() -> None:
    """(canary §5.3a) Broker=UNKNOWN ∧ Capacity=QUARANTINED_UNKNOWN satisfies both CPL-1 and CPL-5."""
    c = _c(
        broker_order_state=BrokerOrderState.UNKNOWN,
        capacity_state=CapacityState.QUARANTINED_UNKNOWN,
    )
    violations = coupling_violations(c, clean_side())
    assert "CPL-5" not in violations
    assert "CPL-1" not in violations


def test_rcl_comparator_backs_the_dominance() -> None:
    """(§5.3a) The dominance rests on the rcl comparator: QUARANTINED_UNKNOWN ≥ POTENTIALLY_LIVE."""
    assert (
        capacity_at_least_as_conservative(
            CapacityState.QUARANTINED_UNKNOWN, CapacityState.POTENTIALLY_LIVE
        )
        is True
    )


# ---------------------------------------------------------------------------
# §5.3b contradictory overlap — CPL-5 ∧ CPL-7 illegal for ALL nine capacity values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", list(CapacityState), ids=lambda s: s.value)
def test_contradictory_overlap_sweep_all_capacity_illegal(cap: CapacityState) -> None:
    """(canary §5.3b M1) Knowledge=CONFLICTED ∧ trapped=True => nonempty for every capacity.

    CPL-5 forces QUARANTINED_UNKNOWN, CPL-7 forces TRAPPED_CONSUMED — exact-vs-exact on
    different values, unsatisfiable by any capacity, so the composite is illegal for all
    nine values.
    """
    side = CouplingSideConditions(
        non_reducible_exposure=True, authority_epoch_current=True
    )
    c = _c(
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=KnowledgeState.CONFLICTED,
        capacity_state=cap,
    )
    assert coupling_violations(c, side) != frozenset()


def test_contradictory_overlap_no_cpl_dropped() -> None:
    """(canary §5.3b no-drop) At each exact value the OTHER CPL still fires — no signal lost."""
    side = CouplingSideConditions(
        non_reducible_exposure=True, authority_epoch_current=True
    )
    # cap=QUARANTINED_UNKNOWN satisfies CPL-5 but must still fail CPL-7 (trapped signal kept).
    at_quarantine = _c(
        knowledge_state=KnowledgeState.CONFLICTED,
        broker_order_state=BrokerOrderState.WORKING,
        capacity_state=CapacityState.QUARANTINED_UNKNOWN,
    )
    v_q = coupling_violations(at_quarantine, side)
    assert "CPL-7" in v_q and "CPL-5" not in v_q
    # cap=TRAPPED_CONSUMED satisfies CPL-7 but must still fail CPL-5 (quarantine signal kept).
    at_trapped = _c(
        knowledge_state=KnowledgeState.CONFLICTED,
        broker_order_state=BrokerOrderState.WORKING,
        capacity_state=CapacityState.TRAPPED_CONSUMED,
    )
    v_t = coupling_violations(at_trapped, side)
    assert "CPL-5" in v_t and "CPL-7" not in v_t


# ---------------------------------------------------------------------------
# never-normalize (§5.5)
# ---------------------------------------------------------------------------


def test_coupling_violations_does_not_mutate_composite() -> None:
    """(canary §5.5) Detecting violations returns a set and leaves the composite unchanged."""
    c = COMPOSITE_14_2_SENT_UNKNOWN
    before = c.model_dump()
    result = coupling_violations(c, clean_side())
    assert isinstance(result, frozenset)
    assert c.model_dump() == before  # no silent normalization
    assert c.capacity_state is CapacityState.POTENTIALLY_LIVE  # still the flagged value


def test_no_coupling_violation_matches_emptiness() -> None:
    """no_coupling_violation is exactly the emptiness of coupling_violations."""
    for fixture in (COMPOSITE_14_2_SENT_UNKNOWN, COMPOSITE_14_4_SUPERSEDED_CANCEL):
        assert no_coupling_violation(fixture, clean_side()) is (
            coupling_violations(fixture, clean_side()) == frozenset()
        )
