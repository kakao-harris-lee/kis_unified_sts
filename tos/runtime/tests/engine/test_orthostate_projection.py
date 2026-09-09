"""Hermetic tests for :class:`tos_runtime.engine.orthostate_projection.OrthostateProjector`
(TOS Phase 3 Wave 2 Lane C-R; plan §2.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine import EventResult
from tos.engine.records import EgressResultPayload, EngineEvent, ProvisionalReservation
from tos.engine.vocabulary import (
    EgressKnowledge,
    EgressResultKind,
    EventKind,
    OrderingAdmission,
    ResultDisposition,
)
from tos.orthostate import (
    BrokerOrderState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import OrthostateProjector
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

ATTEMPT_ID = "attempt-1"


def _egress_result_event(
    *, kind: EgressResultKind, filled: str | None = None, remaining: str | None = None
) -> EngineEvent:
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=ATTEMPT_ID,
            kind=kind,
            filled_quantity=None if filled is None else Decimal(filled),
            remaining_quantity=None if remaining is None else Decimal(remaining),
        ),
    )


def _applied_result(
    *, knowledge: EgressKnowledge, capacity_state: CapacityState
) -> EventResult:
    reservation = ProvisionalReservation(
        instrument_key=fx.instrument_key(),
        capacity_state=capacity_state,
        knowledge=knowledge,
        proposal_id="proposal-1",
        attempt_id=ATTEMPT_ID,
        filled_quantity=Decimal("1"),
        remaining_quantity=Decimal("0"),
    )
    return EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
        reservation=reservation,
        result_disposition=ResultDisposition.APPLIED,
    )


@pytest.fixture
def projector(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> OrthostateProjector:
    return OrthostateProjector(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        authority_epoch_current=lambda: True,
    )


def test_decision_tick_is_not_projected(projector: OrthostateProjector) -> None:
    result = EventResult(
        kind=EventKind.DECISION_TICK,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
    )
    assert projector.project(event=fx.decision_tick_event(seq=1), result=result) is None


def test_non_applied_result_with_no_reservation_is_not_projected(
    projector: OrthostateProjector,
) -> None:
    event = _egress_result_event(kind=EgressResultKind.TIMEOUT)
    result = EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
        reservation=None,
    )
    assert projector.project(event=event, result=result) is None


def test_mismatched_attempt_result_with_scope_reservation_is_not_projected(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """Wiring-review correction: ``EngineCore._handle_egress_result``'s own non-``APPLIED``
    branch STILL returns ``application.projection`` (the scope's unchanged current
    reservation) — it is not ``None``. Before this gate, a foreign/mismatched-attempt result
    would have been projected using the SCOPE's real state but filed under the mismatched
    payload's OWN (wrong) ``attempt_id`` — a misattribution. Only a genuinely-``APPLIED``
    result may write this attempt's composite."""
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    reservation = ProvisionalReservation(
        instrument_key=fx.instrument_key(),
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        knowledge=EgressKnowledge.SENT_UNCONFIRMED,
        proposal_id="proposal-1",
        attempt_id="attempt-the-real-one",  # NOT this event's attempt_id
    )
    result = EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
        reservation=reservation,
        result_disposition=ResultDisposition.MISMATCHED_ATTEMPT,
    )

    assert projector.project(event=event, result=result) is None
    assert inbox.last_composite(ATTEMPT_ID) is None


def test_full_fill_projects_composite_and_records_it(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )

    composite = projector.project(event=event, result=result)

    assert composite is not None
    assert composite.intent_state is IntentState.ACTIVE
    assert composite.transmission_attempt_state is TransmissionAttemptState.ACK_OBSERVED
    assert composite.broker_order_state is BrokerOrderState.FILLED
    assert composite.knowledge_state is KnowledgeState.CONSISTENT
    assert composite.capacity_state is CapacityState.POSITION_CONSUMED

    stored = inbox.last_composite(ATTEMPT_ID)
    assert stored is not None
    raw, revision = stored
    assert revision == 1
    assert raw["broker_order_state"] == "FILLED"


