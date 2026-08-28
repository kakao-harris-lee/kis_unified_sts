"""Transition ownership — the §12 table + Attempt region split; fail-closed (§6.2).

Each single-owner dimension is actor-only (from/to accepted, not gated). The Transmission
Attempt dimension is region-split by to_state (design #8 §6.2; ADR §6 line 82/89, §12 line
186): the Execution Coordinator owns the preparation region (entry into PREPARED /
CAPABILITY_ISSUED) and the Broker Adapter / Egress owns the send-boundary region (entry
into SEND_STARTED and beyond) — neither may perform the other's region, and the
write-ahead entry INTO SEND_STARTED is the send boundary (BAE). None actor / dimension,
None from/to on Attempt, and off-region combinations fail closed. [STATE-EV-005 substrate
— actor auth + rejection evidencing are EV-L2/L3 + Security, deferred]
"""

from __future__ import annotations

import pytest
from tos.orthostate import (
    IntentState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
    may_transition,
)

_D = StateDimension
_T = TransitionAuthority
_A = TransmissionAttemptState

#: The four single-owner dimensions and their sole §12 owner (Attempt is region-split).
_SINGLE_OWNER: dict[StateDimension, TransitionAuthority] = {
    _D.INTENT: _T.INTENT_REGISTRY,
    _D.BROKER_ORDER: _T.BROKER_ADAPTER_EVIDENCE,
    _D.KNOWLEDGE: _T.RECONCILIATION_SERVICE,
    _D.CAPACITY: _T.RISK_CAPACITY_LEDGER,
}

_PREP_ENTRIES = [
    (_A.NONE, _A.PREPARED),
    (_A.PREPARED, _A.CAPABILITY_ISSUED),
]
_SEND_BOUNDARY_ENTRIES = [
    (_A.CAPABILITY_ISSUED, _A.SEND_STARTED),
    (_A.SEND_STARTED, _A.SENT_UNCONFIRMED),
    (_A.SENT_UNCONFIRMED, _A.ACK_OBSERVED),
    (_A.SENT_UNCONFIRMED, _A.SEND_FAILED_PROVEN),
    (_A.SENT_UNCONFIRMED, _A.SUPERSEDED),
]


# ---------------------------------------------------------------------------
# Single-owner dimensions (actor-only; from/to accepted but not region-gated)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dimension,owner", list(_SINGLE_OWNER.items()))
def test_single_owner_allowed(
    dimension: StateDimension, owner: TransitionAuthority
) -> None:
    """(guard True) The sole owner may transition its dimension (from/to not gated)."""
    assert may_transition(owner, dimension, None, None) is True


@pytest.mark.parametrize("dimension,owner", list(_SINGLE_OWNER.items()))
def test_single_owner_non_owner_rejected(
    dimension: StateDimension, owner: TransitionAuthority
) -> None:
    """(canary §12 line 191) Every non-owner actor is rejected on a single-owner dimension."""
    for actor in _T:
        if actor is not owner:
            assert may_transition(actor, dimension, None, None) is False


@pytest.mark.parametrize("dimension", list(_SINGLE_OWNER))
def test_single_owner_none_actor_rejected(dimension: StateDimension) -> None:
    """(canary fail-closed) A None actor may transition no single-owner dimension."""
    assert may_transition(None, dimension, None, None) is False


def test_from_to_not_region_gated_for_single_owner() -> None:
    """(canary) A single-owner dimension's owner is allowed for ANY from/to (not gated)."""
    assert (
        may_transition(
            _T.INTENT_REGISTRY, _D.INTENT, IntentState.ACTIVE, IntentState.CLOSED
        )
        is True
    )
    assert may_transition(_T.INTENT_REGISTRY, _D.INTENT, None, None) is True


def test_reconciliation_cannot_write_capacity() -> None:
    """(canary §12 line 191) A non-owner (Reconciliation) cannot write Capacity (RCL-only)."""
    assert may_transition(_T.RECONCILIATION_SERVICE, _D.CAPACITY, None, None) is False
    assert may_transition(_T.RISK_CAPACITY_LEDGER, _D.CAPACITY, None, None) is True


# ---------------------------------------------------------------------------
# Transmission Attempt region split (the promised §7 region-split test)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("frm,to", _PREP_ENTRIES, ids=lambda x: getattr(x, "value", x))
def test_execution_coordinator_owns_prep(frm, to) -> None:
    """(guard True) The Execution Coordinator owns the preparation region entries."""
    assert (
        may_transition(_T.EXECUTION_COORDINATOR, _D.TRANSMISSION_ATTEMPT, frm, to)
        is True
    )


@pytest.mark.parametrize("frm,to", _PREP_ENTRIES, ids=lambda x: getattr(x, "value", x))
def test_egress_rejected_for_prep(frm, to) -> None:
    """(canary MAJOR fix) The Egress Gateway may NOT perform a preparation transition."""
    assert (
        may_transition(_T.BROKER_ADAPTER_EGRESS, _D.TRANSMISSION_ATTEMPT, frm, to)
        is False
    )


