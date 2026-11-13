"""PR-3b review round 1 — the three failing inputs, each pinned end to end on the fake KIS server."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.engine.vocabulary import EgressResultKind, ResultDisposition
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose import _finalize_wiring
from tos_runtime.compose._boot_integrity import EngineReplayDiverged
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import _boot, _drive_crossing_tick
from .test_kis_mock_fill_finality_e2e import (
    _ORDER_PATH,
    _ack,
    _close,
    _deploy,
    _rcl_releases,
    _rcl_state,
    _row,
    _rows,
    _script_broker,
    _sealed_quantity,
    _witness_paths,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


_DAY_MS = 86_400_000


def _set_observer_config(config_dir: Path, **values: int) -> None:
    path = config_dir / "fill_observer.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))
    raw.update(values)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _acked(tmp_path, config_dir, data_dir, custody_root, server, monkeypatch, **cfg):
    _deploy(config_dir, custody_root, server, monkeypatch)
    if cfg:
        _set_observer_config(config_dir, **cfg)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    ack = _ack(runtime)
    return runtime, ack["attempt_id"], ack["trading_date"], _sealed_quantity(runtime)


def test_crash_between_consumed_fill_and_projection_still_releases_once(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    observer = runtime.fill_observer
    assert observer is not None
    with monkeypatch.context() as patch:
        patch.setattr(
            "tos_runtime.engine.driver.project_finality", lambda *_a, **_k: None
        )
        report = observer.poll_once()
    assert [(k, d) for _a, k, d in report.emitted] == [
        (EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert _rcl_releases(runtime) == 0
    _close(runtime)

    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    observer2 = runtime2.fill_observer
    assert observer2 is not None
    report = observer2.poll_once()
    assert report.reprojected == ((attempt_id, True),)
    assert report.polled is False and report.emitted == ()
    assert _rcl_releases(runtime2) == 1
    assert _rcl_state(runtime2) is CapacityState.POSITION_CONSUMED
    assert len(_rows(runtime2, "POSTTRADE_FINALITY_PROOF")) == 1
    (reprojected,) = _rows(runtime2, "FINALITY_REPROJECTED")
    assert reprojected["reason"] == "release_not_committed"
    fills = [
        r
        for r in _rows(runtime2, "EGRESS_RESULT_CONSUMED")
        + _rows(runtime2, "RESULT_UNMATCHED")
        if r["egress_result_kind"] == "FULL_FILL"
    ]
    assert len(fills) == 1

    assert observer2.poll_once().reprojected == ()
    _close(runtime2)
    runtime3 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime3.recovery is not None and runtime3.recovery.ready is True
    assert _rcl_releases(runtime3) == 1
    _close(runtime3)


def test_transient_reconciliation_failure_is_retried_until_one_release(
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
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    balance, _orders = _witness_paths(config_dir, date)
    server.set_response(balance, status=500, body=None)
    observer = runtime.fill_observer
    assert observer is not None

    report = observer.poll_once()
    assert [(k, d) for _a, k, d in report.emitted] == [
        (EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert held["reason"] == "NOT_CORROBORATED"
    assert _rcl_releases(runtime) == 0

    report = observer.poll_once()
    assert report.reprojected == ((attempt_id, False),)
    assert _rcl_releases(runtime) == 0

    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    report = observer.poll_once()
    assert report.reprojected == ((attempt_id, True),)
    assert _rcl_releases(runtime) == 1
    assert _rcl_state(runtime) is CapacityState.POSITION_CONSUMED
    assert len(_rows(runtime, "POSTTRADE_FINALITY_PROOF")) == 1
    outstanding = runtime.core.ledger.outstanding(fx.instrument_key())
    assert outstanding is None or outstanding.capacity_state is CapacityState.RELEASED

    assert observer.poll_once().reprojected == ()
    assert _rcl_releases(runtime) == 1
    _close(runtime)


_OTHER_INSTRUMENT = "000660"


def test_a_row_for_another_instrument_produces_no_proof_and_no_release(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, _attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    foreign = _row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))
    foreign["pdno"] = _OTHER_INSTRUMENT
    _script_broker(server, config_dir, date, [foreign])
    observer = runtime.fill_observer
    assert observer is not None

    report = observer.poll_once()
    assert report.read_failed is True and report.emitted == ()
    (failed,) = _rows(runtime, "FILL_OBSERVER_READ_FAILED")
    assert _OTHER_INSTRUMENT in failed["reason"]
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert _rcl_releases(runtime) == 0

    consumer = runtime.driver._release_consumer  # noqa: SLF001
    with pytest.raises(WitnessUnavailable, match=_OTHER_INSTRUMENT):
        consumer.recon_service._witness.observe(  # noqa: SLF001
            WitnessScope(account=fx.ACCOUNT, instrument_keys=(fx.instrument_key(),))
        )
    _close(runtime)


@dataclass
class _RowsWithoutWitnessCheck:
    """An ``OrderRowsReader`` that hands back rows as given — the observer's own instrument check,"""

    rows: tuple[KisOrderRow, ...]

    def order_rows(
        self,
        _scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str | None, tuple[KisOrderRow, ...]]:
        if deadline_expired is not None and deadline_expired():
            raise WitnessUnavailable("deadline")
        return inquiry_date, self.rows


