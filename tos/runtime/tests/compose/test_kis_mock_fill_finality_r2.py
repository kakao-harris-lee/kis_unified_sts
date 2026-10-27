"""PR-3b Codex round-2 reproductions (the run died on capacity; its three claims are pinned here).

1. **An interrupted proof write must not loop forever.** The proof rows are written before the
   witness row, and a finality re-run decides by the proof ROWS, not the witness flag — so the
   state an interruption leaves (in either write order) converges to exactly one release. A hold
   no re-run can change ends in one durable ``FILL_OBSERVER_FINALITY_STUCK`` row instead.
2. **Replay must equal live after a release.** The live engine's projection release is recorded
   (``ENGINE_PROJECTION_RELEASED``) and the boot replay re-applies it at the same point, so a
   replay core's step-8 ``admits_new_exposure`` answer equals the live one; the next boot is sound.
3. **An earlier day's receipt must not block today's release.** Release reconciliation inquires
   every trading date the scope's receipts carry; an earlier-day order the broker can no longer
   answer for is an explicit hold, not a silent one.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from tos.engine import EngineCore, NullEvidenceSink
from tos.engine.vocabulary import EgressResultKind
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos_runtime.compose._preconditions import _ReplayPreconditions
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.reservation_identity import permit_reservation_id

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from ._fixtures import SCHEME
from .test_kis_mock_e2e_honesty import _boot
from .test_kis_mock_fill_finality_e2e import (
    _ODNO,
    _close,
    _rcl_releases,
    _row,
    _rows,
    _script_broker,
    _witness_paths,
)
from .test_kis_mock_fill_finality_recovery import _acked

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _full(date: str, qty: Decimal, **kw: str) -> dict[str, str]:
    return _row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0), **kw)


class _Interrupted(Exception):
    """The process 'dies' mid-write."""


# ===========================================================================
# 1. interrupted proof write
# ===========================================================================


@pytest.mark.parametrize("witness_written_first", [False, True])
def test_an_interrupted_proof_write_converges_to_one_release(
    witness_written_first,
    config_dir,
    data_dir,
    custody_root,
    tmp_path,
    monkeypatch,
    server,
) -> None:
    """``witness_written_first`` reproduces the pre-fix write order's leftover (witness True, no
    proof) — the state that used to loop on ``PROOF_NOT_RELOADED`` forever."""
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    original = SqliteEvidenceStore.append

    def _dies_at_the_proof(
        self, payload, *, kind, record_class, **kwargs
    ):  # noqa: ANN001
        if kind == "POSTTRADE_FINALITY_PROOF":
            raise _Interrupted
        return original(self, payload, kind=kind, record_class=record_class, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(SqliteEvidenceStore, "append", _dies_at_the_proof)
        with pytest.raises(_Interrupted):
            observer.poll_once()
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    if witness_written_first:
        runtime.inbox.record_finality_witness(attempt_id, True)
    _close(runtime)

    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    observer2 = runtime2.fill_observer
    assert observer2 is not None
    assert observer2.poll_once().reprojected == ((attempt_id, True),)
    assert _rcl_releases(runtime2) == 1
    assert len(_rows(runtime2, "POSTTRADE_FINALITY_PROOF")) == 1
    assert _rows(runtime2, "FILL_OBSERVER_FINALITY_STUCK") == []
    assert observer2.poll_once().reprojected == ()
    _close(runtime2)
    runtime3 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime3.recovery is not None and runtime3.recovery.ready is True
    _close(runtime3)


def test_a_hold_no_rerun_can_change_ends_in_one_stuck_row(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Fault-injected: the durable-proof check claims rows that are not there, so the consumer
    holds ``PROOF_NOT_RELOADED`` — a hold no re-run changes. One stuck row, then no more re-runs
    (across a restart too)."""
    runtime, attempt_id, date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        finality_retry_interval_ms=1,
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    with monkeypatch.context() as patch:
        patch.setattr(
            "tos_runtime.engine.driver.project_finality", lambda *_a, **_k: None
        )
        observer.poll_once()  # FULL_FILL applied, finality never ran
    monkeypatch.setattr(
        "tos_runtime.engine.finality_projection._fill_proof_durable",
        lambda *_a, **_k: True,
    )
    assert observer.poll_once().reprojected == ((attempt_id, False),)
    (stuck,) = _rows(runtime, "FILL_OBSERVER_FINALITY_STUCK")
    assert (stuck["attempt_id"], stuck["hold_reason"]) == (
        attempt_id,
        "PROOF_NOT_RELOADED",
    )
    assert observer.poll_once().reprojected == ()
    _close(runtime)
    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.fill_observer is not None
    assert runtime2.fill_observer.poll_once().reprojected == ()
    assert len(_rows(runtime2, "FILL_OBSERVER_FINALITY_STUCK")) == 1
    _close(runtime2)


