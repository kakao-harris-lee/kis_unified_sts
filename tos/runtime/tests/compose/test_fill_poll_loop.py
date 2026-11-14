"""Who calls the fill observer: the session loop, once per pass (PR-3b follow-up, rescope plan"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import yaml
from tos.engine.vocabulary import EgressResultKind
from tos.rcl import CapacityState
from tos_runtime.compose._broker_posttrade_wiring import (
    DeferredKisWitness,
    fill_observer_pass,
)
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_CONFIG_NAME,
    load_fill_observer_config,
)

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import _ORDER_PATH, _boot, _drive_crossing_tick
from .test_kis_mock_fill_finality_e2e import (
    _ODNO,
    _ack,
    _acked,
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
from .test_marketfeed_wiring import (
    _observation_line,
    _write_critical_input_policy,
    _write_journal,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NON_CROSSING_CLOSE = (fx.LOWER_BAND + fx.UPPER_BAND) // 2
_FAST_POLL_INTERVAL_MS = 20
_REAL_SLEEP_SECONDS = 0.03
_JOURNAL_PASS_ALLOWANCE_MS = 100


_LOOP_TEST_APP_KEY_INTERVAL_MS = 50


@pytest.fixture(autouse=True)
def _short_app_key_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    original = fx.write_kis_mock_transport_config

    def _write(config_dir: Path, **kwargs: Any) -> Path:
        kwargs.setdefault("min_send_interval_ms", _LOOP_TEST_APP_KEY_INTERVAL_MS)
        return original(config_dir, **kwargs)

    monkeypatch.setattr(fx, "write_kis_mock_transport_config", _write)


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _as_of_ms() -> int:
    return int(time.time() * 1000) - 100


def _write_marketfeed_config(
    config_dir: Path,
    *,
    journal_path: Path,
    direction: str = "LONG",
    allowance_ms: int = _JOURNAL_PASS_ALLOWANCE_MS,
    poll_interval_ms: int = _FAST_POLL_INTERVAL_MS,
) -> None:
    """``test_run_e2e.py``'s fast marketfeed config, with ``direction`` open to a caller (§3"""
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(
            {
                "instruments": [fx.INSTRUMENT],
                "instrument_class": fx.INSTRUMENT_CLASS,
                "account": fx.ACCOUNT,
                "direction": direction,
                "quantity_basis": "RISK",
                "unit": "contract",
                "intake_kind": "journal",
                "journal_path": str(journal_path),
                "poll_interval_ms": poll_interval_ms,
                "journal_pass_allowance_ms": allowance_ms,
                "time_evaluate_closed_interval_ms": 60_000,
                "snapshot_age_bound": 20,
                "interval_width": 10,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _wire_tick_source(
    config_dir: Path,
    tmp_path: Path,
    *,
    direction: str = "LONG",
    allowance_ms: int = _JOURNAL_PASS_ALLOWANCE_MS,
    poll_interval_ms: int = _FAST_POLL_INTERVAL_MS,
) -> int:
    """Put a journal-backed tick source under ``config_dir`` and return its observation's"""
    journal_path = tmp_path / "journal.jsonl"
    as_of_ms = _as_of_ms()
    _write_journal(
        journal_path,
        [
            _observation_line(
                raw_event_id="raw-fill-poll-loop",
                as_of_ms=as_of_ms,
                close=_NON_CROSSING_CLOSE,
            )
        ],
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir,
        journal_path=journal_path,
        direction=direction,
        allowance_ms=allowance_ms,
        poll_interval_ms=poll_interval_ms,
    )
    return as_of_ms


def _retune_observer_poll_interval(
    config_dir: Path, poll_interval_ms: int, *, poll_deadline_ms: int | None = None
) -> None:
    """Rewrite the deployed ``fill_observer.yaml``'s cadence keys (every other key kept)."""
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["poll_interval_ms"] = poll_interval_ms
    if poll_deadline_ms is not None:
        raw["poll_deadline_ms"] = poll_deadline_ms
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _script_slow_order_inquiry(
    server: FakeKisServer,
    config_dir: Path,
    date: str,
    *,
    delay_s: float,
    rows: list[dict[str, Any]] | None = None,
) -> str:
    """``_script_broker`` with a REAL delay on the order inquiry — the fake server's own"""
    balance, orders = _witness_paths(config_dir, date)
    server.set_response(
        balance,
        status=200,
        body={"rt_cd": "0", "output1": [], "output2": [{"dnca_tot_amt": "1000000"}]},
    )
    server.set_response(
        orders,
        status=200,
        body={"rt_cd": "0", "output1": rows or [], "output2": {}},
        delay_s=delay_s,
    )
    return orders


def _real_short_sleep(_seconds: float) -> None:
    time.sleep(_REAL_SLEEP_SECONDS)


def _stop_after(n: int):
    """``run_forever`` checks ``stop()`` before every pass, so this admits exactly ``n``."""
    passes = {"count": 0}

    def stop() -> bool:
        if passes["count"] >= n:
            return True
        passes["count"] += 1
        return False

    return stop


def _stop_when(done: Callable[[], bool], *, max_passes: int = 300):
    """Admit passes until ``done()`` or ``max_passes``. Issue #950: the observer's broker read"""
    passes = {"count": 0}

    def stop() -> bool:
        if passes["count"] >= max_passes or done():
            return True
        passes["count"] += 1
        return False

    return stop


class _SlowHook:
    """Stands in for ``runtime.fill_observer`` with a hook that takes ``seconds`` on the loop"""

    def __init__(self, seconds: float, *, slow_passes: int | None = None) -> None:
        self.seconds = seconds
        self.slow_passes = slow_passes

    def poll_if_due(self) -> None:
        if self.slow_passes is None or self.slow_passes > 0:
            time.sleep(self.seconds)
        if self.slow_passes is not None:
            self.slow_passes -= 1

    def close(self) -> None:
        return None


def _install_slow_hook(runtime: ComposedRuntime, hook: _SlowHook) -> None:
    real = runtime.fill_observer
    if real is not None:
        real.close()
    runtime.fill_observer = cast(Any, hook)


def _fake_runtime(observer: Any) -> ComposedRuntime:
    """A stand-in for the one attribute :func:`fill_observer_pass` reads. Typed through"""
    return cast(ComposedRuntime, SimpleNamespace(fill_observer=observer))


def _evidence_kinds(runtime: ComposedRuntime) -> list[str]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT DISTINCT kind FROM entries"
    ).fetchall()
    return [row[0] for row in rows]


def test_the_pass_polls_nothing_when_this_boot_has_no_observer() -> None:
    """Every boot that is not a stock MOCK order tree, and a stock MOCK boot whose recovery"""
    fill_observer_pass(_fake_runtime(None))()


def test_the_pass_calls_poll_if_due_every_time_and_never_poll_once() -> None:
    """Cadence is the observer's, from ``fill_observer.yaml``'s ``poll_interval_ms`` — the loop"""
    observer = MagicMock()
    one_pass = fill_observer_pass(_fake_runtime(observer))

    one_pass()
    one_pass()

    assert observer.poll_if_due.call_count == 2
    observer.poll_once.assert_not_called()


def test_the_pass_reads_the_observer_per_call_not_at_build_time() -> None:
    """Compose attaches the observer before it builds the scheduler, so capturing the value here"""
    runtime = SimpleNamespace(fill_observer=None)
    one_pass = fill_observer_pass(cast(ComposedRuntime, runtime))

    one_pass()
    observer = MagicMock()
    runtime.fill_observer = observer
    one_pass()

    observer.poll_if_due.assert_called_once_with()


def test_a_raising_observer_propagates_out_of_the_pass() -> None:
    """The pass adds no ``except`` of its own: a failure of the durable post-trade bookkeeping"""
    observer = MagicMock()
    observer.poll_if_due.side_effect = RuntimeError("evidence store is unwritable")

    with pytest.raises(RuntimeError, match="unwritable"):
        fill_observer_pass(_fake_runtime(observer))()


def test_the_session_loop_observes_the_fill_and_releases_once(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """M2's acceptance, through the loop that actually runs in a session: the order ACKs, the"""
    as_of_ms = _wire_tick_source(config_dir, tmp_path)
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    attempt_id = _ack(runtime)["attempt_id"]
    assert runtime.marketfeed is not None, "the tick source must be wired for this e2e"
    assert runtime.fill_observer is not None, "a stock MOCK boot has an observer"

    orders_path = _script_broker(
        server,
        config_dir,
        date,
        [_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )

    runtime.marketfeed.run_forever(
        sleep=_real_short_sleep, stop=_stop_when(lambda: _rcl_releases(runtime) >= 1)
    )

    assert runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == as_of_ms
    assert len(server.requests_for(_ORDER_PATH)) == 1

    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK", "FULL_FILL"]
    (observed,) = _rows(runtime, "FILL_OBSERVED")
    assert (observed["attempt_id"], observed["broker_execution_id"]) == (
        attempt_id,
        _ODNO,
    )
    (proof,) = _rows(runtime, "POSTTRADE_FINALITY_PROOF")
    assert proof["idempotency_key"] == f"broker-fqp-proof:{attempt_id}"
    assert "SYNTHETIC" not in json.dumps(proof)
    (intent,) = _rows(runtime, "CAPACITY_RELEASE_INTENT")
    assert intent["destination"] == "POSITION_CONSUMED"
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    assert _rcl_state(runtime) is CapacityState.POSITION_CONSUMED
    assert _rcl_releases(runtime) == 1
    assert len(server.requests_for(orders_path)) >= 1
    _close(runtime)


def test_the_session_loop_keeps_observing_while_the_broker_shows_nothing_yet(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """The ordinary shape of a session: the ACK is in, the broker has no execution row yet, and"""
    _wire_tick_source(config_dir, tmp_path)
    _deploy(config_dir, custody_root, server, monkeypatch)
    _retune_observer_poll_interval(config_dir, 1)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    date = _ack(runtime)["trading_date"]
    assert date is not None and _sealed_quantity(runtime) >= 1
    assert runtime.marketfeed is not None
    orders_path = _script_broker(server, config_dir, date, [])

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(4))

    assert len(server.requests_for(orders_path)) >= 2
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK"]
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    assert _rcl_releases(runtime) == 0
    assert _rcl_state(runtime) is not CapacityState.POSITION_CONSUMED
    _close(runtime)


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_the_paper_and_futures_loop_has_no_observer_and_polls_nothing(
    direction: str,
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
) -> None:
    """A synthetic-transport boot — the paper and CP-3 LONG/SHORT shape — gets no observer"""
    as_of_ms = _wire_tick_source(config_dir, tmp_path, direction=direction)
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.fill_observer is None
    assert runtime.marketfeed is not None

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(3))

    assert runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == as_of_ms
    assert [kind for kind in _evidence_kinds(runtime) if kind.startswith("FILL")] == []
    assert _rows(runtime, "POSTTRADE_FINALITY_PROOF") == []
    _close(runtime)


def test_the_observer_get_is_bounded_by_its_own_timeout_not_the_order_paths(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#949 review HIGH (a). The witness the hook reads through is sealed with"""
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    observer = runtime.fill_observer
    assert observer is not None
    expected = load_fill_observer_config(
        config_dir / FILL_OBSERVER_CONFIG_NAME
    ).witness_request_timeout_s
    witness = observer.orders
    assert isinstance(witness, DeferredKisWitness) and witness.inner is not None
    sealed = witness.inner._config.request_timeout_s  # noqa: SLF001
    assert sealed == expected
    assert (
        sealed
        != yaml.safe_load(
            (config_dir / "kis_mock_transport.yaml").read_text(encoding="utf-8")
        )["request_timeout_s"]
    )
    _close(runtime)


def test_a_pass_that_outruns_the_reserved_window_leaves_one_overrun_row(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#949 review HIGH (b), end to end through a real composed loop: a post-pass hook that takes"""
    _wire_tick_source(config_dir, tmp_path)
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    date = _ack(runtime)["trading_date"]
    assert date is not None and runtime.marketfeed is not None
    _install_slow_hook(runtime, _SlowHook(0.3))

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(2))

    overruns = _rows(runtime, "MARKETFEED_PASS_OVERRUN")
    assert len(overruns) >= 1
    row = overruns[0]
    assert row["budget_ms"] == _FAST_POLL_INTERVAL_MS + _JOURNAL_PASS_ALLOWANCE_MS
    assert row["pass_allowance_ms"] == _JOURNAL_PASS_ALLOWANCE_MS
    assert row["pass_ms"] > row["budget_ms"]
    assert row["after_pass_ms"] >= 300
    assert row["instrument"] == fx.INSTRUMENT
    _close(runtime)


def test_a_pass_inside_the_reserved_window_leaves_no_overrun_row(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The row must not appear on a healthy session's every pass: a synthetic boot with no"""
    _wire_tick_source(config_dir, tmp_path, allowance_ms=30_000)
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(3))

    assert _rows(runtime, "MARKETFEED_PASS_OVERRUN") == []
    _close(runtime)


def _append_prior_day_ack(
    runtime: ComposedRuntime, *, attempt_id: str, odno: str, date: str
) -> None:
    """A SECOND tracked ACK, under an earlier trading date, written straight to the evidence"""
    runtime.evidence_store.append(
        {
            "attempt_id": attempt_id,
            "instrument_key": {"account": fx.ACCOUNT, "instrument": fx.INSTRUMENT},
            "egress_result_kind": "ACK",
            "broker_execution_id": odno,
            "trading_date": date,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )


class _ReaderThatTakesItsTime:
    """The observer's ``orders`` port, delegating to the real witness and then burning"""

    def __init__(self, inner: Any, sleep_s: float) -> None:
        self.inner = inner
        self.sleep_s = sleep_s
        self.dates: list[str | None] = []

    def order_rows(
        self, scope, *, inquiry_date=None, deadline_expired=None
    ):  # noqa: ANN001
        self.dates.append(inquiry_date)
        result = self.inner.order_rows(
            scope, inquiry_date=inquiry_date, deadline_expired=deadline_expired
        )
        time.sleep(self.sleep_s)
        return result


def test_the_poll_deadline_stops_the_next_read_and_attributes_nothing(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#949 review HIGH (2). Two dates are due; the first read eats the whole poll deadline, so"""
    _deploy(config_dir, custody_root, server, monkeypatch)
    _retune_observer_poll_interval(config_dir, 1, poll_deadline_ms=50)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    today = _ack(runtime)["trading_date"]
    assert today is not None
    qty = _sealed_quantity(runtime)
    observer = runtime.fill_observer
    assert observer is not None

    prior = "20260901"
    _append_prior_day_ack(
        runtime, attempt_id="attempt-prior-day", odno="0000009998", date=prior
    )
    _script_broker(server, config_dir, prior, [])
    orders_today = _script_broker(
        server,
        config_dir,
        today,
        [_row(date=today, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )
    reader = _ReaderThatTakesItsTime(observer.orders, sleep_s=0.2)
    observer.orders = reader

    report = observer.poll_once()

    assert reader.dates == [prior, today]
    assert server.requests_for(orders_today) == []
    assert report.read_failed is True
    assert report.emitted == ()
    (failure,) = _rows(runtime, "FILL_OBSERVER_READ_FAILED")
    assert failure["inquiry_date"] == today
    assert "deadline" in failure["reason"]
    assert _rows(runtime, "FILL_OBSERVED") == []
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == [
        "ACK",
        "ACK",
    ]
    assert _rcl_releases(runtime) == 0

    reader.sleep_s = 0.0
    report = observer.poll_once()
    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    assert len(server.requests_for(orders_today)) >= 1
    (observed,) = _rows(runtime, "FILL_OBSERVED")
    assert observed["broker_execution_id"] == _ODNO
    assert "FULL_FILL" in [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ]
    assert _rcl_releases(runtime) == 0
    _close(runtime)


def test_the_loop_period_does_not_grow_by_the_hooks_broker_read(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#949 review HIGH, the fix: 300 ms spent inside the hook must not push the next intake"""
    _wire_tick_source(config_dir, tmp_path, poll_interval_ms=500)
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    date = _ack(runtime)["trading_date"]
    assert date is not None and runtime.marketfeed is not None
    _install_slow_hook(runtime, _SlowHook(0.3, slow_passes=1))

    sleeps: list[float] = []

    def _recording_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        time.sleep(_REAL_SLEEP_SECONDS)

    runtime.marketfeed.run_forever(sleep=_recording_sleep, stop=_stop_after(3))

    assert len(sleeps) == 3
    assert max(sleeps) <= 0.5
    shortened = [seconds for seconds in sleeps if seconds <= 0.25]
    baseline = [seconds for seconds in sleeps if seconds >= 0.4]
    assert len(shortened) == 1, sleeps
    assert len(baseline) == 2, sleeps
    _close(runtime)


def test_a_slow_broker_read_stretches_no_pass(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """Issue #950 acceptance, through the real loop and the real composed observer: the broker"""
    _wire_tick_source(config_dir, tmp_path, allowance_ms=1_000)
    runtime, date, qty = _acked(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    assert runtime.marketfeed is not None and runtime.fill_observer is not None
    orders_path = _script_slow_order_inquiry(
        server,
        config_dir,
        date,
        delay_s=1.5,
        rows=[_row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
    )

    runtime.marketfeed.run_forever(
        sleep=_real_short_sleep,
        stop=_stop_when(lambda: _rcl_releases(runtime) >= 1, max_passes=600),
    )

    assert _rows(runtime, "MARKETFEED_PASS_OVERRUN") == []
    assert len(server.requests_for(orders_path)) >= 2
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK", "FULL_FILL"]
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    assert _rcl_releases(runtime) == 1
    _close(runtime)


_ORPHAN_ODNO = "0000099999"


def _retune_observer(config_dir: Path, **keys: int) -> None:
    """Rewrite named keys of the deployed ``fill_observer.yaml`` (every other key kept)."""
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw.update(keys)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _wait_until_fetched(observer: Any, limit_s: float = 10.0) -> None:
    """Wait for the observer's in-flight FETCH to finish WITHOUT applying it (no poll call)."""
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        runner = observer._runner  # noqa: SLF001 - the test holds APPLY back on purpose
        if runner is not None and not runner.busy:
            return
        time.sleep(0.01)
    raise AssertionError("the FETCH never finished")


def _boot_filled(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch, **keys
):
    _deploy(config_dir, custody_root, server, monkeypatch)
    _retune_observer(config_dir, **keys)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    date = _ack(runtime)["trading_date"]
    assert date is not None
    qty = _sealed_quantity(runtime)
    filled_a = _row(date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))
    _script_broker(server, config_dir, date, [filled_a])
    assert runtime.fill_observer is not None
    return runtime, date, filled_a


def test_an_expired_release_snapshot_holds_instead_of_releasing(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#969 review r1 HIGH (Codex's failing input): FETCH reads order A fully filled, APPLY is"""
    runtime, date, filled_a = _boot_filled(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        poll_interval_ms=1,
        release_snapshot_max_age_ms=300,
    )
    observer = runtime.fill_observer
    assert observer is not None

    assert observer.poll_if_due().polled is False
    _wait_until_fetched(observer)
    time.sleep(0.5)
    orphan_b = _row(
        odno=_ORPHAN_ODNO,
        date=date,
        ord_qty=Decimal(1),
        filled=Decimal(1),
        remaining=Decimal(0),
    )
    _script_broker(server, config_dir, date, [filled_a, orphan_b])

    report = observer.poll_if_due()

    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    assert _rcl_releases(runtime) == 0
    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert "expired" in (held.get("detail") or "")
    (expired,) = _rows(runtime, "FILL_OBSERVER_RELEASE_SNAPSHOT")
    assert expired["verdict"] == "expired"
    assert expired["age_ms"] > expired["max_age_ms"] == 300
    assert expired["read_started_monotonic_ms"] <= expired["read_finished_monotonic_ms"]

    observer.poll_if_due()
    _wait_until_fetched(observer)
    report = observer.poll_if_due()
    assert [attempt for attempt, _r in report.reprojected] == [
        _ack(runtime)["attempt_id"]
    ]
    assert _rcl_releases(runtime) == 0
    verdicts = [r["verdict"] for r in _rows(runtime, "FILL_OBSERVER_RELEASE_SNAPSHOT")]
    assert verdicts == ["expired", "served"]
    _close(runtime)


def test_a_fresh_release_snapshot_still_releases(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """The other side of the age limit: a snapshot applied inside it releases, and its row"""
    runtime, _date, _a = _boot_filled(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        poll_interval_ms=1,
        release_snapshot_max_age_ms=5_000,
    )
    observer = runtime.fill_observer
    assert observer is not None

    observer.poll_if_due()
    _wait_until_fetched(observer)
    report = observer.poll_if_due()

    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    assert _rcl_releases(runtime) == 1
    (served,) = _rows(runtime, "FILL_OBSERVER_RELEASE_SNAPSHOT")
    assert served["verdict"] == "served"
    assert 0 <= served["age_ms"] <= served["max_age_ms"] == 5_000
    _close(runtime)


def test_an_order_that_appears_right_after_the_balance_read_holds_the_release(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """review-979 r1 HIGH (iii): the snapshot reads the balance and then today's orders, LAST,"""
    runtime, date, filled_a = _boot_filled(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        poll_interval_ms=1,
        release_snapshot_max_age_ms=5_000,
    )
    observer = runtime.fill_observer
    assert observer is not None
    balance, orders = _witness_paths(config_dir, date)
    orphan_b = _row(
        odno=_ORPHAN_ODNO,
        date=date,
        ord_qty=Decimal(1),
        filled=Decimal(1),
        remaining=Decimal(0),
    )

    def _b_appears() -> None:
        server.set_response(
            orders,
            status=200,
            body={"rt_cd": "0", "output1": [filled_a, orphan_b], "output2": {}},
        )

    server.set_response(
        balance,
        status=200,
        body={"rt_cd": "0", "output1": [], "output2": [{"dnca_tot_amt": "1000000"}]},
        on_request=_b_appears,
    )

    observer.poll_if_due()
    _wait_until_fetched(observer)
    report = observer.poll_if_due()

    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    assert _rcl_releases(runtime) == 0
    assert _rows(runtime, "CAPACITY_RELEASE_HELD")
    (served,) = _rows(runtime, "FILL_OBSERVER_RELEASE_SNAPSHOT")
    assert served["verdict"] == "served"
    _close(runtime)
