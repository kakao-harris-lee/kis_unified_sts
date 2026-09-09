"""Phase 3 wave 2 KW2-C1 — ``CANCEL_ACK`` / ``EXPIRED`` egress result kinds (plan §2.2).

Two new closed-vocabulary members, ADR-002-002 §16.2 / ADR-002-005 §7 verbatim: a **bare**
broker cancel acknowledgement moves the projection to ``RELEASE_PENDING_PROOF``, never
further — "cancel is not release" (CPL-4) — and an ``EXPIRED`` broker-observed order is
governed by the identical rule per the plan's own explicit instruction. Both are
knowledge-establishing but never capacity-releasing, exactly like ``REJECT`` before them.

This file also pins the full 8-member result-kind transition table (the "전수" the wave 1
finding named as a gap for the 6-member vocabulary — see
``test_engine_unknown_restrictive.py`` for the pre-existing six) and the specific
cancel-crossing-fill probe (ADR-002-002 §15.2) the plan calls out by name.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine import (
    EgressKnowledge,
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    ResultDisposition,
    knowledge_for_result,
)
from tos.rcl import CapacityState

from ._engine_fixtures import (
    RecordingTransmit,
    build_core,
    decision_tick,
    instrument_key,
    ordering,
)


def _sent_core():
    """A core that has completed one flow, so a reservation is projected POTENTIALLY_LIVE."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit)
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.handed_off is True
    assert result.flow.attempt is not None
    return core, sink, transmit, result.flow.attempt.attempt_id


def _egress_event(
    kind: EgressResultKind, attempt_id: str, *, sequence: int = 2, **fills
):
    """Build an ``EGRESS_RESULT`` event for the projected attempt."""
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id=attempt_id,
            kind=kind,
            reference=ordering(sequence),
            **fills,
        ),
    )


# ---------------------------------------------------------------------------
# vocabulary shape
# ---------------------------------------------------------------------------


def test_cancel_ack_and_expired_are_closed_vocabulary_members() -> None:
    """(§2.2) The two new kinds exist and are distinct from every existing member."""
    assert EgressResultKind.CANCEL_ACK in set(EgressResultKind)
    assert EgressResultKind.EXPIRED in set(EgressResultKind)
    assert EgressResultKind.CANCEL_ACK is not EgressResultKind.REJECT
    assert EgressResultKind.EXPIRED is not EgressResultKind.REJECT


def test_neither_new_kind_carries_a_fill_magnitude() -> None:
    """(§2.2; FILL_RESULT_KINDS unchanged) A magnitude on either kind is unconstructable."""
    from pydantic import ValidationError

    for kind in (EgressResultKind.CANCEL_ACK, EgressResultKind.EXPIRED):
        with pytest.raises(ValidationError, match="must carry no fill magnitude"):
            EgressResultPayload(
                instrument_key=instrument_key(),
                attempt_id="attempt-1",
                kind=kind,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("1"),
            )


# ---------------------------------------------------------------------------
# ADR-002-002 §16.2 / CPL-4 — cancel is not release
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", [EgressResultKind.CANCEL_ACK, EgressResultKind.EXPIRED]
)
def test_cancel_ack_and_expired_advance_to_release_pending_proof_never_further(
    kind,
) -> None:
    """(ADR-002-002 §16.2; CPL-4) Both land at RELEASE_PENDING_PROOF — the projection's own
    last, least-settled position — never at a released state (which does not exist here).
    """
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(kind, attempt_id))

    assert result.halt_reason is None
    assert result.result_disposition is ResultDisposition.APPLIED
    assert result.reservation is not None
    assert result.reservation.capacity_state is CapacityState.RELEASE_PENDING_PROOF


def test_cancel_ack_establishes_its_own_knowledge_member_not_rejected() -> None:
    """(§2.2) A cancel-ack must never be misread as a broker rejection."""
    assert knowledge_for_result(EgressResultKind.CANCEL_ACK) is (
        EgressKnowledge.CANCEL_ACKNOWLEDGED
    )
    assert (
        knowledge_for_result(EgressResultKind.CANCEL_ACK)
        is not EgressKnowledge.REJECTED
    )


def test_expired_establishes_its_own_knowledge_member_not_rejected() -> None:
    """(§2.2) An expiry must never be misread as a broker rejection either."""
    assert knowledge_for_result(EgressResultKind.EXPIRED) is EgressKnowledge.EXPIRED
    assert (
        knowledge_for_result(EgressResultKind.EXPIRED) is not EgressKnowledge.REJECTED
    )


def test_cancel_ack_reaches_the_projection_through_a_live_core() -> None:
    """(end-to-end) A ``CANCEL_ACK`` egress event actually advances a real projection."""
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(EgressResultKind.CANCEL_ACK, attempt_id))
    assert result.reservation.knowledge is EgressKnowledge.CANCEL_ACKNOWLEDGED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )


def test_expired_reaches_the_projection_through_a_live_core() -> None:
    """(end-to-end) An ``EXPIRED`` egress event actually advances a real projection."""
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(EgressResultKind.EXPIRED, attempt_id))
    assert result.reservation.knowledge is EgressKnowledge.EXPIRED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )


# ---------------------------------------------------------------------------
# ADR-002-002 §15.2 — the specific "cancel-crossing-fill" probe the plan names
# ---------------------------------------------------------------------------


