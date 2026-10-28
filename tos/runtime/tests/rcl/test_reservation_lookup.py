"""#966 — resolving an ``attempt_id`` onto its reservation from durable evidence only.

:mod:`tos_runtime.rcl.reservation_lookup` joins ``ATTEMPT_REQUEST_CREATED`` and the step-9
``FLOW_STEP_ADMITTED`` row on their shared ``event_id``. These pin both directions, the
fail-closed cases (empty join, ambiguous join, an id the log holds no row for), and the
pre-#966 fallback that keeps an old ledger resolving.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import (
    permit_reservation_id,
    scope_reservation_id,
)
from tos_runtime.rcl.reservation_lookup import (
    attempt_id_for_reservation,
    permit_identity_for_attempt,
    reservation_id_for_attempt,
)

from ..engine.conftest import FixedKeyProvider  # noqa: F401

_ACCOUNT = "88888888-01"
_INSTRUMENT = "005930"
_ATTEMPT = "attempt-lookup-1"
_PERMIT = "afg-permit-lookup-1"
_EVENT = "evt-lookup-1"


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    store = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield store
    store.close()


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    log = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield log
    log.close()


def _record_commit(
    store: SqliteEvidenceStore, *, event_id: str, permit_identity: str
) -> None:
    """The step-9 ``FLOW_STEP_ADMITTED`` row, in the shape the sequencer writes it."""
    store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": event_id,
            "bound_identity": permit_identity,
            "stage_outcome": "ADMIT",
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )


def _record_attempt(
    store: SqliteEvidenceStore, *, event_id: str, attempt_id: str
) -> None:
    store.append(
        {
            "kind": "ATTEMPT_REQUEST_CREATED",
            "step": "ATTEMPT_REQUEST",
            "event_id": event_id,
            "attempt_id": attempt_id,
        },
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )


def _commit_reservation(log: SqliteCommitLog, reservation_id: str) -> None:
    epoch = log.acquire_epoch(
        RuntimeIdentity(cell_id="lookup-cell", process_nonce="lookup-nonce")
    )
    view = log.read_linearizable(writer_epoch=epoch)
    receipt = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.COMMITTED_UNBOUND,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id=f"cmd-{reservation_id}",
        command_digest=f"dig-{reservation_id}",
        expected_seq=-1 if view.last_seq is None else view.last_seq,
    )
    assert isinstance(receipt, AppendReceipt)


def _resolve(log: SqliteCommitLog, store: SqliteEvidenceStore, attempt_id: str):
    return reservation_id_for_attempt(
        store,
        SqliteReservationProjectionReader(log),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        attempt_id=attempt_id,
    )


# ===========================================================================
# the join, both directions
# ===========================================================================


def test_the_join_resolves_an_attempt_onto_its_permit(
    evidence_store: SqliteEvidenceStore,
) -> None:
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    assert permit_identity_for_attempt(evidence_store, _ATTEMPT) == _PERMIT


def test_the_join_resolves_a_permit_back_onto_its_attempt(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """The reverse direction, used to read the ENTRY attempt's recorded fill quantity."""
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    assert attempt_id_for_reservation(evidence_store, _PERMIT) == _ATTEMPT


def test_two_flows_do_not_cross(evidence_store: SqliteEvidenceStore) -> None:
    """Each attempt resolves to ITS OWN flow's permit — the concrete failing input for a
    join that ignored ``event_id`` and simply took the latest step-9 row."""
    _record_commit(evidence_store, event_id="evt-a", permit_identity="afg-permit-a")
    _record_attempt(evidence_store, event_id="evt-a", attempt_id="attempt-a")
    _record_commit(evidence_store, event_id="evt-b", permit_identity="afg-permit-b")
    _record_attempt(evidence_store, event_id="evt-b", attempt_id="attempt-b")
    assert permit_identity_for_attempt(evidence_store, "attempt-a") == "afg-permit-a"
    assert permit_identity_for_attempt(evidence_store, "attempt-b") == "afg-permit-b"


# ===========================================================================
# fail-closed
# ===========================================================================


def test_an_attempt_with_no_evidence_resolves_to_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    assert permit_identity_for_attempt(evidence_store, "attempt-never-seen") is None