def test_second_observation_advances_revision(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    first_event = _egress_result_event(
        kind=EgressResultKind.PARTIAL_FILL, filled="1", remaining="1"
    )
    first_result = _applied_result(
        knowledge=EgressKnowledge.PARTIALLY_FILLED,
        capacity_state=CapacityState.PARTIALLY_CONSUMED,
    )
    projector.project(event=first_event, result=first_result)
    _raw, first_revision = inbox.last_composite(ATTEMPT_ID)  # type: ignore[misc]
    assert first_revision == 1

    second_event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="2", remaining="0"
    )
    second_result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )
    projector.project(event=second_event, result=second_result)
    _raw2, second_revision = inbox.last_composite(ATTEMPT_ID)  # type: ignore[misc]
    assert second_revision == 2


def test_coupling_violation_records_halt(
    projector: OrthostateProjector, evidence_store: SqliteEvidenceStore
) -> None:
    """CPL-3 (fill transfer): Broker=FILLED requires Capacity=POSITION_CONSUMED. Deliberately
    supply a mismatched capacity state (as if the ledger and this projection disagreed) so the
    coupling gate must fire — a violation is recorded, never silently normalized."""
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED,
        capacity_state=CapacityState.COMMITTED_UNBOUND,  # wrong: should be POSITION_CONSUMED
    )

    composite = projector.project(event=event, result=result)
    assert composite is not None  # never normalizes — the composite is still returned

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'COUPLING_VIOLATION'"
    ).fetchall()
    assert len(rows) == 1
    import json

    payload = json.loads(rows[0][0])["payload"]
    assert "CPL-3" in payload["violations"]


def test_coupling_violation_latches_a_runtime_wide_new_risk_halt(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """Independent review finding #3 (2026-09-09): a recorded ``COUPLING_VIOLATION`` used to
    block nothing (ADR-002-005 §10 "an immediate new-risk halt condition" was unbacked). It must
    now ALSO durably latch the runtime-wide new-risk halt the driver checks."""
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED,
        capacity_state=CapacityState.COMMITTED_UNBOUND,  # wrong: should be POSITION_CONSUMED
    )
    assert inbox.new_risk_halt() is None

    projector.project(event=event, result=result)

    halt = inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"
    assert halt["event_id"] == f"attempt:{ATTEMPT_ID}"


def test_no_coupling_violation_does_not_latch_new_risk_halt(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """Control for the latch test above: a clean FULL_FILL hand-off must not spuriously latch."""
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )
    projector.project(event=event, result=result)
    assert inbox.new_risk_halt() is None


