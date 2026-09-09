"""§7.2-2 — UNKNOWN at the send boundary is restrictive and releases nothing (design #31 §4.2 rule 3).

The design's target: *"send 경계 UNKNOWN/timeout → quarantine 보수 유지·no blind resubmit·
capacity 미해제"*, anchored to RFC-005 §11:325-327 (UNKNOWN is neither a rejection nor
safe-to-retry), ADR-002-002 INV-005:168 / INV-006:174, and ADR-002-005 §7/§10 CPL-5 (Phase 3 wave
2 review finding #2 / kernel disposition KW2b-#2).

Four properties, each of which a naive implementation gets wrong in a different way:

* an ``UNKNOWN`` / ``TIMEOUT`` result must **not** be folded into ``REJECTED`` knowledge — the two
  are different epistemic states and only one of them is a proof of non-liveness;
* the capacity projection must move into quarantine — ``QUARANTINED_UNKNOWN`` — because ADR-002-005
  §7 requires exactly that "until resolved", and CPL-5 requires the exact value whenever Broker
  Order is ``UNKNOWN`` (before KW2b-#2 the projection instead left capacity at whatever it last
  was, which under-claimed the fact and produced a false CPL-5 halt downstream);
* escaping the quarantine happens only through positive broker evidence for the *same* attempt
  (:data:`~tos.engine.state.QUARANTINE_RESOLUTION_EDGES`) — never a bare repeated ``UNKNOWN`` /
  ``TIMEOUT`` (ADR-002-002 §18.6 "escaping quarantine requires evidence, never assertion");
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
    PROJECTION_ORDER,
    PROJECTION_RANK,
    QUARANTINE_RESOLUTION_EDGES,
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
def test_unknown_and_timeout_quarantine_the_reservation(kind) -> None:
    """([KW2b-#2]) UNKNOWN / timeout force the capacity projection into QUARANTINED_UNKNOWN.

    ADR-002-005 §7 "UNKNOWN here forces QUARANTINED_UNKNOWN in the Capacity dimension until
    resolved"; before this fix the projection instead left capacity at POTENTIALLY_LIVE, which
    under-claimed the fact and produced a false CPL-5 coupling violation downstream (Phase 3
    wave 2 review finding #2).
    """
    core, _, _, attempt_id = _sent_core()
    result = core.handle(_egress_event(kind, attempt_id))

    assert result.halt_reason is None
    assert result.reservation is not None
    assert result.reservation.capacity_state is CapacityState.QUARANTINED_UNKNOWN
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
        (EgressResultKind.CANCEL_ACK, {}),
        (EgressResultKind.EXPIRED, {}),
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
    assert (
        core.ledger.outstanding(instrument_key()).model_dump()
        == after_first.model_dump()
    )


def test_duplicate_is_keyed_on_broker_execution_id_not_the_reference_coordinate() -> (
    None
):
    """([K2-p3-#6] finding #6; ADR-002-002 §15.3:725) DUPLICATE keys on broker identity.

    A genuine broker resend of the *same* fill carries a fresh ``reference`` coordinate — the
    driver stamps a new monotone one on every re-enqueue — so keying the DUPLICATE signature on
    ``reference`` can never catch it (only byte-identical already-stamped replays). Keying on
    ``broker_execution_id`` instead (ADR-002-002 §15.3 "broker execution identity or a
    broker-specific deterministic composite identity") catches the case the spec actually names:
    two ``FULL_FILL``s for the same attempt and the same broker execution id, at *different*
    reference coordinates, are the same fact reported twice.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,  # a different reference coordinate — not a byte-identical replay
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",  # same broker-side identity
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE


def test_different_broker_execution_ids_are_both_applied() -> None:
    """([K2-p3-#6]) Two distinct broker execution ids are two distinct facts, not a duplicate."""
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-1",
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
            broker_execution_id="broker-exec-2",
        )
    )
    assert second.halt_reason is None
    assert second.result_disposition is ResultDisposition.APPLIED


def test_timeouts_with_no_broker_id_dedup_as_a_runtime_local_replay_guard() -> None:
    """([K2-p3-#6]) With no broker id, the signature still dedups a byte-identical resend.

    ``TIMEOUT`` never carries a ``broker_execution_id`` (no broker was ever reached). With
    ``broker_execution_id is None`` for both, two TIMEOUTs for the same attempt now collide on the
    signature *regardless of their reference coordinate* — this is a runtime-local replay guard
    against re-processing the same synthetic timeout injection, **not** ADR-002-002 §15.3 broker
    idempotency (which requires a broker-side identity that a TIMEOUT, by definition, never has).
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(_egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2))
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=3)
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.DUPLICATE


def test_a_late_fill_after_timeout_on_the_same_attempt_is_applied() -> None:
    """(Phase 3 A-K-2; ADR-002-002 §15.2 'later valid fill accepted'; [KW2b-#2]) TIMEOUT then
    FULL_FILL applies — and resolves the quarantine TIMEOUT forced.

    A TIMEOUT is not a rejection and does not close the door on the *same* attempt: a later
    FULL_FILL for that exact attempt is APPLIED, resolving ``QUARANTINED_UNKNOWN`` down to
    ``POSITION_CONSUMED`` via the closed ``QUARANTINE_RESOLUTION_EDGES`` table — positive broker
    evidence for the same attempt is the one licit way out of quarantine (ADR-002-002 §18.6). The
    scope is never released either way (capacity release is the RCL's alone).
    """
    core, _, _, attempt_id = _sent_core()
    timeout_result = core.handle(
        _egress_event(EgressResultKind.TIMEOUT, attempt_id, sequence=2)
    )
    assert timeout_result.halt_reason is None
    assert timeout_result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
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


def test_a_late_fill_after_reject_does_not_crash_and_is_recorded_non_monotonic() -> (
    None
):
    """([K2-p3-#4] finding #4; ADR-002-002 §15.2) REJECT -> late FULL_FILL is not a crash.

    ``RELEASE_PENDING_PROOF`` outranks ``POSITION_CONSUMED`` in the projection's conservatism
    order (design #31 §2.4), so a late ``FULL_FILL`` arriving after a ``REJECT`` would revive the
    projection backwards. The pre-fix behaviour let :meth:`ProvisionalReservationLedger._store`
    raise :class:`~tos.canonical.ArtifactIntegrityError` straight out of ``core.handle`` — a crash,
    not an event (design plan 2026-09-09 §1.1 "크래시는 이벤트가 아니다"). The fix records
    ``NON_MONOTONIC_PROJECTION`` and leaves the projection exactly at ``RELEASE_PENDING_PROOF``:
    the fact is not silently lost — it surfaces as ``RESULT_UNMATCHED`` evidence — but the
    projection's own rank cannot move backward; reconciling the two is Phase 5's job.
    """
    core, _, _, attempt_id = _sent_core()
    rejected = core.handle(
        _egress_event(EgressResultKind.REJECT, attempt_id, sequence=2)
    )
    assert rejected.result_disposition is ResultDisposition.APPLIED
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
    assert late_fill.halt_reason is HaltReason.RESULT_UNMATCHED
    assert late_fill.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    # projection unchanged — still RELEASE_PENDING_PROOF, never revived to POSITION_CONSUMED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.RELEASE_PENDING_PROOF
    )


def test_a_late_partial_fill_after_full_fill_does_not_crash_and_is_recorded_non_monotonic() -> (
    None
):
    """([K2-p3-#4] finding #4) FULL_FILL -> late PARTIAL_FILL is not a crash either.

    ``POSITION_CONSUMED`` outranks ``PARTIALLY_CONSUMED``, so a reordered ``PARTIAL_FILL`` after a
    ``FULL_FILL`` hits the same non-revival guard from the other rank-regressing direction.
    """
    core, _, _, attempt_id = _sent_core()
    full = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert full.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )

    late_partial = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("1"),
        )
    )
    assert late_partial.halt_reason is HaltReason.RESULT_UNMATCHED
    assert late_partial.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )


def test_a_regressing_filled_quantity_is_refused_not_applied() -> None:
    """([K2-p3-#5] finding #5; ADR-002-002 §15.1:710) Filled quantity may never go down.

    Two ``PARTIAL_FILL``s on the same attempt where the second reports a *smaller* filled
    magnitude than the first must not silently overwrite the larger, already-recorded figure —
    that reader (``outstanding_consumed_magnitude``) is documented as the input to a
    position-closing derivation sized "from the position that actually exists" and ADR-002-002
    §15.1:710 requires reservation usage be reduced by no more than the amount proven filled.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding_consumed_magnitude(instrument_key()) == Decimal("4")

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("9"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    # the already-recorded, larger magnitude is retained — not overwritten downward
    assert core.ledger.outstanding_consumed_magnitude(instrument_key()) == Decimal("4")


def test_a_growing_remaining_quantity_is_refused_not_applied() -> None:
    """(Phase 3 wave 2 N2; ADR-002-002 §15.1) ``remaining_quantity`` may never grow.

    The reviewer probe named in the wave 1 finding: PARTIAL(4/6) -> PARTIAL(4/60) with the
    *same* filled magnitude. Before this fix ``apply_egress_result`` only compared
    ``filled_quantity`` (unchanged here, so the old check passed it straight through) and
    silently applied a remaining-quantity increase that implies the authorized quantity
    itself grew for the same attempt — unrepresentable, and non-conservative.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("60"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    # the already-recorded projection is retained byte-for-byte — untouched by the refusal
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("4")


def test_a_remaining_quantity_shrink_unmatched_by_a_filled_increase_is_refused() -> (
    None
):
    """(Phase 3 wave 2 N2; CPL-2/CPL-4) ``remaining_quantity`` may not shrink for free.

    The symmetric direction the same finding named: ``filled_quantity`` stays put while
    ``remaining_quantity`` drops — 4 units of quantity would vanish, unaccounted by either a
    proven fill or the still-outstanding remainder, which is an implicit, evidence-free
    release of exposure.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("2"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")


def test_a_remaining_quantity_shrink_fully_matched_by_filled_growth_is_applied() -> (
    None
):
    """(Phase 3 wave 2 N2, the non-regressing control) Ordinary partial-fill progression still works.

    ``remaining`` shrinking by *exactly* as much as ``filled`` grew is the legitimate case the
    N2 rule must not also catch — a control proving the new check does not over-reject.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("6"),
            remaining_quantity=Decimal("4"),
        )
    )
    assert second.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("4")
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("6")


def test_an_inflating_authorized_total_is_refused_not_applied() -> None:
    """([KW2b-#10]; Phase 3 wave 2 review finding #10; ADR-002-002 §15.1:710) ``filled`` may not
    outrun ``remaining``'s shrink either — the mirror of the vanishing-quantity direction.

    Reviewer's P4 probe: ``4/6`` -> ``6/5`` (``filled`` grows by 2, ``remaining`` shrinks by only
    1) inflates the attempt's authorized total from ``10`` to ``11``. The pre-fix check only
    refused a ``remaining`` shrink that *exceeded* the ``filled`` growth, never one that fell
    short of it, so this direction was silently ``APPLIED`` even though it is exactly as
    unrepresentable for one attempt as the direction the pre-existing check already caught.
    """
    core, _, _, attempt_id = _sent_core()
    first = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    assert first.result_disposition is ResultDisposition.APPLIED

    second = core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("6"),
            remaining_quantity=Decimal("5"),
        )
    )
    assert second.halt_reason is HaltReason.RESULT_UNMATCHED
    assert second.result_disposition is ResultDisposition.QUANTITY_REGRESSION
    # the established, non-inflated authorized total (10) is retained — not silently grown to 11
    assert core.ledger.outstanding(instrument_key()).filled_quantity == Decimal("4")
    assert core.ledger.outstanding(instrument_key()).remaining_quantity == Decimal("6")


def test_apply_egress_result_never_raises_artifact_integrity_error() -> None:
    """([K2-p3-#4] finding #4) The egress-result path never raises — only records a disposition.

    This is the structural guard the finding named: ``core.handle`` and
    ``ProvisionalReservationLedger.apply_egress_result`` must never let
    :class:`~tos.canonical.ArtifactIntegrityError` escape on this path, for *any* reachable
    disposition. A regression that reintroduces the raise (letting ``_store`` raise again) fails
    this test with an uncaught ``ArtifactIntegrityError`` instead of a clean assertion failure.
    """
    core, _, _, attempt_id = _sent_core()
    core.handle(_egress_event(EgressResultKind.REJECT, attempt_id, sequence=2))
    # must not raise:
    result = core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert result.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION


def test_the_six_dispositions_are_exhaustive_and_distinguishable() -> None:
    """(Phase 3 A-K-2, extended [K2-p3-#4/#5]) All six :class:`ResultDisposition` members reach."""
    core, _, _, attempt_id = _sent_core()

    orphan_core, _ = build_core(transmit=RecordingTransmit())
    orphan = orphan_core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-x", sequence=1)
    )
    assert orphan.result_disposition is ResultDisposition.ORPHAN_NO_RESERVATION

    mismatched = core.handle(
        _egress_event(EgressResultKind.ACK, "attempt-someone-else", sequence=2)
    )
    assert mismatched.result_disposition is ResultDisposition.MISMATCHED_ATTEMPT

    applied = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert applied.result_disposition is ResultDisposition.APPLIED

    duplicate = core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert duplicate.result_disposition is ResultDisposition.DUPLICATE

    non_monotonic_core, _, _, non_monotonic_attempt_id = _sent_core()
    non_monotonic_core.handle(
        _egress_event(EgressResultKind.REJECT, non_monotonic_attempt_id, sequence=2)
    )
    non_monotonic = non_monotonic_core.handle(
        _egress_event(
            EgressResultKind.FULL_FILL,
            non_monotonic_attempt_id,
            sequence=3,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert (
        non_monotonic.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    )

    regression_core, _, _, regression_attempt_id = _sent_core()
    regression_core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            regression_attempt_id,
            sequence=2,
            filled_quantity=Decimal("4"),
            remaining_quantity=Decimal("6"),
        )
    )
    regression = regression_core.handle(
        _egress_event(
            EgressResultKind.PARTIAL_FILL,
            regression_attempt_id,
            sequence=3,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("9"),
        )
    )
    assert regression.result_disposition is ResultDisposition.QUANTITY_REGRESSION

    assert {
        orphan.result_disposition,
        mismatched.result_disposition,
        applied.result_disposition,
        duplicate.result_disposition,
        non_monotonic.result_disposition,
        regression.result_disposition,
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
    # An ACK arriving late leaves the capacity axis alone (its ordinary mapping has no capacity
    # target, and this is not a quarantine-resolution case since the projection is not quarantined
    # — QUARANTINE_RESOLUTION_EDGES is only consulted from QUARANTINED_UNKNOWN).
    core.handle(_egress_event(EgressResultKind.ACK, attempt_id, sequence=3))
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.POSITION_CONSUMED
    )


def test_an_unknown_after_settlement_quarantines_forward_not_backward() -> None:
    """([KW2b-#2]) UNKNOWN after a definite settlement is a forward move into quarantine.

    Unlike ACK (whose ordinary mapping has no explicit capacity target and so cannot move the
    projection at all), UNKNOWN's capacity target is now the unconditional, explicit
    ``QUARANTINED_UNKNOWN`` (ADR-002-005 §7 "until resolved") — and ``QUARANTINED_UNKNOWN`` is
    the single most-conservative rank in ``PROJECTION_ORDER``, strictly above
    ``POSITION_CONSUMED``. So a later UNKNOWN for the same attempt is APPLIED even after a full
    fill: this is *not* the non-revival guard's business (rank increases, it does not decrease) —
    it is the intended, blanket "any UNKNOWN quarantines" rule, not an exception to it.
    """
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

    result = core.handle(
        _egress_event(EgressResultKind.UNKNOWN, attempt_id, sequence=3)
    )
    assert result.halt_reason is None
    assert result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
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
    assert PROJECTION_RANK[CapacityState.RELEASE_PENDING_PROOF] < (
        PROJECTION_RANK[CapacityState.QUARANTINED_UNKNOWN]
    ), (
        "QUARANTINED_UNKNOWN must outrank every settled state ([KW2b-#2]; mirrors "
        "tos.rcl.predicates._CONSERVATISM_RANK, where it is the single highest member)"
    )


def test_quarantined_unknown_is_the_last_projection_order_member() -> None:
    """([KW2b-#2]) QUARANTINED_UNKNOWN sits after RELEASE_PENDING_PROOF, not before it."""
    assert PROJECTION_ORDER[-1] is CapacityState.QUARANTINED_UNKNOWN
    assert PROJECTION_ORDER[-2] is CapacityState.RELEASE_PENDING_PROOF


# ---------------------------------------------------------------------------
# [KW2b-#2] quarantine resolution — QUARANTINE_RESOLUTION_EDGES
# ---------------------------------------------------------------------------


def _quarantined_core(kind: EgressResultKind = EgressResultKind.TIMEOUT):
    """A core whose reservation has already been forced into QUARANTINED_UNKNOWN by ``kind``."""
    core, sink, transmit, attempt_id = _sent_core()
    quarantine = core.handle(_egress_event(kind, attempt_id))
    assert quarantine.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )
    return core, sink, transmit, attempt_id


@pytest.mark.parametrize(
    ("kind", "fills"),
    [
        (EgressResultKind.ACK, {}),
        (
            EgressResultKind.PARTIAL_FILL,
            {"filled_quantity": Decimal("1"), "remaining_quantity": Decimal("1")},
        ),
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
        ),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.CANCEL_ACK, {}),
        (EgressResultKind.EXPIRED, {}),
    ],
)
def test_positive_evidence_resolves_the_quarantine(kind, fills) -> None:
    """([KW2b-#2]; ADR-002-002 §18.6/§15.2) Every ``QUARANTINE_RESOLUTION_EDGES`` member actually
    resolves the quarantine, even though every one of its targets ranks *below*
    ``QUARANTINED_UNKNOWN`` in ``PROJECTION_ORDER`` — positive broker evidence for the same
    attempt is the one licit rank decrease ("escaping quarantine requires evidence, never
    assertion").
    """
    core, _, _, attempt_id = _quarantined_core()
    result = core.handle(_egress_event(kind, attempt_id, sequence=3, **fills))

    assert result.halt_reason is None
    assert result.result_disposition is ResultDisposition.APPLIED
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        QUARANTINE_RESOLUTION_EDGES[kind]
    )


@pytest.mark.parametrize("kind", [EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT])
def test_a_repeated_unknown_or_timeout_stays_quarantined(kind) -> None:
    """([KW2b-#2]) Neither UNKNOWN nor TIMEOUT is positive evidence, so repeating either while
    quarantined never resolves it (ADR-002-002 §18.6). Both carry no attempt-distinguishing
    magnitude and no broker execution id, so the repeat collides on the DUPLICATE signature
    exactly as an ordinary byte-identical re-send does.
    """
    core, _, _, attempt_id = _quarantined_core(kind)
    repeat = core.handle(_egress_event(kind, attempt_id, sequence=3))

    assert repeat.halt_reason is HaltReason.RESULT_UNMATCHED
    assert repeat.result_disposition is ResultDisposition.DUPLICATE
    assert core.ledger.outstanding(instrument_key()).capacity_state is (
        CapacityState.QUARANTINED_UNKNOWN
    )


def test_quarantine_resolution_edges_excludes_unknown_and_timeout() -> None:
    """([KW2b-#2]) The closed resolution table never lists UNKNOWN/TIMEOUT as an escape route —
    every *other* member of the closed EgressResultKind vocabulary is, and is, listed.
    """
    assert EgressResultKind.UNKNOWN not in QUARANTINE_RESOLUTION_EDGES
    assert EgressResultKind.TIMEOUT not in QUARANTINE_RESOLUTION_EDGES
    assert set(QUARANTINE_RESOLUTION_EDGES) == set(EgressResultKind) - {
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    }
