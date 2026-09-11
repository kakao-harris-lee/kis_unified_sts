"""``CapacityObligationRecorder`` tests (kernel round #1 §3, lane B).

Real components throughout: a real :class:`SqliteEvidenceStore`, a real
:class:`EmergencyAppendLog`, a real :class:`SqliteCommitLog` +
:class:`SqliteReservationProjectionReader`, and the real kernel
``tos.cur.obligation_preserved`` predicate (never a stand-in for the
predicate itself — only the reservation-id resolver, which this recorder's
own caller injects, is test-doubled here).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.egressgw.records import GatewayEvidenceRecord
from tos.engine.vocabulary import CommitmentStep
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.obligation import (
    CAPACITY_CONSUMING_STATE_VALUES,
    CapacityObligationRecorder,
)
from tos_runtime.rcl.projection import SqliteReservationProjectionReader

_SCOPE = ReservationScope(account="acct-1", instrument="ES")
_IDENTITY = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")


class _FixedKeyProvider:
    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes")


def _store(tmp_path: Path) -> SqliteEvidenceStore:
    return SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=_FixedKeyProvider()
    )


def _emergency_log(tmp_path: Path) -> EmergencyAppendLog:
    return EmergencyAppendLog(tmp_path / "emergency.jsonl")


def _log(tmp_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
    return SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)


def _commit_reservation(
    log: SqliteCommitLog,
    *,
    reservation_id: str,
    state: CapacityState,
    writer_epoch: int,
) -> None:
    """Commit ``reservation_id`` to ``state`` via a real, gate-admissible
    transition path (test setup only) — ``COMMITTED_UNBOUND ->
    POTENTIALLY_LIVE`` (a strongly-authorized command) for a live
    consuming state, or that SAME setup followed by ``POTENTIALLY_LIVE ->
    RELEASED`` (``FINAL_QUANTITY_PROOF`` + a positive finality witness,
    the kernel's own required release gate) for ``RELEASED``."""
    setup = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=writer_epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=_SCOPE,
        ),
        cause=TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id=f"cmd-{reservation_id}-0",
        command_digest=f"dig-{reservation_id}-0",
        expected_seq=-1,
    )
    assert isinstance(setup, AppendReceipt)
    if state is CapacityState.POTENTIALLY_LIVE:
        return
    if state is not CapacityState.RELEASED:
        raise AssertionError(
            f"_commit_reservation only supports POTENTIALLY_LIVE/RELEASED, got {state!r}"
        )
    result = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=writer_epoch,
            from_state=CapacityState.POTENTIALLY_LIVE,
            to_state=CapacityState.RELEASED,
            scope=_SCOPE,
        ),
        cause=TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id=f"cmd-{reservation_id}-1",
        command_digest=f"dig-{reservation_id}-1",
        expected_seq=setup.seq,
        finality_witness=True,
    )
    assert isinstance(result, AppendReceipt)


class _FixedStateProjection:
    """A minimal :class:`~tos_runtime.rcl.projection.ReservationProjectionReader`
    test double reporting one fixed state for one fixed reservation id — used
    only where the test's own point is the recorder's per-state DECISION
    (which must agree with the kernel predicate for every
    :class:`~tos.rcl.CapacityState` member), not rcl's own transition-gate
    mechanics (already covered by ``tos_runtime.rcl.test_log_reservations``
    and exercised for real by the two dedicated tests above)."""

    def __init__(self, reservation_id: str, state: CapacityState) -> None:
        self._reservation_id = reservation_id
        self._state = state

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self._state if reservation_id == self._reservation_id else None

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        return 0 if reservation_id == self._reservation_id else None

    def all_reservations(self) -> dict[str, CapacityState]:
        return {self._reservation_id: self._state}

    def instrument_state(self, _key: object) -> CapacityState | None:
        return None

    def instrument_last_seq(self, _key: object) -> int | None:
        return None


def test_capacity_consuming_state_values_excludes_only_released() -> None:
    """(module docstring) Mirrors rcl's private ``_LIVE_COMMITTED_STATES`` member-for-member."""
    assert CapacityState.RELEASED.value not in CAPACITY_CONSUMING_STATE_VALUES
    assert (
        frozenset(s.value for s in CapacityState if s is not CapacityState.RELEASED)
        == CAPACITY_CONSUMING_STATE_VALUES
    )
    assert len(CAPACITY_CONSUMING_STATE_VALUES) == len(list(CapacityState)) - 1


