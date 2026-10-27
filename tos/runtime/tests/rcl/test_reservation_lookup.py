"""#966 — resolving an ``attempt_id`` onto its reservation from durable evidence only.

:mod:`tos_runtime.rcl.reservation_lookup` joins ``ATTEMPT_REQUEST_CREATED`` and the step-9
``FLOW_STEP_ADMITTED`` row on their shared ``event_id``. These pin both directions, the
fail-closed cases (empty join, ambiguous join, an id the log holds no row for), and the
pre-#966 fallback that keeps an old ledger resolving.
"""

from __future__ import annotations

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