# ===========================================================================
# 2. replay equals live after a release
# ===========================================================================


def _replayed_core(
    runtime, *, window_events: int | None = None, expect_ok: bool = True
) -> EventCorrelatingCore:
    """A boot-replay core over ``runtime``'s durable stores — the same recipe
    ``_engine_wiring.verify_replay_or_halt`` (and ``recovery/test_drill.py``) uses."""
    built: list[EventCorrelatingCore] = []

    def _build():
        evidence_store = runtime.evidence_store
        recorded_stage = RecordedStage(evidence_store)
        core = EngineCore(
            registry=runtime.registry,
            stages=dict.fromkeys(
                runtime.core._stages.keys(), recorded_stage
            ),  # noqa: SLF001
            configuration=runtime.core._configuration,  # noqa: SLF001
            preconditions=_ReplayPreconditions(),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
            sink=NullEvidenceSink(),
            scheme=SCHEME,
        )
        wrapped = EventCorrelatingCore(
            core=core, recorded_stage=recorded_stage, scheme=SCHEME
        )
        built.append(wrapped)
        return wrapped

    verdict = replay_engine(
        runtime.inbox,
        runtime.evidence_store,
        runtime.emergency_log,
        _build,
        scheme=SCHEME,
        window_events=window_events,
        rcl_committed=runtime.rcl_log.committed_command,
    )
    assert verdict.ok is expect_ok, verdict
    return built[0]


@pytest.mark.parametrize("path", ["driver", "re-drive"])
def test_replay_reproduces_the_live_release(
    path, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        finality_retry_interval_ms=1,
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    if path == "re-drive":
        with monkeypatch.context() as patch:
            patch.setattr(
                "tos_runtime.engine.driver.project_finality", lambda *_a, **_k: None
            )
            observer.poll_once()
        assert observer.poll_once().reprojected == ((attempt_id, True),)
    else:
        observer.poll_once()
    assert _rcl_releases(runtime) == 1
    (released,) = _rows(runtime, "ENGINE_PROJECTION_RELEASED")
    assert released["attempt_id"] == attempt_id

    key = fx.instrument_key()
    live = runtime.core.ledger.admits_new_exposure(key)
    assert live is True  # the live projection released the scope
    assert _replayed_core(runtime).ledger.admits_new_exposure(key) is live

    # A further decision tick, then a restart: the boot replay is sound.
    runtime.run_once((fx.crossing_event(seq=60),))
    # A windowed replay that no longer contains the attempt has nothing to reproduce for it —
    # the recorded release is skipped, not reported as a divergence.
    _replayed_core(runtime, window_events=1)
    _close(runtime)
    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.recovery is not None and runtime2.recovery.ready is True
    _close(runtime2)


# ===========================================================================
# 3. an earlier day's receipt in the same scope
# ===========================================================================

_EARLIER_ATTEMPT = "attempt-earlier-day"
_EARLIER_ODNO = "0000003000"


def _prev_day(date: str) -> str:
    return (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")


_EARLIER_PERMIT = "afg-permit-earlier-day"
_EARLIER_EVENT = "evt-earlier-day"


def _commit_earlier_day_reservation(runtime) -> str:
    """Commit the earlier attempt's own reservation and the evidence join that names it.

    The reservation goes straight to ``RELEASED`` under ``FINAL_QUANTITY_PROOF`` with a
    positive witness — the state a completed, discharged attempt leaves behind — so it is NOT
    outstanding and cannot affect today's attempt's own step-8 verdict or release path.
    """
    log = runtime.rcl_log
    epoch = log.current_epoch()
    view = log.read_linearizable(writer_epoch=epoch)
    reservation_id = permit_reservation_id(fx.ACCOUNT, fx.INSTRUMENT, _EARLIER_PERMIT)
    receipt = log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.RELEASED,
            scope=ReservationScope(account=fx.ACCOUNT, instrument=fx.INSTRUMENT),
        ),
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id=f"release-{_EARLIER_ATTEMPT}",
        command_digest="dig-earlier-day",
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=True,
    )
    assert isinstance(receipt, AppendReceipt)
    runtime.evidence_store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": _EARLIER_EVENT,
            "bound_identity": _EARLIER_PERMIT,
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    runtime.evidence_store.append(
        {
            "kind": "ATTEMPT_REQUEST_CREATED",
            "attempt_id": _EARLIER_ATTEMPT,
            "event_id": _EARLIER_EVENT,
        },
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )
    return reservation_id