@pytest.mark.parametrize("pdno", [_OTHER_INSTRUMENT, None])
def test_the_observer_refuses_a_row_for_another_or_no_instrument(
    pdno, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, _attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    wire = _row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))
    if pdno is None:
        del wire["pdno"]
    else:
        wire["pdno"] = pdno
    observer = runtime.fill_observer
    assert observer is not None
    observer.orders = _RowsWithoutWitnessCheck((KisOrderRow.from_wire(wire),))

    report = observer.poll_once()
    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.UNKNOWN]
    (observed,) = _rows(runtime, "FILL_OBSERVED")
    assert observed["reason"] == "instrument_mismatch"
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert _rcl_releases(runtime) == 0
    _close(runtime)


def _next_day(date: str) -> str:
    return (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")


def _boot_next_day(tmp_path, config_dir, data_dir, custody_root):
    """Reboot one KST day later (the fill, if any, happened while the runtime was down)."""
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS + _DAY_MS),
    )
    _reach_trusted(runtime)
    return runtime


def test_an_ack_from_the_previous_day_is_read_under_its_own_date(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    runtime, attempt_id, ack_date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        prior_day_poll_interval_ms=1,
    )
    _close(runtime)
    runtime2 = _boot_next_day(tmp_path, config_dir, data_dir, custody_root)
    observer = runtime2.fill_observer
    assert observer is not None
    _script_broker(server, config_dir, _next_day(ack_date), [])

    _balance, ack_orders = _witness_paths(config_dir, ack_date)
    server.set_response(ack_orders, status=500, body=None)
    assert observer.poll_once().read_failed is True
    (failed,) = _rows(runtime2, "FILL_OBSERVER_READ_FAILED")
    assert failed["inquiry_date"] == ack_date

    server.set_response(
        ack_orders,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                _row(date=ack_date, ord_qty=qty, filled=qty, remaining=Decimal(0))
            ],
            "output2": {},
        },
    )
    report = observer.poll_once()
    assert [(a, k, d) for a, k, d in report.emitted] == [
        (attempt_id, EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    (observed,) = _rows(runtime2, "FILL_OBSERVED")
    assert (observed["attempt_id"], observed["trading_date"]) == (attempt_id, ack_date)
    assert _rows(runtime2, "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT") == []
    assert _rcl_releases(runtime2) == 1
    assert observer.poll_once().polled is False
    _close(runtime2)


def test_a_fill_while_down_is_applied_and_released_once_across_three_boots(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """#944: before the fix the restarted engine held no pre-restart reservation, so the"""
    runtime, attempt_id, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _close(runtime)

    runtime2 = _boot(tmp_path, config_dir, data_dir, custody_root)
    held = runtime2.core.ledger.outstanding(runtime2.context_resolver.instrument_key)
    assert held is not None and held.attempt_id == attempt_id
    _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    observer = runtime2.fill_observer
    assert observer is not None
    report = observer.poll_once()
    assert [(a, k, d) for a, k, d in report.emitted] == [
        (attempt_id, EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    assert report.held == ()
    assert _rows(runtime2, "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT") == []
    assert _rows(runtime2, "RESULT_UNMATCHED") == []
    assert _rcl_releases(runtime2) == 1
    assert _rcl_state(runtime2) is CapacityState.POSITION_CONSUMED
    assert observer.poll_once().emitted == ()
    _close(runtime2)

    runtime3 = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert runtime3.recovery is not None and runtime3.recovery.ready is True
    assert (
        runtime3.core.ledger.outstanding(runtime3.context_resolver.instrument_key)
        is None
    )
    observer3 = runtime3.fill_observer
    assert observer3 is not None
    report3 = observer3.poll_once()
    assert report3.emitted == () and report3.reprojected == ()
    assert _rcl_releases(runtime3) == 1
    _close(runtime3)


def test_a_prior_day_ack_is_read_at_the_slower_cadence_not_abandoned(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Codex r2 MEDIUM (replaces the r1 "stop after overdue" rule): a previous day's ACK whose"""
    runtime, attempt_id, ack_date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        overdue_after_ms=1,
        prior_day_poll_interval_ms=3_600_000,
    )
    _close(runtime)
    runtime2 = _boot_next_day(tmp_path, config_dir, data_dir, custody_root)
    observer = runtime2.fill_observer
    assert observer is not None
    working = _row(date=ack_date, ord_qty=qty, filled=Decimal(0), remaining=qty)
    ack_orders = _script_broker(server, config_dir, ack_date, [working])

    assert observer.poll_once().polled is True
    reads = len(server.requests_for(ack_orders))
    assert observer.poll_once().polled is False
    assert len(server.requests_for(ack_orders)) == reads
    observer._last_prior_day_read_ms.clear()  # noqa: SLF001 - advance the cadence clock
    assert observer.poll_once().polled is True
    assert len(server.requests_for(ack_orders)) == reads + 1
    _close(runtime2)


def test_overdue_then_date_change_then_the_read_recovers_and_the_fill_is_observed(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Codex r2 MEDIUM input: OVERDUE on day D, the fill happens during a GET outage, the date"""
    runtime, attempt_id, ack_date, qty = _acked(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        overdue_after_ms=1,
        prior_day_poll_interval_ms=1,
    )
    observer = runtime.fill_observer
    assert observer is not None
    _balance, ack_orders = _witness_paths(config_dir, ack_date)
    server.set_response(ack_orders, status=500, body=None)
    observer.poll_once()
    observer.poll_once()
    (overdue,) = _rows(runtime, "FILL_OBSERVER_OVERDUE")
    assert overdue["attempt_id"] == attempt_id

    observer.today = lambda: _next_day(ack_date)
    assert observer.poll_once().read_failed is True

    _script_broker(
        server,
        config_dir,
        ack_date,
        [_row(date=ack_date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    observer._last_prior_day_read_ms.clear()  # noqa: SLF001 - advance the cadence clock
    report = observer.poll_once()
    assert [(k, d) for _a, k, d in report.emitted] == [
        (EgressResultKind.FULL_FILL, ResultDisposition.APPLIED)
    ]
    assert _rcl_releases(runtime) == 1
    _close(runtime)


def test_an_ack_whose_odno_has_no_usable_digits_is_never_tracked(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Claude review LOW 3: an all-zero ODNO canonicalizes to nothing and would match every row"""
    _deploy(config_dir, custody_root, server, monkeypatch)
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={"rt_cd": "0", "msg_cd": "APBK0013", "output": {"ODNO": "0000000000"}},
    )
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    assert _ack(runtime)["broker_execution_id"] == "0000000000"
    observer = runtime.fill_observer
    assert observer is not None

    before = len(server.all_requests)
    assert observer.poll_once().polled is False
    assert observer.poll_once().polled is False
    assert len(server.all_requests) == before
    (untrackable,) = _rows(runtime, "FILL_OBSERVER_ACK_UNTRACKABLE")
    assert untrackable["broker_execution_id"] == "0000000000"
    assert untrackable["reason"] == "odno_no_digits"
    _close(runtime)


def _evidence_kinds(data_dir: Path, kind: str) -> list[dict]:
    """Rows of ``kind`` straight from the evidence file — the boot refused, so no runtime exists"""
    conn = sqlite3.connect(f"file:{data_dir / 'evidence.sqlite3'}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq", (kind,)
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r[0])["payload"] for r in rows]


def test_a_diverged_boot_replay_hands_back_no_runtime(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """#944: the replay rebuilds the live core's ledger in place, so a replay that diverges"""
    runtime, attempt_id, _date, _qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    runtime.evidence_store.append(
        {
            "attempt_id": attempt_id,
            "proof_digest": "nonexistent-proof",
            "evidence_seq": 1,
            "resolution_generation": 0,
        },
        kind="ENGINE_PROJECTION_RELEASED",
        record_class="ENGINE_PROJECTION_RELEASED",
    )
    _close(runtime)

    composed: list[object] = []
    real = _finalize_wiring.ComposedRuntime

    def _spy(*a: Any, **k: Any) -> object:
        built = real(*a, **k)
        composed.append(built)
        return built

    monkeypatch.setattr(_finalize_wiring, "ComposedRuntime", _spy)
    with pytest.raises(EngineReplayDiverged):
        _boot(tmp_path, config_dir, data_dir, custody_root)
    assert composed == []
    assert [
        r["attempt_id"]
        for r in _evidence_kinds(data_dir, "REPLAY_DIVERGED")
        if r.get("replay_result_state") == "ENGINE_RELEASE_NOT_REPRODUCED"
    ] == [attempt_id]


def test_a_replay_onto_a_ledger_that_already_holds_a_reservation_refuses_the_boot(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """#944 precondition: the replay may only rebuild a projection the live core has not touched."""
    runtime, _attempt, _date, _qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _close(runtime)

    real = _finalize_wiring.verify_replay_or_halt

    def _twice(**kwargs):
        real(**kwargs)
        return real(**kwargs)

    monkeypatch.setattr(_finalize_wiring, "verify_replay_or_halt", _twice)
    with pytest.raises(EngineReplayDiverged, match="not empty before the rebuild"):
        _boot(tmp_path, config_dir, data_dir, custody_root)
    (halt,) = _evidence_kinds(data_dir, "ENGINE_LEDGER_NOT_PRISTINE")
    assert halt["instrument"] == fx.instrument_key().instrument
