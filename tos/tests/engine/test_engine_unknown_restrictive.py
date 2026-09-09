"""§7.2-2 — UNKNOWN at the send boundary is restrictive and releases nothing (design #31 §4.2 rule 3).

The design's target: *"send 경계 UNKNOWN/timeout → POTENTIALLY_LIVE 보수 유지·no blind resubmit·
capacity 미해제"*, anchored to RFC-005 §11:325-327 (UNKNOWN is neither a rejection nor
safe-to-retry) and ADR-002-002 INV-005:168 / INV-006:174.

Three properties, each of which a naive implementation gets wrong in a different way:

* an ``UNKNOWN`` / ``TIMEOUT`` result must **not** be folded into ``REJECTED`` knowledge — the two
  are different epistemic states and only one of them is a proof of non-liveness;
* the capacity projection must stay exactly where it was — ``POTENTIALLY_LIVE`` — because a crash
  or a silence after ``SEND_STARTED`` is intentionally treated as potentially live;
* **no** result kind may release the scope. The projection has no release path at all: releasing is
  the RCL's act and a producer-local counter creates no headroom (RFC-002 §9.1:557-558). This is
  asserted over the *whole* result vocabulary, not just the UNKNOWN case, so a future "an ACK frees
  the scope" shortcut fails here.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import ArtifactIntegrityError
from tos.engine import (
    PROJECTION_RANK,
    EgressKnowledge,
    EgressResultKind,
    EgressResultPayload,
    EngineEvent,
    EventKind,
    HaltReason,
    ProvisionalReservationLedger,
    ResultDisposition,
    knowledge_for_result,
)
from tos.rcl import CapacityState

from ._engine_fixtures import (
    PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
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


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_unknown_and_timeout_keep_the_reservation_potentially_live(kind) -> None:
    """(§7.2-2) UNKNOWN / timeout hold the capacity projection at POTENTIALLY_LIVE."""
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(kind, attempt_id))

    assert result.halt_reason is None
    assert result.reservation is not None
    assert result.reservation.capacity_state is CapacityState.POTENTIALLY_LIVE
    assert result.reservation.knowledge is EgressKnowledge.UNKNOWN


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_unknown_and_timeout_are_not_rejections(kind) -> None:
    """(§7.2-2; RFC-005 §11:325) UNKNOWN is never folded into REJECTED knowledge."""
    assert knowledge_for_result(kind) is EgressKnowledge.UNKNOWN
    assert knowledge_for_result(kind) is not EgressKnowledge.REJECTED


def test_unknown_causes_no_blind_resubmission() -> None:
    """(§7.2-2; RFC-002 §9.1:574) After an UNKNOWN the core sends nothing further by itself."""
    core, _, transmit, attempt_id = _sent_core()
    assert len(transmit.attempts) == 1
    core.handle(_egress_event(EgressResultKind.UNKNOWN, attempt_id))
    assert (
        len(transmit.attempts) == 1
    ), "an UNKNOWN result must not trigger a resubmission"


def test_a_second_tick_after_unknown_is_still_denied_at_the_capacity_stage() -> None:
    """(§7.2-2 + §7.2-9) An unresolved UNKNOWN keeps the scope occupied — no retry exposure."""
    core, _, transmit, attempt_id = _sent_core()
    core.handle(_egress_event(EgressResultKind.UNKNOWN, attempt_id))
    again = core.handle(decision_tick(sequence=3))
    assert again.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    assert len(transmit.attempts) == 1


@pytest.mark.parametrize(
    ("kind", "fills"),
    [
        (EgressResultKind.ACK, {}),
        (EgressResultKind.UNKNOWN, {}),
        (EgressResultKind.TIMEOUT, {}),
        (EgressResultKind.REJECT, {}),
        (
            EgressResultKind.PARTIAL_FILL,
            {"filled_quantity": Decimal("1"), "remaining_quantity": Decimal("1")},
        ),
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
        ),
    ],
)
def test_no_egress_result_ever_releases_the_scope(kind, fills) -> None:
    """(§4.4; RFC-002 §9.1:557-558) **No** result frees the scope — release is the RCL's act."""
    core, _, _, attempt_id = _sent_core()
    core.handle(_egress_event(kind, attempt_id, **fills))
    assert core.ledger.outstanding(instrument_key()) is not None
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_the_projection_has_no_release_method_at_all() -> None:
    """(§4.4 structural seal) The projection exposes no release/free/clear path in any spelling."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    for forbidden in (
        "release",
        "free",
        "clear",
        "reset",
        "remove",
        "release_reservation",
    ):
        assert not hasattr(ledger, forbidden), (
            f"ProvisionalReservationLedger.{forbidden} must not exist — releasing capacity is the "
            "Risk Capacity Ledger's act and a producer-local counter creates no headroom "
            "(RFC-002 §9.1:557-558)"
        )


def test_a_result_for_an_unknown_attempt_is_refused() -> None:
    """(§2.1(ii); Phase 3 A-K-2) A result naming another attempt transitions nothing.

    Recorded as ``MISMATCHED_ATTEMPT`` — a conservative disposition, never an
    :class:`~tos.canonical.ArtifactIntegrityError` crash (design plan 2026-09-09 §1.1).
    """
    core, _, _, _ = _sent_core()
    before = core.ledger.outstanding(instrument_key())
    result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            "attempt-someone-else",
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert result.halt_reason is HaltReason.RESULT_UNMATCHED
    assert result.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT
    # projection unchanged: identical model_dump before/after (mutation guard — a silent APPLIED
    # coercion of a mismatched attempt would still pass a bare object-identity/state check here
    # only if it happened to also leave the dump untouched, so the dump comparison is the real gate).
    assert core.ledger.outstanding(instrument_key()).model_dump() == before.model_dump()
    assert core.ledger.outstanding(instrument_key()) == before


def test_a_result_with_no_projected_reservation_is_refused() -> None:
    """(§2.2; Phase 3 A-K-2) An egress result is not a licence to create a reservation.

    Recorded as ``ORPHAN_NO_RESERVATION`` rather than raised.
    """
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-unknown", sequence=1)
    )
    assert result.halt_reason is HaltReason.RESULT_UNMATCHED
    assert result.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION
    assert result.reservation is None
    assert core.ledger.outstanding(instrument_key()) is None


def test_a_duplicate_result_is_recorded_as_duplicate_not_reapplied() -> None:
    """(Phase 3 A-K-2) The identical result applied twice is DUPLICATE the second time."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert first.halt_reason is None
    assert first.result_disposition is ResultDisposition.APPLIED
    after_first = core.ledger.outstanding(instrument_key())

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE
    # the duplicate never re-touches the projection
    assert core.ledger.outstanding(instrument_key()).model_dump() == after_first.model_dump()


