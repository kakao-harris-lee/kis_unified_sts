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

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from tos.engine import EngineCore, NullEvidenceSink
from tos_runtime.compose._preconditions import _ReplayPreconditions
from tos_runtime.engine.replay import replay_engine
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.store import SqliteEvidenceStore

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


def _record_earlier_day_attempt(runtime, date: str, qty: Decimal) -> None:
    """An attempt completed on an earlier trading day in the same scope: its applied
    ``FULL_FILL`` receipt and its fill proof (the two rows reconciliation reads)."""
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
    runtime, _attempt_id, today, qty = _acked(
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
    assert _rcl_releases(runtime) == 1
    _close(runtime)


def test_an_earlier_day_the_broker_cannot_answer_for_is_an_explicit_hold(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, _attempt_id, today, qty = _acked(
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
    assert _rcl_releases(runtime) == 0
    _close(runtime)


# ===========================================================================
# Codex r2 verdict — HIGH 1: a cancel is held, never released (scope narrowed)
# ===========================================================================


@pytest.mark.parametrize(
    "case", ["unfilled_cancel", "cancel_after_partial", "separate_cancel_row"]
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
