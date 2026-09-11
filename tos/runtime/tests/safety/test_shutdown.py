"""Tests for :mod:`tos_runtime.safety.shutdown` (Phase 5 W3.2 plan §2 decision 9,
lane d3). Fixtures are local to this file, never shared via ``conftest.py`` or
another test module: ``tos/runtime/tests/safety/`` is a shared worktree where
several lanes land tests concurrently (this file is lane d3's own), so a
fixture this file alone needs stays here rather than risking a merge
conflict or an accidental cross-lane dependency in a file another lane also
edits."""

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
from tos.sir import (
    SHUTDOWN_PROHIBITIONS,
    AllFalseIncidentAuthority,
    IncidentRecoveryHandoffPackage,
    recovery_handoff_requires_accepted_barrier,
)
from tos.workload import RuntimeIdentity
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.safety.shutdown import ControlledShutdown, ShutdownOutcome

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_SCOPE = ReservationScope(account="acct-1", instrument="101S06")


class _FixedKeyProvider:
    """A minimal :class:`~tos_runtime.evidence.store.KeyProvider` double — fixed bytes,
    shared across every fixture in this file so a REOPENED store (built with a fresh
    instance of this same class) reads back the identical signing key."""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"shutdown-test-key"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)


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
    """Reopen ``evidence_path`` fresh and return every committed entry's ``kind`` —
    proves durability independent of the (already-closed) instance under test."""
    reopened = SqliteEvidenceStore(evidence_path, key_provider=_FixedKeyProvider())
    try:
        return [row.kind for row in reopened.iter_entry_meta()]
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# nominal shutdown — every step proven, resources durably closed
# ---------------------------------------------------------------------------


def test_nominal_shutdown_proves_every_step(
    shutdown: ControlledShutdown, inbox_path: Path, evidence_path: Path
) -> None:
    outcome = shutdown.run(reason="test-nominal-shutdown")

    assert isinstance(outcome, ShutdownOutcome)
    assert len(outcome.procedure.ordered_steps) == 6
    assert all(step.completed is True for step in outcome.procedure.ordered_steps)
    assert all(outcome.step_completion_proven)
    assert outcome.all_steps_proven is True
    assert outcome.not_broker_finality is True
    assert outcome.procedure.deny_before_stop is True
    assert frozenset(outcome.procedure.prohibited) >= SHUTDOWN_PROHIBITIONS

    # the new-risk-halt latch is durable — a FRESH inbox instance over the same file
    # sees it, independent of the (closed) instance under test.
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
    assert outcome.handoff_package.unresolved_obligations == ()


# ---------------------------------------------------------------------------
# obligations_survive_shutdown is disclosed as never-called (module docstring)
# ---------------------------------------------------------------------------


def test_obligations_survive_shutdown_is_never_called(
    shutdown: ControlledShutdown,
) -> None:
    outcome = shutdown.run(reason="test-obligations-disclosure")
    assert outcome.obligations_survive_shutdown_called is False


# ---------------------------------------------------------------------------
# unresolved RCL reservations transfer as OngoingSafetyObligation
# ---------------------------------------------------------------------------


def test_unresolved_reservation_becomes_an_ongoing_obligation(
    shutdown: ControlledShutdown, rcl_log: SqliteCommitLog
) -> None:
    _commit_reservation(
        rcl_log, reservation_id="res-1", to_state=CapacityState.ATTEMPT_BOUND
    )

    outcome = shutdown.run(reason="test-unresolved-obligation")

    assert len(outcome.obligations) == 1
    obligation = outcome.obligations[0]
    assert obligation.obligation_id == "res-1"
    assert obligation.kind == CapacityState.ATTEMPT_BOUND.value
    assert obligation.resolved is False
    assert obligation.transferred_with_owner_and_evidence is True
    assert outcome.handoff_package.unresolved_obligations == outcome.obligations


def test_released_reservation_is_not_an_obligation(
    shutdown: ControlledShutdown, rcl_log: SqliteCommitLog
) -> None:
    # Reaching RELEASED through the real gated transition path needs a full finality-
    # witness/proof chain (see tos/runtime/tests/rcl/test_finality_witness.py) unrelated
    # to what this test asserts — inserted directly against the reservations PROJECTION
    # table instead (the exact row shape SqliteReservationProjectionReader reads,
    # tos_runtime/rcl/schema.py::CREATE_RESERVATIONS_TABLE_SQL).
    rcl_log._conn.execute(  # noqa: SLF001 — see comment above
        "INSERT INTO reservations (reservation_id, state, last_seq, scope_account, "
        "scope_instrument) VALUES ('res-released', 'RELEASED', 1, 'acct-1', '101S06')"
    )

    outcome = shutdown.run(reason="test-released-not-obligation")

    assert outcome.obligations == ()


# ---------------------------------------------------------------------------
# recovery handoff — honestly NOT accepted at shutdown time (M4's production side)
# ---------------------------------------------------------------------------


