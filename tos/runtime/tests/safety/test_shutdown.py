"""Tests for :mod:`tos_runtime.safety.shutdown` — latch first, then close, then"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.safety.shutdown import (
    STEP_LATCH_NEW_RISK_HALT,
    ControlledShutdown,
    ShutdownOutcome,
)

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


class _FixedKeyProvider:
    """A minimal :class:`~tos_runtime.evidence.store.KeyProvider` double — fixed bytes,"""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"shutdown-test-key"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)

    def generations(self) -> tuple[int, ...]:
        return (self._key_generation,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return self._key


def _write_custody_manifest(path: Path, *, environment_label: str) -> None:
    path.write_text(f'environment_label: "{environment_label}"\nscopes: {{}}\n')


@pytest.fixture()
def evidence_path(tmp_path: Path) -> Path:
    return tmp_path / "evidence.sqlite3"


@pytest.fixture()
def inbox_path(tmp_path: Path) -> Path:
    return tmp_path / "inbox.sqlite3"


@pytest.fixture()
def rcl_path(tmp_path: Path) -> Path:
    return tmp_path / "rcl.sqlite3"


@pytest.fixture()
def custody_root(tmp_path: Path) -> Path:
    root = tmp_path / "custody"
    root.mkdir()
    _write_custody_manifest(
        root / "custody.manifest.yaml", environment_label="test-cell"
    )
    return root


@pytest.fixture()
def evidence_store(evidence_path: Path) -> SqliteEvidenceStore:
    return SqliteEvidenceStore(evidence_path, key_provider=_FixedKeyProvider())


@pytest.fixture()
def inbox(inbox_path: Path) -> SqliteEventInbox:
    return SqliteEventInbox(inbox_path, scheme=_SCHEME)


@pytest.fixture()
def rcl_log(rcl_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
    return SqliteCommitLog(rcl_path, evidence_port=evidence_store)


@pytest.fixture()
def custody(custody_root: Path, evidence_store: SqliteEvidenceStore) -> FileCustody:
    return FileCustody(
        custody_root,
        environment_label="test-cell",
        expected_owner_uid=os.getuid(),
        evidence=evidence_store,
    )


@pytest.fixture()
def key_provider(custody_root: Path) -> FileKeyProvider:
    return FileKeyProvider(custody_root, expected_owner_uid=os.getuid())


@pytest.fixture()
def shutdown(
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    custody: FileCustody,
    key_provider: FileKeyProvider,
) -> ControlledShutdown:
    return ControlledShutdown(
        inbox=inbox,
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        custody=custody,
        key_provider=key_provider,
    )


def _commit_reservation(
    rcl_log: SqliteCommitLog, *, reservation_id: str, to_state: CapacityState
) -> None:
    epoch = rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="test-cell", process_nonce="n1")
    )
    transition = CapacityReservationTransition(
        reservation_id=reservation_id,
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=to_state,
        scope=_SCOPE,
    )
    result = rcl_log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id=f"cmd-{reservation_id}",
        command_digest=f"digest-{reservation_id}",
        expected_seq=-1,
    )
    assert isinstance(result, AppendReceipt)


def _entry_kinds(evidence_path: Path) -> list[str]:
    """Reopen ``evidence_path`` fresh and return every committed entry's ``kind`` —"""
    reopened = SqliteEvidenceStore(evidence_path, key_provider=_FixedKeyProvider())
    try:
        return [row.kind for row in reopened.iter_entry_meta()]
    finally:
        reopened.close()


def test_nominal_shutdown_proves_every_step(
    shutdown: ControlledShutdown, inbox_path: Path, evidence_path: Path
) -> None:
    outcome = shutdown.run(reason="test-nominal-shutdown")

    assert isinstance(outcome, ShutdownOutcome)
    assert len(outcome.steps) == 5
    assert all(step.completed is True for step in outcome.steps)
    assert outcome.all_steps_proven is True
    assert outcome.latched_before_close is True
    assert outcome.steps[0].step_kind == STEP_LATCH_NEW_RISK_HALT

    reopened_inbox = SqliteEventInbox(inbox_path, scheme=_SCHEME)
    try:
        assert reopened_inbox.new_risk_halt() is not None
    finally:
        reopened_inbox.close()

    kinds = _entry_kinds(evidence_path)
    assert "CONTROLLED_SHUTDOWN_STARTED" in kinds
    assert "CONTROLLED_SHUTDOWN_STEPS" in kinds
    assert "CONTROLLED_SHUTDOWN_HANDOFF" in kinds