def test_no_obligation_appends_no_evidence_and_never_resolves(tmp_path: Path) -> None:
    """``preserved_worst_credible_capacity is None`` AND
    ``preserved_obligation_magnitude_unknown`` is ``False`` (the field's own
    default — left implicit here) => no-op (no evidence, no resolver call).
    kernel round #1 review #4: the no-op condition is now two-part; see
    ``test_magnitude_unknown_obligation_is_not_a_no_op_appends_evidence_and_halts``
    for the case where ``obligation is None`` but the flag is ``True`` and
    the no-op must NOT fire."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    projection = SqliteReservationProjectionReader(log)
    resolver_calls: list[str] = []

    def resolver(attempt_id: str) -> str | None:
        resolver_calls.append(attempt_id)
        return "resv-1"

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=resolver,
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-1",
            preserved_worst_credible_capacity=None,
        )
    )

    assert list(store.iter_entry_meta()) == []
    assert resolver_calls == []
    store.close()
    log.close()


def test_magnitude_unknown_obligation_is_not_a_no_op_appends_evidence_and_halts(
    tmp_path: Path,
) -> None:
    """(kernel round #1 review #4) ``preserved_worst_credible_capacity is
    None`` but ``preserved_obligation_magnitude_unknown`` is ``True`` MUST
    NOT no-op — this is the fifth, most dangerous case (a concrete halt
    whose obligation size was never observed), not "no obligation was ever
    asserted". The resolver IS called, the kernel predicate is asked (which
    forces ``False`` unconditionally for ``magnitude_unknown`` regardless of
    the reservation's actual state — CUR-INV-011:183), evidence is appended
    with ``magnitude_unknown: true``, and the recorder ALWAYS halts, even
    against a reservation that is still safely capacity-consuming."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    writer_epoch = log.acquire_epoch(_IDENTITY)
    _commit_reservation(
        log,
        reservation_id="resv-acct-1-ES",
        state=CapacityState.POTENTIALLY_LIVE,
        writer_epoch=writer_epoch,
    )
    projection = SqliteReservationProjectionReader(log)
    resolver_calls: list[str] = []

    def resolver(attempt_id: str) -> str | None:
        resolver_calls.append(attempt_id)
        return "resv-acct-1-ES"

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=resolver,
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-1",
            preserved_worst_credible_capacity=None,
            preserved_obligation_magnitude_unknown=True,
        )
    )

    assert resolver_calls == ["attempt-1"]
    metas = list(store.iter_entry_meta())
    kinds = [m.kind for m in metas]
    assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
    # ALWAYS halts, even though the reservation is still POTENTIALLY_LIVE
    # (safely capacity-consuming) — magnitude_unknown overrides the state
    # check entirely (CUR-INV-011:183).
    assert kinds.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1
    assert emergency_log.path.exists()
    store.close()
    log.close()


def test_consuming_state_appends_evidence_with_no_halt(tmp_path: Path) -> None:
    """A concrete obligation against a still-capacity-consuming state: evidenced, no halt."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    writer_epoch = log.acquire_epoch(_IDENTITY)
    _commit_reservation(
        log,
        reservation_id="resv-acct-1-ES",
        state=CapacityState.POTENTIALLY_LIVE,
        writer_epoch=writer_epoch,
    )
    projection = SqliteReservationProjectionReader(log)

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: "resv-acct-1-ES",
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-1",
            preserved_worst_credible_capacity=5,
        )
    )

    metas = list(store.iter_entry_meta())
    kinds = [m.kind for m in metas]
    assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
    assert "CAPACITY_OBLIGATION_VIOLATION_ALERT" not in kinds
    assert not emergency_log.path.exists()
    store.close()
    log.close()


def test_released_state_appends_evidence_and_halts(tmp_path: Path) -> None:
    """A concrete obligation against a RELEASED (non-consuming) state: evidenced AND halted."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    writer_epoch = log.acquire_epoch(_IDENTITY)
    _commit_reservation(
        log,
        reservation_id="resv-acct-1-ES",
        state=CapacityState.RELEASED,
        writer_epoch=writer_epoch,
    )
    projection = SqliteReservationProjectionReader(log)

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: "resv-acct-1-ES",
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-1",
            preserved_worst_credible_capacity=5,
        )
    )

    kinds = [m.kind for m in store.iter_entry_meta()]
    assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
    assert kinds.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1
    assert emergency_log.path.exists()
    assert "CAPACITY_OBLIGATION_VIOLATION_ALERT" in emergency_log.path.read_text(
        encoding="utf-8"
    )
    store.close()
    log.close()