def test_ownership_violation_when_attempt_mapping_drifts_to_prep_region(
    projector: OrthostateProjector,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review finding #4 (2026-09-09): reachability proof that the NARROWED
    ownership check (Transmission-Attempt only) CAN fail, unlike the two removed tautological
    Broker-Order/Knowledge checks (a full state-pair sweep found zero reachable refusals for
    either — they were dropped, not merely left in place unreachable).

    A test-only monkeypatch of the KERNEL's own CLOSED ``_RESULT_ATTEMPT_TRANSITION`` table
    (never mutated in production — see the module docstring's "Ownership check, narrowed")
    points ``ACK`` at ``PREPARED``, the preparation-region state owned exclusively by
    ``EXECUTION_COORDINATOR``. This projector's fixed ``BROKER_ADAPTER_EGRESS`` actor may never
    write it — the ownership check must refuse, and the refusal must ALSO latch the runtime-wide
    new-risk halt (finding #3), exactly like a coupling violation.
    """
    import json

    import tos.engine.orthostate_projection as kernel_orthostate_projection

    monkeypatch.setitem(
        kernel_orthostate_projection._RESULT_ATTEMPT_TRANSITION,
        EgressResultKind.ACK,
        TransmissionAttemptState.PREPARED,
    )
    event = _egress_result_event(kind=EgressResultKind.ACK)
    result = _applied_result(
        knowledge=EgressKnowledge.ACKNOWLEDGED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )

    composite = projector.project(event=event, result=result)
    assert composite is not None  # never normalizes — still returned and recorded

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'ORTHOSTATE_OWNERSHIP_VIOLATION'"
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])["payload"]
    assert payload["to_state"] == "PREPARED"
    assert payload["from_state"] == "NONE"

    halt = inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"


def test_cancel_crossing_fill_corrects_broker_order_dimension(
    projector: OrthostateProjector,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Independent review finding #8 (2026-09-09): ADR-002-005 §7 "a later valid fill SHALL be
    accepted even after a locally observed CANCELLED/REJECTED; the Broker Order dimension is
    corrected". A ``CANCEL_ACK`` then a late ``FULL_FILL`` for the SAME attempt must correct the
    persisted composite's Broker Order dimension, not leave it frozen at ``CANCEL_PENDING``
    forever.

    **Measured against the real predicate, not assumed (report to the reviewer):** the corrected
    composite is NOT coupling-violation-free — CPL-3 (Broker=FILLED requires
    Capacity=POSITION_CONSUMED) fires because the Capacity axis is deliberately left unchanged,
    and CPL-5 fires too because the correction's own Knowledge=CONFLICTED is in CPL-5's trigger
    set. Both are expected and recorded, not suppressed (module docstring's own disclosure) —
    this is a genuine "our records disagree with the broker" situation and correctly engages the
    new-risk halt latch (finding #3).
    """
    import json

    cancel_event = _egress_result_event(kind=EgressResultKind.CANCEL_ACK)
    cancel_result = _applied_result(
        knowledge=EgressKnowledge.CANCEL_ACKNOWLEDGED,
        capacity_state=CapacityState.RELEASE_PENDING_PROOF,
    )
    cancel_composite = projector.project(event=cancel_event, result=cancel_result)
    assert cancel_composite is not None
    assert cancel_composite.broker_order_state is BrokerOrderState.CANCEL_PENDING

    late_fill_event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    late_fill_result = EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
        reservation=cancel_result.reservation,  # the SCOPE's unchanged current projection
        result_disposition=ResultDisposition.NON_MONOTONIC_PROJECTION,
    )
    corrected = projector.project(event=late_fill_event, result=late_fill_result)
    assert corrected is not None
    assert corrected.broker_order_state is BrokerOrderState.FILLED
    assert corrected.knowledge_state is KnowledgeState.CONFLICTED
    assert (
        corrected.capacity_state is CapacityState.RELEASE_PENDING_PROOF
    )  # unchanged axis

    stored = inbox.last_composite(ATTEMPT_ID)
    assert stored is not None
    raw, revision = stored
    assert revision == 2
    assert raw["broker_order_state"] == "FILLED"

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'COUPLING_VIOLATION'"
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])["payload"]
    assert set(payload["violations"]) == {"CPL-3", "CPL-5"}

    halt = inbox.new_risk_halt()
    assert halt is not None