def test_handoff_is_honestly_not_accepted_at_shutdown_time(
    shutdown: ControlledShutdown,
) -> None:
    outcome = shutdown.run(reason="test-handoff-honesty")

    assert outcome.handoff_package.recovery_barrier_closed is None
    assert outcome.handoff_package.accepted_by_recovery_session is None
    assert outcome.handoff_accepted is False


def test_handoff_predicate_requires_both_barrier_and_session_true(
    shutdown: ControlledShutdown,
) -> None:
    """M4 pin — the KERNEL predicate itself, called on a package our production code
    never builds (both coordinates faked ``True``), is the ONLY way it admits. This
    proves :meth:`ControlledShutdown._build_handoff_package`'s ``None``/``None`` default
    is not vacuously always-``False`` for some unrelated reason (e.g. a missing field),
    and that faking acceptance is a real, deliberate, never-taken path."""
    outcome = shutdown.run(reason="test-handoff-predicate-shape")
    honest_package = outcome.handoff_package

    faked_package = IncidentRecoveryHandoffPackage(
        handoff_id=honest_package.handoff_id,
        handoff_generation=honest_package.handoff_generation,
        incident_id=honest_package.incident_id,
        active_set_generation=honest_package.active_set_generation,
        unresolved_obligations=honest_package.unresolved_obligations,
        recovery_barrier_closed=True,
        accepted_by_recovery_session=True,
        authority_effect=AllFalseIncidentAuthority(),
    )

    assert recovery_handoff_requires_accepted_barrier(honest_package) is False
    assert recovery_handoff_requires_accepted_barrier(faked_package) is True


# ---------------------------------------------------------------------------
# fail-closed halt policy — a raising close leaves later 1-4 steps unattempted,
# but step 5 (record) and step 6 (custody no-op) are ALWAYS attempted
# ---------------------------------------------------------------------------


def test_inbox_close_raising_halts_later_steps_but_still_records(
    shutdown: ControlledShutdown, inbox: SqliteEventInbox, evidence_path: Path
) -> None:
    def _raise() -> None:
        raise RuntimeError("simulated inbox close failure")

    inbox.close = _raise  # type: ignore[method-assign]

    outcome = shutdown.run(reason="test-inbox-close-raises")
    steps = outcome.procedure.ordered_steps

    assert steps[0].completed is True  # deny_before_stop — ran before the failure
    assert steps[1].completed is True  # obligation transfer — ran before the failure
    assert steps[2].completed is False  # close inbox — raised
    assert steps[3].completed is None  # close rcl log — never attempted (halted)
    assert steps[4].completed is True  # record + close evidence — ALWAYS attempted
    assert steps[5].completed is True  # custody no-op — ALWAYS attempted
    assert outcome.all_steps_proven is False

    # step 5 still recorded evidence despite the halt (module docstring "stop and record").
    assert "CONTROLLED_SHUTDOWN_STEPS" in _entry_kinds(evidence_path)


def test_pending_inbox_event_leaves_disposition_unestablished(
    shutdown: ControlledShutdown, inbox: SqliteEventInbox
) -> None:
    """Step 3 is honestly incomplete (no exception needed) when an admitted event was
    never consumed — closing the connection regardless does not retroactively decide
    anything about it. A row is inserted directly against the inbox's own ``events``
    table (never a full :class:`~tos.engine.records.EngineEvent`, which needs unrelated
    capsule/time fixture machinery this suite has no reason to depend on) — the ONLY
    fact :meth:`ControlledShutdown._close_inbox` reads is
    :attr:`~tos_runtime.engine.inbox.SqliteEventInbox.unconsumed_count`, which is a
    direct ``COUNT(*) ... WHERE consumed_evidence_seq IS NULL`` query this row alone
    satisfies."""
    inbox._conn.execute(  # noqa: SLF001 — see docstring: the minimal honest row shape
        "INSERT INTO events (seq, event_id, kind, account, instrument, reference_json, "
        "payload_json, payload_digest, consumed_evidence_seq, consumed_generation) "
        "VALUES (1, 'ev-pending-1', 'DECISION_TICK', 'acct-1', '101S06', '{}', '{}', "
        "'digest-1', NULL, NULL)"
    )  # isolation_level=None (autocommit) — the row is durable as soon as execute() returns
    assert inbox.unconsumed_count == 1

    outcome = shutdown.run(reason="test-pending-inbox-event")
    steps = outcome.procedure.ordered_steps

    assert (
        steps[2].completed is False
    )  # ESTABLISH_DISPOSITION... — one event still pending
    assert steps[3].completed is None  # halted — rcl log close never attempted


# ---------------------------------------------------------------------------
# secret hygiene — no evidence payload this module writes carries anything
# credential-shaped (this shutdown never reads custody at all — see the
# module docstring's "close custody" section)
# ---------------------------------------------------------------------------


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
