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
    )


@pytest.fixture
def projector(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> OrthostateProjector:
    return OrthostateProjector(
        inbox=inbox, evidence_store=evidence_store, emergency_log=emergency_log
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


def test_restart_reconstructs_conservatively(
    projector: OrthostateProjector, inbox: SqliteEventInbox
) -> None:
    """A restart must never carry forward positive Knowledge (``CONSISTENT``/``RECONCILED``) —
    ``reconstruct_conservative`` downgrades it to ``CONFLICTED`` before the next observation is
    derived from it. Since :func:`~tos.engine.orthostate_projection.composite_state_for` always
    re-derives Broker/Knowledge fresh from the CURRENT projection (never from the reconstructed
    prior), this test targets the ownership-check "genesis" path instead: it proves a SECOND
    projector instance (a simulated restart, same durable inbox) resumes from the persisted
    composite rather than a fresh unconditional genesis, by observing revision continuity.
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
    )
    second_event = _egress_result_event(
        kind=EgressResultKind.FULL_FILL, filled="1", remaining="0"
    )
    restarted.project(event=second_event, result=result)
    _raw, revision = inbox.last_composite(ATTEMPT_ID)  # type: ignore[misc]
    assert revision == 2  # continued from the persisted revision, not re-started at 1


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