def test_orphan_and_mismatched_and_duplicate_results_still_project_nothing(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """The cancel-crossing correction (finding #8) is scoped to ``NON_MONOTONIC_PROJECTION`` +
    a fill kind ONLY — every other non-``APPLIED`` disposition must still project nothing, exactly
    as before this fix."""
    for disposition in (
        ResultDisposition.ORPHAN_NO_RESERVATION,
        ResultDisposition.MISMATCHED_ATTEMPT,
        ResultDisposition.DUPLICATE,
        ResultDisposition.QUANTITY_REGRESSION,
    ):
        event = _egress_result_event(
            kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
        )
        result = EventResult(
            kind=EventKind.EGRESS_RESULT,
            instrument_key=fx.instrument_key(),
            ordering=OrderingAdmission.MONOTONE,
            reservation=ProvisionalReservation(
                instrument_key=fx.instrument_key(),
                capacity_state=CapacityState.RELEASE_PENDING_PROOF,
                knowledge=EgressKnowledge.CANCEL_ACKNOWLEDGED,
                proposal_id="proposal-1",
                attempt_id=ATTEMPT_ID,
            ),
            result_disposition=disposition,
        )
        assert projector.project(event=event, result=result) is None
    assert inbox.last_composite(ATTEMPT_ID) is None


def test_non_monotonic_projection_for_a_non_fill_kind_still_projects_nothing(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """A ``NON_MONOTONIC_PROJECTION`` for a kind with no fill magnitudes (e.g. ``CANCEL_ACK``
    itself, or ``ACK``) has no Broker Order correction to make (finding #8's own scope: only
    ``FULL_FILL``/``PARTIAL_FILL`` are cancel-crossing-fill shapes) and must still project
    nothing."""
    event = _egress_result_event(kind=EgressResultKind.CANCEL_ACK)
    result = EventResult(
        kind=EventKind.EGRESS_RESULT,
        instrument_key=fx.instrument_key(),
        ordering=OrderingAdmission.MONOTONE,
        reservation=ProvisionalReservation(
            instrument_key=fx.instrument_key(),
            capacity_state=CapacityState.RELEASE_PENDING_PROOF,
            knowledge=EgressKnowledge.CANCEL_ACKNOWLEDGED,
            proposal_id="proposal-1",
            attempt_id=ATTEMPT_ID,
        ),
        result_disposition=ResultDisposition.NON_MONOTONIC_PROJECTION,
    )
    assert projector.project(event=event, result=result) is None
    assert inbox.last_composite(ATTEMPT_ID) is None


def test_stale_authority_epoch_records_cpl6_violation(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Wiring-review bug found live (team-lead CR-4 dispatch): every genuine hand-off's Attempt
    dimension lands at ``ACK_OBSERVED`` — a send-boundary-and-beyond state — so CPL-6 (an
    authority epoch must be verifiably current at final egress) applies to EVERY FULL_FILL this
    projector ever sees. An ``authority_epoch_current`` callable returning ``False`` (a stale
    epoch) must record a CPL-6 violation; this is the compose e2e regression this projector
    would silently mis-report as a bare, non-actionable halt without a dedicated unit test.
    """
    projector = OrthostateProjector(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        authority_epoch_current=lambda: False,
    )
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )

    composite = projector.project(event=event, result=result)
    assert composite is not None

    import json

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'COUPLING_VIOLATION'"
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])["payload"]
    assert payload["violations"] == ["CPL-6"]


def test_current_authority_epoch_produces_no_cpl6_violation(
    projector: OrthostateProjector, evidence_store: SqliteEvidenceStore
) -> None:
    """Control for the CPL-6 test above: the ``projector`` fixture's ``authority_epoch_current``
    stand-in returns ``True``, so a genuine FULL_FILL hand-off records NO coupling violation at
    all — the compose e2e scenario this fixture's default is meant to mirror."""
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )

    composite = projector.project(event=event, result=result)
    assert composite is not None

    rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'COUPLING_VIOLATION'"
    ).fetchone()[0]
    assert rows == 0


def test_restart_reconstructs_conservatively(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """A restart must never carry forward positive Knowledge (``CONSISTENT``/``RECONCILED``) —
    ``reconstruct_conservative`` downgrades it to ``CONFLICTED``, and independent review finding
    #5 (2026-09-09) now makes that downgrade OBSERVABLE in the persisted composite: it proves a
    SECOND projector instance (a simulated restart, same durable inbox) resumes from the
    persisted composite rather than a fresh unconditional genesis — both via revision continuity
    AND via the resumed composite's own Knowledge value never being less conservative than the
    reconstructed prior's, even though :func:`~tos.engine.orthostate_projection
    .composite_state_for` would otherwise re-derive a fresh ``CONSISTENT`` for this FULL_FILL
    (mutation M11 — dropping ``reconstruct_conservative`` entirely left this exact assertion
    green before the fix; it is red now).
    """
    event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )
    projector.project(event=event, result=result)

    restarted = OrthostateProjector(
        inbox=projector.inbox,
        evidence_store=projector.evidence_store,
        emergency_log=projector.emergency_log,
        authority_epoch_current=lambda: True,
    )
    second_event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    resumed = restarted.project(event=second_event, result=result)
    _raw, revision = inbox.last_composite(ATTEMPT_ID)  # type: ignore[misc]
    assert revision == 2  # continued from the persisted revision, not re-started at 1
    assert resumed is not None
    assert (
        resumed.knowledge_state is KnowledgeState.CONFLICTED
    )  # inherited, not re-derived
    assert (
        resumed.broker_order_state is BrokerOrderState.FILLED
    )  # broker still re-derives fresh


def test_second_call_on_the_same_instance_does_not_re_lock_knowledge(
    projector: OrthostateProjector,
) -> None:
    """Independent review finding #5's own scoping test: the conservative-Knowledge merge only
    applies on THIS instance's FIRST touch of a known attempt — a SECOND observation on the SAME
    (never-restarted) instance must still let Knowledge advance normally, or Knowledge would be
    permanently locked at ``CONFLICTED`` after the very first positive result for the rest of the
    attempt's life (module docstring's own "not a restart-recovery property, it is a
    regression")."""
    first_event = _egress_result_event(
        kind=EgressResultKind.PARTIAL_FILL, filled="1", remaining="1"
    )
    first_result = _applied_result(
        knowledge=EgressKnowledge.PARTIALLY_FILLED,
        capacity_state=CapacityState.PARTIALLY_CONSUMED,
    )
    projector.project(event=first_event, result=first_result)

    second_event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="2", remaining="0"
    )
    second_result = _applied_result(
        knowledge=EgressKnowledge.FILLED, capacity_state=CapacityState.POSITION_CONSUMED
    )
    second_composite = projector.project(event=second_event, result=second_result)
    assert second_composite is not None
    assert second_composite.knowledge_state is KnowledgeState.CONSISTENT  # not locked


