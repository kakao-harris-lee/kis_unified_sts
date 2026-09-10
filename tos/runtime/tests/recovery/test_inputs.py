"""Unit tests for :mod:`tos_runtime.recovery.inputs` (TOS Phase 5 W1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.engine.records import event_identity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
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
    """Disclosed limitation (module docstring): nothing writes to the ``tos.staterestore``
    composite-state store yet, so every possibly-live attempt is conservatively flagged
    incomplete today."""
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