def test_cancel_ack_then_late_full_fill_does_not_crash_and_is_recorded_non_monotonic() -> (
    None
):
    """(plan §2.2 "CANCEL_ACK 후 late FULL_FILL"; ADR-002-002 §15.2 "cancel-crossing-fill")

    ``RELEASE_PENDING_PROOF`` outranks ``POSITION_CONSUMED`` in the projection's own
    conservatism order (design #31 §2.4 — it sits last because a proven rejection/cancel
    still awaits the RCL-owned release proof). A late ``FULL_FILL`` arriving after a
    ``CANCEL_ACK`` would therefore revive the projection *backwards* by that order, which the
    existing non-revival guard refuses exactly as it already does for REJECT -> late FULL_FILL
    (``test_engine_unknown_restrictive.py``). The decision recorded here, honestly: this is
    the *provisional projection's own* conservatism ordering refusing a rank move, not a
    verdict that the fact itself is discarded — ADR-002-002 §15.2 "the Ledger SHALL accept
    valid late evidence" is a **real RCL** obligation (this package is explicitly
    non-authoritative, see ``tos/src/tos/engine/state.py`` module docstring); what this
    projection guarantees is only that the fact is never silently lost — it surfaces as
    ``RESULT_UNMATCHED`` evidence (``EvidenceKind.RESULT_UNMATCHED``) for a real reconciler to
    consume, and the projection never crashes and never re-releases capacity on it.
    """
    core, _, _, attempt_id = _sent_core()
    cancel = core.handle(
        _egress_event(EgressResultKind.CANCEL_ACK, attempt_id, sequence=2)
    )
    assert cancel.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )

    late_fill = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    # must not raise, and must not silently apply either:
    assert late_fill.halt_reason is HaltReason.RESULT_UNMATCHED
    assert late_fill.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )


def test_mutation_cancel_ack_treated_as_released_is_a_cpl4_violation() -> None:
    """Mutation guard (plan §2.2 "뮤테이션: CANCEL_ACK ⇒ RELEASED 위반 red").

    ``RELEASE_PENDING_PROOF`` is not, and must never become, ``RELEASED`` (which this
    projection cannot even represent — see ``PROJECTION_ORDER``'s own docstring, "RELEASED is
    absent, because this projection cannot release"). This test would go **red** under the
    mutation the plan names: if a future edit made ``CANCEL_ACK`` skip straight past
    ``RELEASE_PENDING_PROOF`` — the only way to simulate "released" here — the assertion below
    fails because the capacity state would no longer be the last, least-settled projection
    position.
    """
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(EgressResultKind.CANCEL_ACK, attempt_id))
    assert result.reservation.capacity_state is CapacityState.RELEASE_PENDING_PROOF
    assert result.reservation.capacity_state is not CapacityState.RELEASED


# ---------------------------------------------------------------------------
# full 8-member transition table (the "전수" this wave adds to the 6-member table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "fills", "expected_capacity", "expected_knowledge"),
    [
        (EgressResultKind.ACK, {}, None, EgressKnowledge.ACKNOWLEDGED),
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
            CapacityState.POSITION_CONSUMED,
            EgressKnowledge.FILLED,
        ),
        (
            EgressResultKind.PARTIAL_FILL,
            {"filled_quantity": Decimal("1"), "remaining_quantity": Decimal("1")},
            CapacityState.PARTIALLY_CONSUMED,
            EgressKnowledge.PARTIALLY_FILLED,
        ),
        (
            EgressResultKind.REJECT,
            {},
            CapacityState.RELEASE_PENDING_PROOF,
            EgressKnowledge.REJECTED,
        ),
        (EgressResultKind.UNKNOWN, {}, None, EgressKnowledge.UNKNOWN),
        (EgressResultKind.TIMEOUT, {}, None, EgressKnowledge.UNKNOWN),
        (
            EgressResultKind.CANCEL_ACK,
            {},
            CapacityState.RELEASE_PENDING_PROOF,
            EgressKnowledge.CANCEL_ACKNOWLEDGED,
        ),
        (
            EgressResultKind.EXPIRED,
            {},
            CapacityState.RELEASE_PENDING_PROOF,
            EgressKnowledge.EXPIRED,
        ),
    ],
)
def test_the_full_eight_member_transition_table(
    kind, fills, expected_capacity, expected_knowledge
) -> None:
    """(§2.2, full 전수) Every one of the eight ``EgressResultKind`` members transitions exactly
    as declared — capacity ``None`` means "unchanged, still POTENTIALLY_LIVE"."""
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(kind, attempt_id, **fills))

    assert result.result_disposition is ResultDisposition.APPLIED
    assert result.reservation.knowledge is expected_knowledge
    if expected_capacity is None:
        assert result.reservation.capacity_state is CapacityState.POTENTIALLY_LIVE
    else:
        assert result.reservation.capacity_state is expected_capacity


def test_all_eight_members_are_covered_by_the_table_above() -> None:
    """Anti-phantom: a future ninth member without a table row fails here, not silently."""
    covered = {
        EgressResultKind.ACK,
        EgressResultKind.FULL_FILL,
        EgressResultKind.PARTIAL_FILL,
        EgressResultKind.REJECT,
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
    }
    assert covered == set(EgressResultKind)
    assert len(covered) == 8