# -- pin: replace is only ever a NEW attempt (RFC-005 §11) -------------------


def test_no_resend_or_resubmit_api_exists() -> None:
    """Grep-style pin: neither :class:`EngineDriver` nor :class:`OrthostateProjector` exposes
    any method that re-sends an already-recorded attempt or replays an existing attempt's
    composite forward by hand — the only way a new send happens is a NEW attempt (RFC-005 §11
    "retry is a new send")."""
    banned_substrings = ("resend", "resubmit", "replay_attempt", "resend_attempt")
    for cls in (EngineDriver, OrthostateProjector):
        for name in dir(cls):
            lowered = name.lower()
            assert not any(
                banned in lowered for banned in banned_substrings
            ), f"{cls.__name__}.{name} looks like a resend/resubmit API"


def test_record_composite_replaces_wholesale_never_merges(
    inbox: SqliteEventInbox,
) -> None:
    """:meth:`SqliteEventInbox.record_composite` REPLACES the stored row wholesale — a second
    call with a DIFFERENT (smaller) mapping must not leave any field from the first call
    behind."""
    inbox.record_composite(ATTEMPT_ID, {"a": 1, "b": 2}, observation_revision=1)
    inbox.record_composite(ATTEMPT_ID, {"c": 3}, observation_revision=2)
    raw, revision = inbox.last_composite(ATTEMPT_ID)  # type: ignore[misc]
    assert raw == {"c": 3}
    assert revision == 2