def test_an_attempt_whose_flow_never_committed_resolves_to_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A flow that halted before step 9 created an attempt id but no reservation."""
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    assert permit_identity_for_attempt(evidence_store, _ATTEMPT) is None


def test_an_ambiguous_join_resolves_to_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """One flow carrying two distinct step-9 permits is unresolvable, not a pick.

    Concrete failing input for a "take the first" implementation: it would name one of two
    reservations with no basis, and the release consumer would then transition that one.
    """
    _record_commit(evidence_store, event_id=_EVENT, permit_identity="afg-permit-x")
    _record_commit(evidence_store, event_id=_EVENT, permit_identity="afg-permit-y")
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    assert permit_identity_for_attempt(evidence_store, _ATTEMPT) is None


# ===========================================================================
# reservation_id_for_attempt: only ever an id the log holds a row for
# ===========================================================================


def test_resolution_requires_the_log_to_hold_the_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    """The join resolves, but no reservation was ever committed under it -> ``None``.

    This is what keeps a resolved id honest: it is always a row the RCL itself has, never a
    name the function merely spelled.
    """
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    assert _resolve(rcl_log, evidence_store, _ATTEMPT) is None


def test_resolution_returns_the_per_attempt_row_when_it_exists(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    expected = permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT)
    _commit_reservation(rcl_log, expected)
    assert _resolve(rcl_log, evidence_store, _ATTEMPT) == expected


def test_a_pre_966_ledger_resolves_to_its_scope_level_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    """A ledger written before #966 holds one ``resv-{acct}-{instr}`` row for the scope.

    Its flow evidence resolves normally — the two joined rows predate #966 — but no per-permit
    reservation was ever committed, so the scope row is the answer. No migration, no rewrite
    (plan §2.1).
    """
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    legacy = scope_reservation_id(_ACCOUNT, _INSTRUMENT)
    _commit_reservation(rcl_log, legacy)
    assert _resolve(rcl_log, evidence_store, _ATTEMPT) == legacy


def test_a_failed_join_never_falls_through_to_the_scope_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    """review-973 L1: no flow evidence for this attempt -> ``None``, even with a scope row.

    Concrete failing input: the scope holds a reservation committed by a DIFFERENT attempt and
    this attempt has no join rows at all. Falling through handed the caller that other
    attempt's reservation, which the release consumer would then transition.
    """
    _commit_reservation(rcl_log, scope_reservation_id(_ACCOUNT, _INSTRUMENT))
    assert _resolve(rcl_log, evidence_store, "attempt-with-no-flow-evidence") is None


def test_an_ambiguous_join_never_falls_through_to_the_scope_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    """The other half of L1: an unresolvable (two-permit) flow is not a scope-row lookup."""
    _record_commit(evidence_store, event_id=_EVENT, permit_identity="afg-permit-x")
    _record_commit(evidence_store, event_id=_EVENT, permit_identity="afg-permit-y")
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    _commit_reservation(rcl_log, scope_reservation_id(_ACCOUNT, _INSTRUMENT))
    assert _resolve(rcl_log, evidence_store, _ATTEMPT) is None


def test_the_per_attempt_row_wins_over_a_legacy_row(
    rcl_log: SqliteCommitLog, evidence_store: SqliteEvidenceStore
) -> None:
    """A ledger that spans the change holds both; this attempt's OWN row is the answer."""
    legacy = scope_reservation_id(_ACCOUNT, _INSTRUMENT)
    _commit_reservation(rcl_log, legacy)
    _record_commit(evidence_store, event_id=_EVENT, permit_identity=_PERMIT)
    _record_attempt(evidence_store, event_id=_EVENT, attempt_id=_ATTEMPT)
    own = permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT)
    _commit_reservation(rcl_log, own)
    assert _resolve(rcl_log, evidence_store, _ATTEMPT) == own


# ============================================================================
# #976 — the join reads each evidence row once, not once per lookup
# ============================================================================


def _count_decodes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the payload decodes the lookup performs (one per evidence row it reads)."""
    from tos_runtime.rcl import reservation_lookup

    calls = [0]
    real = reservation_lookup._decode

    def counting(text: str) -> object:
        calls[0] += 1
        return real(text)

    monkeypatch.setattr(reservation_lookup, "_decode", counting)
    return calls


def _seed_flows(store: SqliteEvidenceStore, count: int, *, start: int = 0) -> None:
    for i in range(start, start + count):
        _record_attempt(store, event_id=f"evt-{i}", attempt_id=f"attempt-{i}")
        _record_commit(store, event_id=f"evt-{i}", permit_identity=f"permit-{i}")


def test_repeated_lookups_do_not_rescan_the_evidence(
    evidence_store: SqliteEvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failing input (#976, review-973 L5): the recon resolver asks once per attempt, and each
    call decoded every FLOW_STEP_ADMITTED and ATTEMPT_REQUEST_CREATED row — 20 flows, 20
    lookups, 2 kinds read twice per call: 20 x 80 = 1600 decodes. Now each row once: 40.
    """
    _seed_flows(evidence_store, 20)
    decodes = _count_decodes(monkeypatch)
    for i in range(20):
        assert permit_identity_for_attempt(evidence_store, f"attempt-{i}") == (
            f"permit-{i}"
        )
        assert attempt_id_for_reservation(evidence_store, f"permit-{i}") == (
            f"attempt-{i}"
        )
    assert decodes[0] == 40