@pytest.mark.parametrize(
    "frm,to", _SEND_BOUNDARY_ENTRIES, ids=lambda x: getattr(x, "value", x)
)
def test_egress_owns_send_boundary(frm, to) -> None:
    """(guard True) The Egress Gateway owns the send-boundary region entries."""
    assert (
        may_transition(_T.BROKER_ADAPTER_EGRESS, _D.TRANSMISSION_ATTEMPT, frm, to)
        is True
    )


@pytest.mark.parametrize(
    "frm,to", _SEND_BOUNDARY_ENTRIES, ids=lambda x: getattr(x, "value", x)
)
def test_execution_coordinator_rejected_for_send_boundary(frm, to) -> None:
    """(canary MAJOR fix) The Coordinator may NOT perform a send-boundary transition.

    Closes the reviewer's concrete over-grant: EXECUTION_COORDINATOR must be REJECTED for
    SEND_STARTED -> SENT_UNCONFIRMED (and every send-boundary entry).
    """
    assert (
        may_transition(_T.EXECUTION_COORDINATOR, _D.TRANSMISSION_ATTEMPT, frm, to)
        is False
    )


def test_capability_issued_to_send_started_is_egress_owned() -> None:
    """(canary §6 line 89) The write-ahead entry INTO SEND_STARTED is the send boundary (BAE)."""
    assert (
        may_transition(
            _T.BROKER_ADAPTER_EGRESS,
            _D.TRANSMISSION_ATTEMPT,
            _A.CAPABILITY_ISSUED,
            _A.SEND_STARTED,
        )
        is True
    )
    assert (
        may_transition(
            _T.EXECUTION_COORDINATOR,
            _D.TRANSMISSION_ATTEMPT,
            _A.CAPABILITY_ISSUED,
            _A.SEND_STARTED,
        )
        is False
    )


def test_attempt_none_from_or_to_fails_closed() -> None:
    """(canary fail-closed) A None from/to on the Attempt dimension is rejected for any actor."""
    assert (
        may_transition(
            _T.EXECUTION_COORDINATOR, _D.TRANSMISSION_ATTEMPT, None, _A.PREPARED
        )
        is False
    )
    assert (
        may_transition(_T.EXECUTION_COORDINATOR, _D.TRANSMISSION_ATTEMPT, _A.NONE, None)
        is False
    )
    assert (
        may_transition(_T.BROKER_ADAPTER_EGRESS, _D.TRANSMISSION_ATTEMPT, None, None)
        is False
    )


def test_attempt_off_region_to_state_fails_closed() -> None:
    """(canary) An Attempt transition into the genesis NONE (off-region to_state) fails closed."""
    for actor in (_T.EXECUTION_COORDINATOR, _T.BROKER_ADAPTER_EGRESS):
        assert (
            may_transition(actor, _D.TRANSMISSION_ATTEMPT, _A.PREPARED, _A.NONE)
            is False
        )


def test_attempt_non_region_actors_rejected() -> None:
    """(canary) Actors outside both Attempt regions are rejected for any Attempt transition."""
    for actor in _T:
        if actor not in (_T.EXECUTION_COORDINATOR, _T.BROKER_ADAPTER_EGRESS):
            assert (
                may_transition(actor, _D.TRANSMISSION_ATTEMPT, _A.NONE, _A.PREPARED)
                is False
            )
            assert (
                may_transition(
                    actor, _D.TRANSMISSION_ATTEMPT, _A.SEND_STARTED, _A.SENT_UNCONFIRMED
                )
                is False
            )


def test_none_actor_rejected_for_attempt() -> None:
    """(canary fail-closed) A None actor may perform no Attempt transition."""
    assert may_transition(None, _D.TRANSMISSION_ATTEMPT, _A.NONE, _A.PREPARED) is False


# ---------------------------------------------------------------------------
# Exhaustive full-matrix sweep (§12 + region split)
# ---------------------------------------------------------------------------


def test_full_ownership_matrix() -> None:
    """(exhaustive) Every (actor, dimension[, region]) cell matches the §12 + region table."""
    # Single-owner dimensions: allowed iff actor is the sole owner (from/to irrelevant).
    for dimension, owner in _SINGLE_OWNER.items():
        for actor in _T:
            assert may_transition(actor, dimension, None, None) is (actor is owner)
    # Attempt preparation region: only the Execution Coordinator.
    for actor in _T:
        assert may_transition(actor, _D.TRANSMISSION_ATTEMPT, _A.NONE, _A.PREPARED) is (
            actor is _T.EXECUTION_COORDINATOR
        )
    # Attempt send-boundary region: only the Broker Adapter / Egress.
    for actor in _T:
        assert may_transition(
            actor, _D.TRANSMISSION_ATTEMPT, _A.SEND_STARTED, _A.SENT_UNCONFIRMED
        ) is (actor is _T.BROKER_ADAPTER_EGRESS)