def test_a_late_fill_after_timeout_on_the_same_attempt_is_applied() -> None:
    """(Phase 3 A-K-2; ADR-002-002 §15.2 'later valid fill accepted') TIMEOUT then FULL_FILL applies.

    A TIMEOUT is not a rejection and does not close the door on the *same* attempt: a later
    FULL_FILL for that exact attempt is APPLIED — knowledge and capacity advance, and the scope is
    never released (capacity release is the RCL's alone).
    """
    core, _, _, attempt_id = _sent_core()
    timeout_result = core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2))
    assert timeout_result.halt_reason is None
    assert timeout_result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POTENTIALLY_LIVE
    )

    fill_result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert fill_result.halt_reason is None
    assert fill_result.result_disposition is ResultDisposition.APPLIED
    reservation = core.ledger.outstanding(instrument_key())
    assert reservation.capacity_state is CapacityState.POSITION_CONSUMED
    assert reservation.knowledge is EgressKnowledge.FILLED
    # never released: still occupies the scope, still denies a new overlapping exposure
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_the_four_dispositions_are_exhaustive_and_distinguishable() -> None:
    """(Phase 3 A-K-2) Each of the four :class:`ResultDisposition` members is independently reachable."""
    core, _, _, attempt_id = _sent_core()

    orphan_core, _ = build_core(transmit=RecordingTransmit())
    orphan = orphan_core.handle(_egress_event(EgressResultKind.ACK, "attempt-x", sequence=1))
    assert orphan.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION

    mismatched = core.handle(_egress_event(EgressResultKind.ACK, "attempt-someone-else", sequence=2))
    assert mismatched.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT

    applied = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert applied.result_disposition is ResultDisposition.APPLIED

    duplicate = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert duplicate.result_disposition is ResultDisposition.DUPLICATE

    assert {
        orphan.result_disposition,
        mismatched.result_disposition,
        applied.result_disposition,
        duplicate.result_disposition,
    } == set(ResultDisposition)


def test_the_projection_never_revives_to_a_less_consumed_state() -> None:
    """(§2.4 non-revival) A later result may not move the projection backwards."""
    core, _, _, attempt_id = _sent_core()
    core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )
    # An ACK arriving late leaves the capacity axis alone (its mapping has no capacity target),
    # and an UNKNOWN likewise: neither can walk the projection back to POTENTIALLY_LIVE.
    core.handle(_egress_event(EgressResultKind.UNKNOWN, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )


@pytest.mark.parametrize("backwards", ["bind_attempt", "mark_potentially_live"])
def test_a_backwards_projection_transition_is_refused(backwards) -> None:
    """(§2.4 non-revival) A settled projection cannot be walked back to an earlier state.

    The egress-result mapping alone never moves backwards, so this exercises the guard through the
    ledger's own transition API — the case a *later* wiring change (a re-bind, a re-send) would
    otherwise reintroduce. ``ATTEMPT_BOUND`` and ``POTENTIALLY_LIVE`` both rank below
    ``POSITION_CONSUMED``, so both are refused.
    """
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id="prop-1")
    ledger.bind_attempt(key, attempt_id="attempt-1")
    ledger.mark_potentially_live(key)
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id="attempt-1",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert ledger.outstanding(key).capacity_state is CapacityState.POSITION_CONSUMED

    with pytest.raises(ArtifactIntegrityError, match="may not revive"):
        if backwards == "bind_attempt":
            ledger.bind_attempt(key, attempt_id="attempt-2")
        else:
            ledger.mark_potentially_live(key)
    assert ledger.outstanding(key).capacity_state is CapacityState.POSITION_CONSUMED


def test_the_projection_rank_orders_the_states_conservatively() -> None:
    """(§2.4) The rank the non-revival guard consumes is the declared conservatism order."""
    assert PROJECTION_RANK[CapacityState.COMMITTED_UNBOUND] < (
        PROJECTION_RANK[CapacityState.ATTEMPT_BOUND]
    )
    assert PROJECTION_RANK[CapacityState.ATTEMPT_BOUND] < (
        PROJECTION_RANK[CapacityState.POTENTIALLY_LIVE]
    )
    assert PROJECTION_RANK[CapacityState.POTENTIALLY_LIVE] < (
        PROJECTION_RANK[CapacityState.PARTIALLY_CONSUMED]
    )
    assert PROJECTION_RANK[CapacityState.PARTIALLY_CONSUMED] < (
        PROJECTION_RANK[CapacityState.POSITION_CONSUMED]
    )
    assert PROJECTION_RANK[CapacityState.POSITION_CONSUMED] < (
        PROJECTION_RANK[CapacityState.RELEASE_PENDING_PROOF]
    )