def test_rows_appended_after_a_lookup_are_seen_and_read_once(
    evidence_store: SqliteEvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_flows(evidence_store, 3)
    decodes = _count_decodes(monkeypatch)
    assert permit_identity_for_attempt(evidence_store, "attempt-3") is None
    _seed_flows(evidence_store, 2, start=3)
    assert permit_identity_for_attempt(evidence_store, "attempt-3") == "permit-3"
    assert attempt_id_for_reservation(evidence_store, "permit-4") == "attempt-4"
    assert decodes[0] == 10  # 6 rows, then the 4 new ones — never the first 6 again


def _old_scan(store: SqliteEvidenceStore, kind: str) -> list[dict]:
    """The pre-#976 read, verbatim in effect: every row of ``kind``, payload unwrapped."""
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    decoded = [json.loads(text).get("payload") for (text,) in rows]
    return [payload for payload in decoded if isinstance(payload, dict)]


def _old_commits(store: SqliteEvidenceStore) -> list[tuple[str, str]]:
    return [
        (p["event_id"], p["bound_identity"])
        for p in _old_scan(store, "FLOW_STEP_ADMITTED")
        if p.get("step") == "ATOMIC_COMMIT"
        and isinstance(p.get("event_id"), str)
        and isinstance(p.get("bound_identity"), str)
    ]


def _old_permit_for(store: SqliteEvidenceStore, attempt_id: str) -> str | None:
    events = {
        p["event_id"]
        for p in _old_scan(store, "ATTEMPT_REQUEST_CREATED")
        if p.get("attempt_id") == attempt_id and isinstance(p.get("event_id"), str)
    }
    found = {permit for event, permit in _old_commits(store) if event in events}
    return next(iter(found)) if events and len(found) == 1 else None


def _old_attempt_for(store: SqliteEvidenceStore, permit: str) -> str | None:
    events = {event for event, committed in _old_commits(store) if committed == permit}
    found = {
        p["attempt_id"]
        for p in _old_scan(store, "ATTEMPT_REQUEST_CREATED")
        if p.get("event_id") in events and isinstance(p.get("attempt_id"), str)
    }
    return next(iter(found)) if events and len(found) == 1 else None


def test_incremental_results_equal_the_old_full_scan_at_every_step(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Results are identical to the pre-#976 full scan after every batch of appends,
    including the fail-closed shapes: an ambiguous permit, an attempt whose flow never
    committed, an admitted row for another step, and non-string ids the old scan skipped.
    """
    probes = [f"attempt-{i}" for i in range(6)] + ["attempt-x", "attempt-amb"]
    permits = [f"permit-{i}" for i in range(6)] + ["permit-amb-1", "permit-amb-2", "p"]

    def check() -> None:
        for attempt_id in probes:
            assert permit_identity_for_attempt(evidence_store, attempt_id) == (
                _old_permit_for(evidence_store, attempt_id)
            ), attempt_id
        for permit in permits:
            assert attempt_id_for_reservation(evidence_store, permit) == (
                _old_attempt_for(evidence_store, permit)
            ), permit

    _seed_flows(evidence_store, 3)
    check()
    _record_attempt(evidence_store, event_id="evt-amb", attempt_id="attempt-amb")
    _record_commit(evidence_store, event_id="evt-amb", permit_identity="permit-amb-1")
    check()
    _record_commit(evidence_store, event_id="evt-amb", permit_identity="permit-amb-2")
    _record_attempt(evidence_store, event_id="evt-x", attempt_id="attempt-x")
    evidence_store.append(
        {"step": "ORDER_CONFORMANCE_PROOF", "event_id": "evt-x", "bound_identity": "p"},
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    evidence_store.append(
        {"step": "ATOMIC_COMMIT", "event_id": 7, "bound_identity": "permit-5"},
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    evidence_store.append(
        {"event_id": "evt-4", "attempt_id": 4},
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )
    _seed_flows(evidence_store, 3, start=3)
    check()
    assert permit_identity_for_attempt(evidence_store, "attempt-amb") is None
    assert attempt_id_for_reservation(evidence_store, "permit-amb-2") == "attempt-amb"
    assert permit_identity_for_attempt(evidence_store, "attempt-x") is None


def test_a_lookup_inside_an_open_transaction_bypasses_the_cache(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Rows read inside a transaction may still roll back, so they are never cached: after the
    rollback the lookup answers from committed rows only."""
    from tos_runtime.rcl import reservation_lookup

    _seed_flows(evidence_store, 1)
    conn = evidence_store.connection
    conn.execute("BEGIN")
    try:
        assert conn.in_transaction
        assert permit_identity_for_attempt(evidence_store, "attempt-0") == "permit-0"
        assert evidence_store not in reservation_lookup._INDEXES
    finally:
        conn.execute("ROLLBACK")
    assert permit_identity_for_attempt(evidence_store, "attempt-0") == "permit-0"
    assert evidence_store in reservation_lookup._INDEXES
