"""Unit tests for :mod:`tos_runtime.recovery.inputs` (TOS Phase 5 W1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.engine.records import event_identity
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recovery.barrier import RecoveryBarrier
from tos_runtime.recovery.composite_state_writer import CompositeStateWriter
from tos_runtime.recovery.inputs import assemble_recovery_inputs
from tos_runtime.time.service import TimeServiceNotStarted

from .conftest import SCHEME, fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class _NeverStartedTimeService:
    """A minimal :class:`~tos_runtime.time.service.TrustworthyTimeService` double for these
    unit tests, which do not boot a full compose chain: raises the SAME
    ``TimeServiceNotStarted`` a genuinely never-started real service raises, so
    :mod:`tos_runtime.recovery.reconciliation`'s own fail-closed freshness path is exercised
    exactly as it would be against a real one."""

    def current_snapshot(self):
        raise TimeServiceNotStarted("never started (test double)")


@pytest.fixture()
def rcl_log(tmp_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def _assemble(
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
):
    return assemble_recovery_inputs(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        scheme=SCHEME,
        window_events=None,
        custody_root=custody_root,
        composite_state_store_path=tmp_path / "composite_state.sqlite3",
        time_service=_NeverStartedTimeService(),
        account=fx.instrument_key().account,
        instrument=fx.instrument_key().instrument,
    )


def test_genesis_boot_has_no_possibly_live_or_legacy_facts(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.possibly_live_attempts == ()
    assert inputs.legacy_receipts.count == 0
    assert inputs.inbox_unconsumed_count == 0
    assert inputs.composite_state_incomplete_attempt_ids == ()
    # A genuinely empty RCL log has never acquired an epoch — current_epoch() reports 0.
    assert inputs.rcl_writer_epoch == 0
    assert inputs.rcl_runtime_generation is None
    assert inputs.evidence_tip_seq is None
    assert inputs.evidence_tip_key_generation is None


def test_custody_identity_is_read_from_the_real_manifest(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.custody_environment_label == "non-live-test"
    assert inputs.custody_manifest_digest is not None
    assert len(inputs.custody_manifest_digest) == 64  # sha256 hex digest


def test_unconsumed_event_is_counted_but_not_possibly_live(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    inbox.enqueue(fx.crossing_event(seq=1))
    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.inbox_unconsumed_count == 1
    assert inputs.possibly_live_attempts == ()


def test_possibly_live_attempt_is_also_composite_state_incomplete(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    """This possibly-live attempt has a durable ``EVENT_HANDLING_STARTED`` marker but NO
    ``SEND_HANDED_OFF`` row at all (crash window 1 — the flow never reached the send boundary),
    so :func:`~tos_runtime.recovery.reconciliation.send_handed_off_attempt_id` cannot resolve an
    ``attempt_id`` to reload a composite for — independent-review finding F3's own ``NO_ATTEMPT_ID``
    path, conservatively incomplete for a genuinely different reason than "nothing writes to the
    store" (see ``test_composite_state_is_complete_after_a_clean_hand_off`` below for the case
    where a composite genuinely WAS written)."""
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = evidence_store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )

    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert [attempt.event_id for attempt in inputs.possibly_live_attempts] == [event_id]
    assert inputs.composite_state_incomplete_attempt_ids == (event_id,)


def _composite() -> CompositeState:
    return CompositeState(
        intent_identity="proposal-digest-not-the-attempt-id",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=KnowledgeState.CONSISTENT,
        capacity_state=CapacityState.POSITION_CONSUMED,
    )


def test_composite_state_is_complete_after_a_clean_hand_off(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    """Independent-review finding F3 (2026-09-10): a possibly-live attempt whose ``event_id``
    DOES durably resolve to an ``attempt_id`` (via ``SEND_HANDED_OFF``), and whose composite was
    ALREADY written under that ``attempt_id`` (:class:`~tos_runtime.recovery
    .composite_state_writer.CompositeStateWriter`'s own new keying), is reported COMPLETE — the
    write and read sides finally agree on the same identity."""
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = evidence_store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    attempt_id = "attempt-clean-hand-off"
    evidence_store.append(
        {"event_id": event_id, "attempt_id": attempt_id},
        kind="SEND_HANDED_OFF",
        record_class="SEND_HANDED_OFF",
    )
    writer = CompositeStateWriter(tmp_path / "composite_state.sqlite3")
    writer(attempt_id, _composite())

    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert [attempt.event_id for attempt in inputs.possibly_live_attempts] == [event_id]
    assert inputs.composite_state_incomplete_attempt_ids == ()


def test_forged_divergent_replay_row_holds_the_barrier(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    """Independent-review finding F5 (2026-09-10) — obligation 1's mutation guard: a
    ``REPLAY_DIVERGED`` row present (forged directly here, mirroring how
    ``tos_runtime.engine.replay`` itself would record a genuine divergence) with NO
    ``REPLAY_VERDICT_IDENTICAL`` row makes ``replay_verdict_ok`` ``False`` — obligation 1 is no
    longer a hardcoded ``ok=True`` a mutation removing the real check could pass silently.
    """
    evidence_store.append(
        {"event_id": "forged-divergent-event", "detail": "forged for this test"},
        kind="REPLAY_DIVERGED",
        record_class="REPLAY_DIVERGED",
    )

    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.replay_verdict_ok is False

    verdict = RecoveryBarrier.verdict(inputs)
    assert verdict.ready is False


def test_real_replay_verdict_row_satisfies_obligation_one(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    """The positive half: a durable ``REPLAY_VERDICT_IDENTICAL`` row with no
    ``REPLAY_DIVERGED`` row makes ``replay_verdict_ok`` ``True`` — the SAME row
    ``tos_runtime.compose._engine_wiring.verify_replay_or_halt`` appends on every clean boot.
    """
    evidence_store.append(
        {"total_compared": 0, "uncompared": 0, "has_unverifiable_receipts": False},
        kind="REPLAY_VERDICT_IDENTICAL",
        record_class="REPLAY_VERDICT_IDENTICAL",
    )

    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.replay_verdict_ok is True


def test_malformed_inbox_row_fails_obligation_five_gracefully(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    """Independent-review finding F5 (2026-09-10) — obligation 5's mutation guard: a row whose
    ``payload_json`` cannot parse through the kernel ``EngineEvent`` model must resolve to a
    graceful ``inbox_events_parseable=False`` (HOLD), never an unhandled exception escaping
    :func:`assemble_recovery_inputs`."""
    inbox._conn.execute(  # no public seam for a raw malformed insert -- direct access
        "INSERT INTO events (seq, event_id, kind, account, instrument, reference_json, "
        "payload_json, payload_digest, consumed_evidence_seq, consumed_generation) "
        "VALUES (1, 'malformed-event', 'DECISION_TICK', 'acct-1', '005930', '{}', "
        "'{\"not\": \"a valid EngineEvent shape\"}', 'digest-x', NULL, NULL)"
    )

    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.inbox_events_parseable is False

    verdict = RecoveryBarrier.verdict(inputs)
    assert verdict.ready is False


def test_well_formed_inbox_rows_satisfy_obligation_five(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    tmp_path: Path,
    custody_root: Path,
) -> None:
    inbox.enqueue(fx.crossing_event(seq=1))
    inputs = _assemble(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        tmp_path=tmp_path,
        custody_root=custody_root,
    )
    assert inputs.inbox_events_parseable is True