def test_no_obligations_when_no_reservation_is_outstanding(
    shutdown: ControlledShutdown,
) -> None:
    outcome = shutdown.run(reason="test-no-obligations")
    assert outcome.obligations == ()


def test_unresolved_reservation_becomes_an_ongoing_obligation(
    shutdown: ControlledShutdown, rcl_log: SqliteCommitLog
) -> None:
    _commit_reservation(
        rcl_log, reservation_id="res-1", to_state=CapacityState.ATTEMPT_BOUND
    )

    outcome = shutdown.run(reason="test-unresolved-obligation")

    assert outcome.obligations == (("res-1", CapacityState.ATTEMPT_BOUND.value),)


def test_released_reservation_is_not_an_obligation(
    shutdown: ControlledShutdown, rcl_log: SqliteCommitLog
) -> None:
    rcl_log._conn.execute(  # noqa: SLF001 — see comment above
        "INSERT INTO reservations (reservation_id, state, last_seq, scope_account, "
        "scope_instrument) VALUES ('res-released', 'RELEASED', 1, 'acct-1', '101S06')"
    )

    outcome = shutdown.run(reason="test-released-not-obligation")

    assert outcome.obligations == ()


def test_the_handoff_id_comes_from_the_started_evidence_row(
    shutdown: ControlledShutdown,
) -> None:
    """A real, unique coordinate — never a fabricated id. The next boot's recovery"""
    outcome = shutdown.run(reason="test-handoff-honesty")

    assert outcome.handoff_id is not None
    assert outcome.handoff_id.startswith("controlled-shutdown-evidence-seq-")


def test_inbox_close_raising_halts_later_steps_but_still_records(
    shutdown: ControlledShutdown, inbox: SqliteEventInbox, evidence_path: Path
) -> None:
    def _raise() -> None:
        raise RuntimeError("simulated inbox close failure")

    inbox.close = _raise  # type: ignore[method-assign]

    outcome = shutdown.run(reason="test-inbox-close-raises")
    steps = outcome.steps

    assert steps[0].completed is True
    assert steps[1].completed is True
    assert steps[2].completed is False
    assert steps[3].completed is None
    assert steps[4].completed is True
    assert outcome.all_steps_proven is False

    assert "CONTROLLED_SHUTDOWN_STEPS" in _entry_kinds(evidence_path)


def test_pending_inbox_event_leaves_disposition_unestablished(
    shutdown: ControlledShutdown, inbox: SqliteEventInbox
) -> None:
    """Step 3 is honestly incomplete (no exception needed) when an admitted event was"""
    inbox._conn.execute(  # noqa: SLF001 — see docstring: the minimal honest row shape
        "INSERT INTO events (seq, event_id, kind, account, instrument, reference_json, "
        "payload_json, payload_digest, consumed_evidence_seq, consumed_generation) "
        "VALUES (1, 'ev-pending-1', 'DECISION_TICK', 'acct-1', '101S06', '{}', '{}', "
        "'digest-1', NULL, NULL)"
    )
    assert inbox.unconsumed_count == 1

    outcome = shutdown.run(reason="test-pending-inbox-event")
    steps = outcome.steps

    assert steps[2].completed is False
    assert steps[3].completed is None


def test_no_evidence_payload_carries_a_credential_shaped_field(
    shutdown: ControlledShutdown, evidence_path: Path
) -> None:
    shutdown.run(reason="test-secret-hygiene")
    reopened = SqliteEvidenceStore(evidence_path, key_provider=_FixedKeyProvider())
    try:
        blocked = {
            "secret",
            "password",
            "credential",
            "token",
            "key_bytes",
            "private_key",
        }
        for row in reopened.iter_entry_meta():
            for term in blocked:
                assert term not in row.kind.lower()
                assert term not in row.record_class.lower()
    finally:
        reopened.close()