def test_unresolvable_reservation_appends_evidence_and_halts(tmp_path: Path) -> None:
    """A resolver returning ``None`` (no reservation bound to this attempt) fails closed."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    projection = SqliteReservationProjectionReader(log)

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: None,
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="attempt-1",
            preserved_worst_credible_capacity=5,
        )
    )

    kinds = [m.kind for m in store.iter_entry_meta()]
    assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
    assert kinds.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1
    store.close()
    log.close()


def test_attempt_id_none_never_calls_the_resolver(tmp_path: Path) -> None:
    """A record with no ``attempt_id`` cannot be resolved — treated as unresolvable, fails closed."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    log = _log(tmp_path, store)
    projection = SqliteReservationProjectionReader(log)
    resolver_calls: list[str] = []

    def resolver(attempt_id: str) -> str | None:
        resolver_calls.append(attempt_id)
        return "resv-acct-1-ES"

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=resolver,
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id=None,
            preserved_worst_credible_capacity=5,
        )
    )

    assert resolver_calls == []
    kinds = [m.kind for m in store.iter_entry_meta()]
    assert kinds.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1
    store.close()
    log.close()


class _MutableStateProjection:
    """A :class:`~tos_runtime.rcl.projection.ReservationProjectionReader`
    test double whose ONE reservation's state can be advanced mid-test —
    used only to demonstrate the resolver's own limitation (independent
    review finding #5): every attempt sharing this account+instrument
    resolves to the SAME reservation id, so the recorder reads whatever
    state that ONE shared reservation holds AT CALL TIME, never a
    per-attempt snapshot."""

    def __init__(self, reservation_id: str, state: CapacityState) -> None:
        self._reservation_id = reservation_id
        self.state = state

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self.state if reservation_id == self._reservation_id else None

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        return 0 if reservation_id == self._reservation_id else None

    def all_reservations(self) -> dict[str, CapacityState]:
        return {self._reservation_id: self.state}

    def instrument_state(self, _key: object) -> CapacityState | None:
        return None

    def instrument_last_seq(self, _key: object) -> int | None:
        return None


def test_resolver_is_not_attempt_scoped_reads_the_shared_reservations_current_state(
    tmp_path: Path,
) -> None:
    """(module docstring, independent review finding #5) The injected
    resolver is per-(account, instrument), not per-attempt: TWO different
    attempts sharing this compose root's one account+instrument BOTH
    resolve to the SAME reservation id. Attempt "a1" is refused while the
    shared reservation is still POTENTIALLY_LIVE (consuming — obligation
    holds, no halt). Before the recorder ever sees attempt "a2"'s refusal,
    the SAME shared reservation legitimately advances to RELEASED. The
    recorder for "a2" reads the reservation's state AS OF NOW, not as of
    "a2"'s own refusal moment — there is no attempt-scoped snapshot to read
    instead. This is the resolver's real, still-live limitation: it always
    reads "the latest" shared state, never an attempt-bound one."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    reservation_id = "resv-acct-1-ES"
    projection = _MutableStateProjection(reservation_id, CapacityState.POTENTIALLY_LIVE)

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        # The SAME resolver formula for every attempt, exactly as wired in
        # production (_wiring.py) — it discards attempt_id entirely.
        reservation_id_resolver=lambda _attempt_id: reservation_id,
    )

    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="a1",
            preserved_worst_credible_capacity=5,
        )
    )
    kinds_after_a1 = [m.kind for m in store.iter_entry_meta()]
    assert kinds_after_a1.count("CAPACITY_OBLIGATION_PRESERVED") == 1
    assert "CAPACITY_OBLIGATION_VIOLATION_ALERT" not in kinds_after_a1

    # The SAME shared reservation legitimately advances — nothing to do
    # with attempt "a1" specifically; this is what "not attempt-scoped"
    # means in practice.
    projection.state = CapacityState.RELEASED

    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="a2",
            preserved_worst_credible_capacity=3,
        )
    )
    kinds_after_a2 = [m.kind for m in store.iter_entry_meta()]
    assert kinds_after_a2.count("CAPACITY_OBLIGATION_PRESERVED") == 2
    # "a2" halts because the SHARED reservation is now RELEASED — the
    # recorder has no way to tell this apart from "a2" itself having
    # caused or witnessed that release; it only ever reads the current
    # shared state.
    assert kinds_after_a2.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1
    store.close()


@pytest.mark.parametrize("state", list(CapacityState))
def test_every_capacity_state_matches_the_kernel_predicate(
    tmp_path: Path, state: CapacityState
) -> None:
    """(state전수) The recorder's halt decision agrees with ``obligation_preserved`` for every state."""
    store = _store(tmp_path)
    emergency_log = _emergency_log(tmp_path)
    reservation_id = f"resv-{state.value}"
    projection = _FixedStateProjection(reservation_id, state)

    recorder = CapacityObligationRecorder(
        store=store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: reservation_id,
    )
    recorder(
        GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id="a1",
            preserved_worst_credible_capacity=1,
        )
    )

    expect_halt = state is CapacityState.RELEASED
    kinds = [m.kind for m in store.iter_entry_meta()]
    assert (kinds.count("CAPACITY_OBLIGATION_VIOLATION_ALERT") == 1) is expect_halt
    store.close()