def _record_earlier_day_attempt(runtime, date: str, qty: Decimal) -> None:
    """An attempt completed on an earlier trading day in the same scope.

    Its applied ``FULL_FILL`` receipt and its fill proof (the two rows reconciliation reads),
    plus — #966 — the three rows that make it a REAL completed attempt rather than evidence
    with nothing behind it: the ``ATTEMPT_REQUEST_CREATED``/``FLOW_STEP_ADMITTED`` pair that
    binds its attempt id to the permit its reservation is named after
    (:mod:`tos_runtime.rcl.reservation_lookup`), and that reservation itself, terminal at
    ``RELEASED``.

    Before #966 every attempt in a scope shared ONE reservation id, so this fixture could omit
    all three and still have reconciliation resolve the earlier attempt onto *today's*
    reservation row — a different attempt's. With per-attempt ids that shortcut is gone, which
    is the point: a completed attempt's own row is what proves it existed, and a real one
    always has it (rows are never deleted, only advanced to ``RELEASED``).
    """
    _commit_earlier_day_reservation(runtime)
    runtime.evidence_store.append(
        {
            "instrument_key": {"account": fx.ACCOUNT, "instrument": fx.INSTRUMENT},
            "attempt_id": _EARLIER_ATTEMPT,
            "egress_result_kind": "FULL_FILL",
            "result_disposition": "APPLIED",
            "filled_quantity": format(qty, "f"),
            "remaining_quantity": "0",
            "broker_execution_id": _EARLIER_ODNO,
            "trading_date": date,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    runtime.evidence_store.append(
        {"idempotency_key": f"broker-fqp-proof:{_EARLIER_ATTEMPT}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def test_an_earlier_day_receipt_does_not_block_todays_release(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, today, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    earlier = _prev_day(today)
    _record_earlier_day_attempt(runtime, earlier, qty)
    _script_broker(server, config_dir, today, [_full(today, qty)])
    _balance, earlier_orders = _witness_paths(config_dir, earlier)
    server.set_response(
        earlier_orders,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [_full(earlier, qty, odno=_EARLIER_ODNO)],
            "output2": {},
        },
    )
    observer = runtime.fill_observer
    assert observer is not None
    observer.poll_once()

    assert server.requests_for(earlier_orders)  # the earlier date was inquired
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    assert _rcl_releases(runtime, attempt_id=attempt_id) == 1
    _close(runtime)


def test_an_earlier_day_the_broker_cannot_answer_for_is_an_explicit_hold(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, today, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    earlier = _prev_day(today)
    _record_earlier_day_attempt(runtime, earlier, qty)
    _script_broker(server, config_dir, today, [_full(today, qty)])
    _balance, earlier_orders = _witness_paths(config_dir, earlier)
    server.set_response(earlier_orders, status=500, body=None)
    observer = runtime.fill_observer
    assert observer is not None
    observer.poll_once()

    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert held["reason"] == "NOT_CORROBORATED"
    assert "broker witness unavailable" in (held["detail"] or "")
    assert _rcl_releases(runtime, attempt_id=attempt_id) == 0
    _close(runtime)


# ===========================================================================
# Codex r2 verdict — HIGH 1: a cancel is held, never released (scope narrowed)
# ===========================================================================


@pytest.mark.parametrize(
    "case",
    [
        "unfilled_cancel",
        "cancel_after_partial",
        "separate_cancel_row",
        "derived_only_cancel",
    ],
)
def test_a_cancel_is_one_durable_hold_no_retry_no_release(
    case, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """``unfilled_cancel`` is the review's input: same ODNO/date/symbol, ``cncl_yn=Y``,
    ``ord_qty`` = sealed, ``tot_ccld_qty=0``, ``rmn_qty=0``."""
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    zero = Decimal(0)
    rows = {
        "unfilled_cancel": [
            _row(date=date, ord_qty=qty, filled=zero, remaining=zero, cancelled="Y")
        ],
        "cancel_after_partial": [
            _row(
                date=date, ord_qty=qty, filled=Decimal(1), remaining=zero, cancelled="Y"
            )
        ],
        "derived_only_cancel": [  # Codex r3 MEDIUM (1): no row under our own ODNO
            _row(
                odno="0000004471",
                orgn_odno=_ODNO,
                date=date,
                ord_qty=qty,
                filled=zero,
                remaining=zero,
                cancelled="Y",
            ),
        ],
        "separate_cancel_row": [
            _row(date=date, ord_qty=qty, filled=zero, remaining=qty),
            _row(
                odno="0000004471",
                orgn_odno=_ODNO,
                date=date,
                ord_qty=qty,
                filled=zero,
                remaining=zero,
                cancelled="Y",
            ),
        ],
    }[case]
    orders = _script_broker(server, config_dir, date, rows)
    observer = runtime.fill_observer
    assert observer is not None

    report = observer.poll_once()
    assert report.emitted == ()
    assert len(report.held) == 1
    (hold,) = _rows(runtime, "FILL_OBSERVER_CANCEL_UNSUPPORTED")
    assert hold["attempt_id"] == attempt_id and hold["observed_rows"]
    # Nothing reached the engine, nothing proven or released, the reservation is kept.
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK"]
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert _rcl_releases(runtime) == 0
    # No retry loop: no further read, no second hold, no finality re-run.
    reads = len(server.requests_for(orders))
    later = observer.poll_once()
    assert later.polled is False and later.reprojected == ()
    assert len(server.requests_for(orders)) == reads
    assert len(_rows(runtime, "FILL_OBSERVER_CANCEL_UNSUPPORTED")) == 1
    _close(runtime)

    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.recovery is not None and runtime2.recovery.ready is True
    assert runtime2.fill_observer is not None
    assert runtime2.fill_observer.poll_once().polled is False
    assert _rcl_releases(runtime2) == 0
    _close(runtime2)


# ===========================================================================
# Codex r2 verdict — HIGH 2: a release row replay cannot corroborate is a divergence
# ===========================================================================


@pytest.mark.parametrize(
    "forged",
    [
        # the review's input
        {
            "proof_digest": "nonexistent-proof",
            "evidence_seq": 999999,
            "resolution_generation": -9,
        },
        # well-formed, pointing at evidence that is not the claimed chain
        {
            "proof_digest": "nonexistent-proof",
            "evidence_seq": 1,
            "resolution_generation": 0,
        },
    ],
)
def test_an_uncorroborated_release_row_is_a_replay_divergence(
    forged, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    balance, _orders = _witness_paths(config_dir, date)
    server.set_response(balance, status=500, body=None)  # release held, not committed
    observer = runtime.fill_observer
    assert observer is not None
    observer.poll_once()
    assert _rcl_releases(runtime) == 0
    key = fx.instrument_key()
    assert runtime.core.ledger.admits_new_exposure(key) is False

    runtime.evidence_store.append(
        {"attempt_id": attempt_id, **forged},
        kind="ENGINE_PROJECTION_RELEASED",
        record_class="ENGINE_PROJECTION_RELEASED",
    )
    replayed = _replayed_core(runtime, expect_ok=False)
    assert replayed.ledger.admits_new_exposure(key) is False  # never applied
    halts = [
        r
        for r in _rows(runtime, "REPLAY_DIVERGED")
        if r.get("replay_result_state") == "ENGINE_RELEASE_NOT_REPRODUCED"
    ]
    assert [h["attempt_id"] for h in halts] == [attempt_id]
    assert halts[0]["reason"]
    _close(runtime)


def test_a_cancel_after_an_earlier_unknown_is_still_one_hold(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Codex r3 MEDIUM (2): the attempt is already UNKNOWN (an inconsistent row was fed), then
    its valid ``cncl_yn=Y`` row with a partial fill shows — a hold, not a silent no-op.
    """
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    one, zero = Decimal(1), Decimal(0)
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=one, remaining=zero)],
    )
    observer = runtime.fill_observer
    assert observer is not None
    assert [k for _a, k, _d in observer.poll_once().emitted] == [
        EgressResultKind.UNKNOWN
    ]

    orders = _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=one, remaining=zero, cancelled="Y")],
    )
    report = observer.poll_once()
    assert report.emitted == () and len(report.held) == 1
    (hold,) = _rows(runtime, "FILL_OBSERVER_CANCEL_UNSUPPORTED")
    assert (hold["attempt_id"], hold["reason"]) == (attempt_id, "cancelled_after_fill")
    reads = len(server.requests_for(orders))
    assert observer.poll_once().polled is False
    assert len(server.requests_for(orders)) == reads
    _close(runtime)
    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.fill_observer is not None
    assert runtime2.fill_observer.poll_once().polled is False
    assert len(_rows(runtime2, "FILL_OBSERVER_CANCEL_UNSUPPORTED")) == 1
    _close(runtime2)


# ===========================================================================
# Codex r3 HIGH: replay reads the RCL's COMMITTED release, not pre-commit evidence
# ===========================================================================


class _CommitFails(sqlite3.OperationalError):
    """The RCL's COMMIT fails after its transition evidence row was already written."""


def _fail_next_commits(runtime, times: int) -> list[int]:
    """Make the RCL's next ``times`` commits fail at ``before_commit`` — the transition evidence
    row is already appended (inside the transaction, before COMMIT) and the entry rolls back.
    """
    left = [times]

    def _hook(stage: str) -> None:
        if stage == "before_commit" and left[0] > 0:
            left[0] -= 1
            raise _CommitFails("injected: COMMIT failed")

    runtime.rcl_log._crash_hook = _hook  # noqa: SLF001 - the log's own injection seam
    return left


def test_a_rolled_back_release_then_a_committed_retry_replays_as_one_release(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        finality_retry_interval_ms=1,
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    left = _fail_next_commits(runtime, 1)
    observer.poll_once()  # FULL_FILL -> intent I1 -> transition evidence T1 -> COMMIT fails
    assert left == [0]
    assert _rcl_releases(runtime) == 0
    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert held["reason"] == "RCL_TRANSITION_REFUSED"

    assert observer.poll_once().reprojected == (
        (attempt_id, True),
    )  # I2 -> T2 -> COMMIT
    assert _rcl_releases(runtime) == 1
    transitions = [
        r
        for r in _rows(runtime, "RCL_RESERVATION_TRANSITION")
        if r.get("command_id") == f"release-{attempt_id}"
    ]
    assert len(transitions) == 2  # T1 (rolled back) and T2 (committed)
    assert len(_rows(runtime, "CAPACITY_RELEASE_INTENT")) == 2

    key = fx.instrument_key()
    assert _replayed_core(runtime).ledger.admits_new_exposure(key) is True
    _close(runtime)
    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime2.recovery is not None and runtime2.recovery.ready is True
    _close(runtime2)


def test_a_release_row_over_an_uncommitted_transition_is_a_divergence(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    _fail_next_commits(runtime, 1)
    observer.poll_once()  # I1 -> T1 -> COMMIT fails; nothing committed
    assert _rcl_releases(runtime) == 0
    (intent,) = _rows(runtime, "CAPACITY_RELEASE_INTENT")
    seq = runtime.evidence_store.connection.execute(
        "SELECT seq FROM entries WHERE kind = 'CAPACITY_RELEASE_INTENT'"
    ).fetchone()[0]
    # A release row whose every evidence pointer is genuine — except that the RCL never
    # committed the transition it rests on.
    runtime.evidence_store.append(
        {
            "attempt_id": attempt_id,
            "proof_digest": intent["proof_id"],
            "evidence_seq": seq,
            "resolution_generation": intent["resolution_generation"],
        },
        kind="ENGINE_PROJECTION_RELEASED",
        record_class="ENGINE_PROJECTION_RELEASED",
    )
    key = fx.instrument_key()
    replayed = _replayed_core(runtime, expect_ok=False)
    assert replayed.ledger.admits_new_exposure(key) is False  # never applied
    (halt,) = [
        r
        for r in _rows(runtime, "REPLAY_DIVERGED")
        if r.get("replay_result_state") == "ENGINE_RELEASE_NOT_REPRODUCED"
    ]
    assert "no committed release" in halt["reason"]
    _close(runtime)


# ===========================================================================
# Final review LOW: the restore drill checks releases against the restored RCL too
# ===========================================================================


class _RclStateWithheld:
    """A composed runtime whose RCL committed state is withheld from the drill's replay."""

    class _NoCommits:
        def committed_command(self, command_id: str) -> None:
            del command_id

    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self.rcl_log = self._NoCommits()

    def __getattr__(self, name: str):
        return getattr(self._runtime, name)


@pytest.mark.parametrize("rcl_state", ["given", "withheld"])
def test_the_restore_drill_reads_the_restored_rcl_for_a_recorded_release(
    rcl_state, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    from tos_runtime.operations.backup_set import (
        DurableSetPaths,
        backup_set,
        restore_drill,
        restore_set,
    )

    runtime, _attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _script_broker(server, config_dir, date, [_full(date, qty)])
    observer = runtime.fill_observer
    assert observer is not None
    observer.poll_once()
    assert _rcl_releases(runtime) == 1
    assert _rows(runtime, "ENGINE_PROJECTION_RELEASED")
    assert runtime.recovery is not None
    readiness = runtime.recovery.readiness_verdict.value
    key_provider = runtime.key_provider
    runtime.rcl_log.close()
    runtime.evidence_store.close()
    runtime.inbox.close()
    backup_set(
        DurableSetPaths.from_data_dir(data_dir),
        tmp_path / "backups",
        generation=1,
        readiness_verdict_at_backup=readiness,
    )
    restored = restore_set(
        tmp_path / "backups" / "gen1.set.manifest.json",
        tmp_path / "restored",
        key_provider=key_provider,
    )

    box: dict[str, object] = {}

    def _compose(restored_dir, environment_label):
        del environment_label
        composed = _boot(tmp_path, config_dir, restored_dir, custody_root)
        box["runtime"] = composed
        return composed if rcl_state == "given" else _RclStateWithheld(composed)

    verdict = restore_drill(
        restored,
        compose=_compose,
        build_core=lambda: _replay_build_core(box["runtime"]),
        scheme=SCHEME,
        environment_label="non-live-test",
    )
    if rcl_state == "given":
        assert verdict.result == "PASSED", verdict
    else:
        assert verdict.result == "FAILED"  # a release it cannot check is never trusted
    composed = box["runtime"]
    composed.rcl_log.close()  # type: ignore[attr-defined]
    composed.evidence_store.close()  # type: ignore[attr-defined]


def _replay_build_core(runtime) -> EventCorrelatingCore:
    evidence_store = runtime.evidence_store
    recorded_stage = RecordedStage(evidence_store)
    core = EngineCore(
        registry=runtime.registry,
        stages=dict.fromkeys(
            runtime.core._stages.keys(), recorded_stage
        ),  # noqa: SLF001
        configuration=runtime.core._configuration,  # noqa: SLF001
        preconditions=_ReplayPreconditions(),
        transmit=(
            RecordedTransmit(evidence_store)
            if any_recorded_hand_off(evidence_store)
            else None
        ),
        sink=NullEvidenceSink(),
        scheme=SCHEME,
    )
    return EventCorrelatingCore(core=core, recorded_stage=recorded_stage, scheme=SCHEME)
