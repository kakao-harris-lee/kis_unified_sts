"""Who calls the fill observer: the session loop, once per pass (PR-3b follow-up, rescope plan
``docs/plans/2026-10-22-tos-rescope-plan.md`` §3 M2).

PR-3b built :class:`~tos_runtime.posttrade.fill_observer.KisMockFillObserver` and attached it to a
stock MOCK boot, and **nothing called it**: every test drove ``poll_once()``/``poll_if_due()`` by
hand, so in a real session an ACKed order's fill was never observed and its capacity never
released. This file covers the caller:

* §1 :func:`~tos_runtime.compose._broker_posttrade_wiring.fill_observer_pass` — what the loop
  runs: ``poll_if_due()`` when this boot has an observer, nothing when it does not, read per call;
* §2 the e2e: a real :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.run_forever` session
  loop over a stock MOCK boot against the fake KIS server observes ACK -> FULL_FILL -> broker
  finality proof -> exactly one RCL release, with **no** ``poll_*`` call anywhere in the test;
* §3 the paper / CP-3 LONG and SHORT loop is unchanged: no observer, so the pass polls nothing;
* §4 the #949 review's HIGH, the half of it this lane could close: the hook runs inside the
  loop's tick-to-tick freshness window, so its GETs carry the observer's OWN timeout (not the
  order path's 10 s) and every pass that outruns ``journal_pass_allowance_ms`` leaves one
  ``MARKETFEED_PASS_OVERRUN`` row — a ``STALE`` field caused by this hook is no longer
  indistinguishable from a late producer. The residual (a GET that runs to its timeout still
  stretches that pass) is in the scheduler's own module docstring and in #949's PR body.

The e2e's journaled observation is deliberately NON-crossing (``close`` between the bands, so the
band-reversion strategy proposes nothing): the loop's real passes must not send a second order,
which is what makes "one order POST in the whole run" a meaningful assertion about the fill path.

Hermetic: the fake server binds ``127.0.0.1``, every file lives under ``tmp_path``, and the only
production patch is PR-3a's INSTANCE ``rest_base`` -> fake server (``_sealed_mock_deployment``).
"""

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

#: Between ``fx.LOWER_BAND`` and ``fx.UPPER_BAND`` — the band-reversion strategy proposes only on
#: ``close < lower_band``, so every loop pass here is a real tick that orders nothing.
_NON_CROSSING_CLOSE = (fx.LOWER_BAND + fx.UPPER_BAND) // 2
#: Short on purpose (``test_run_e2e.py``'s own reasoning): the pacing gate compares REAL
#: wall-clock readings, so a hermetic loop that wants several real passes needs a real — but
#: small — sleep between them.
_FAST_POLL_INTERVAL_MS = 20
_REAL_SLEEP_SECONDS = 0.03
#: The runtime's own share of the freshness budget, as this suite's marketfeed config declares
#: it — the number ``TickScheduler`` measures each pass against (§4).
_JOURNAL_PASS_ALLOWANCE_MS = 100


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
    """``test_run_e2e.py``'s fast marketfeed config, with ``direction`` open to a caller (§3
    drives LONG and SHORT) — the journal intake, this suite's one instrument, a 20 ms interval.
    """
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
    """Put a journal-backed tick source under ``config_dir`` and return its observation's
    ``as_of_ms`` (the value the durable store must hold once the loop has really ticked).
    """
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
    """Rewrite the deployed ``fill_observer.yaml``'s cadence keys (every other key kept).

    The shipped tenant value is 3000 ms — one 모의 call per rate-limit budget — so a hermetic
    loop of a few 30 ms passes sees exactly one broker read, which cannot tell "the loop keeps
    asking" from "something asked once at boot". Lowering the CONFIGURED cadence is how a test
    gets several real reads: the number still comes from the file ``poll_if_due`` reads, not from
    a second interval invented in the caller.
    """
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
    """``_script_broker`` with a REAL delay on the order inquiry — the fake server's own
    ``delay_s`` route option, so the slowness is a genuine wall-clock wait on the GET the hook
    makes, not a patched clock."""
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
    """Admit passes until ``done()`` or ``max_passes``. Issue #950: the observer's broker read
    finishes on its own worker, so "the fill landed" is a number of passes the loop cannot know
    in advance — the test waits for the durable fact, bounded, instead of guessing a count.
    """
    passes = {"count": 0}

    def stop() -> bool:
        if passes["count"] >= max_passes or done():
            return True
        passes["count"] += 1
        return False

    return stop


class _SlowHook:
    """Stands in for ``runtime.fill_observer`` with a hook that takes ``seconds`` on the loop
    thread. Issue #950 moved the observer's own broker reads off the loop, so a slow broker no
    longer produces a slow pass; the scheduler's overrun row and sleep compensation (#949) still
    guard any hook that is slow, and these stand-ins are how their tests still get one.
    """

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
    """A stand-in for the one attribute :func:`fill_observer_pass` reads. Typed through
    :func:`typing.cast` rather than composed: §2/§3 below drive the real thing end to end, and
    these three cases are about the pass's own branch, not about composition."""
    return cast(ComposedRuntime, SimpleNamespace(fill_observer=observer))


def _evidence_kinds(runtime: ComposedRuntime) -> list[str]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT DISTINCT kind FROM entries"
    ).fetchall()
    return [row[0] for row in rows]


# ===========================================================================
# 1. the pass itself
# ===========================================================================


def test_the_pass_polls_nothing_when_this_boot_has_no_observer() -> None:
    """Every boot that is not a stock MOCK order tree, and a stock MOCK boot whose recovery
    barrier held: ``fill_observer`` is ``None`` and the pass is a no-op, never an
    ``AttributeError`` that would take the session loop down."""
    fill_observer_pass(_fake_runtime(None))()


def test_the_pass_calls_poll_if_due_every_time_and_never_poll_once() -> None:
    """Cadence is the observer's, from ``fill_observer.yaml``'s ``poll_interval_ms`` — the loop
    asks every pass and ``poll_if_due`` decides. Mutation: call ``poll_once()`` instead (a second
    cadence, in the caller) -> red on both assertions."""
    observer = MagicMock()
    one_pass = fill_observer_pass(_fake_runtime(observer))

    one_pass()
    one_pass()

    assert observer.poll_if_due.call_count == 2
    observer.poll_once.assert_not_called()


def test_the_pass_reads_the_observer_per_call_not_at_build_time() -> None:
    """Compose attaches the observer before it builds the scheduler, so capturing the value here
    would freeze that wiring order into this hook. Mutation: bind the observer when the pass is
    built -> the second call polls nothing -> red."""
    runtime = SimpleNamespace(fill_observer=None)
    one_pass = fill_observer_pass(cast(ComposedRuntime, runtime))

    one_pass()  # nothing attached yet
    observer = MagicMock()
    runtime.fill_observer = observer
    one_pass()

    observer.poll_if_due.assert_called_once_with()


def test_a_raising_observer_propagates_out_of_the_pass() -> None:
    """The pass adds no ``except`` of its own: a failure of the durable post-trade bookkeeping
    reaches ``run_forever`` and stops the loop (``scheduler.py``'s own post-pass-hook
    paragraph)."""
    observer = MagicMock()
    observer.poll_if_due.side_effect = RuntimeError("evidence store is unwritable")

    with pytest.raises(RuntimeError, match="unwritable"):
        fill_observer_pass(_fake_runtime(observer))()


# ===========================================================================
# 2. the e2e — the session loop observes the fill, with no manual poll
# ===========================================================================


def test_the_session_loop_observes_the_fill_and_releases_once(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """M2's acceptance, through the loop that actually runs in a session: the order ACKs, the
    broker shows it fully filled, and ``run_forever`` — not the test — observes it, proves it
    from the broker, and releases the reservation exactly once.

    Mutation (the red-before): remove the ``after_pass`` call from
    :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.run_forever` -> no ``FULL_FILL``, no
    proof, no release -> red. ⚠ This test calls no ``poll_once``/``poll_if_due`` itself, and must
    not grow one: that is the whole claim.
    """
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

    # The loop really ticked (the durable store advanced), and ordered nothing more.
    assert runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == as_of_ms
    assert len(server.requests_for(_ORDER_PATH)) == 1

    # The fill was observed, proven from the broker, and released once.
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
    """The ordinary shape of a session: the ACK is in, the broker has no execution row yet, and
    the loop keeps reading pass after pass without releasing anything. Pins that the caller is
    the LOOP (several reads across several passes), not a one-shot at boot.

    Boots by hand rather than through ``_acked`` for one reason: the observer's cadence has to be
    retuned between the deployment and the boot (see
    :func:`_retune_observer_poll_interval`). ``>= 2`` rather than ``== passes``: ``poll_if_due``
    owns the cadence, so the pass count is an upper bound on reads, never the claim.
    """
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


# ===========================================================================
# 3. paper / CP-3 LONG and SHORT — no observer, so the pass polls nothing
# ===========================================================================


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_the_paper_and_futures_loop_has_no_observer_and_polls_nothing(
    direction: str,
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
) -> None:
    """A synthetic-transport boot — the paper and CP-3 LONG/SHORT shape — gets no observer
    (``test_broker_posttrade_wiring.py`` pins that from the committed trees). This pins what the
    LOOP then does: real passes, and not one post-trade row.

    Mutation: make the pass poll unconditionally (drop the ``None`` guard) -> ``AttributeError``
    out of ``run_forever`` -> red.
    """
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


# ===========================================================================
# 4. the hook sits in the freshness window: its own timeout, and a measured pass
# ===========================================================================


def test_the_observer_get_is_bounded_by_its_own_timeout_not_the_order_paths(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch,
    server,
) -> None:
    """#949 review HIGH (a). The witness the hook reads through is sealed with
    ``fill_observer.yaml::witness_request_timeout_s``, deliberately not the order transport's
    ``request_timeout_s`` — the observer's read happens inside the loop's tick-to-tick window
    and the order POST does not.

    Mutation: wire ``transport_config.request_timeout_s`` back in -> the sealed value becomes
    the fixture's 5.0 -> red on both assertions.
    """
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
    # The fixture's transport says 5.0 (``_fixtures.write_kis_mock_transport_config``): the
    # point of the change is that these two numbers are no longer the same one.
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
    """#949 review HIGH (b), end to end through a real composed loop: a post-pass hook that takes
    longer than the whole reserved window (``poll_interval_ms`` 20 + ``journal_pass_allowance_ms``
    100) overruns its pass, and the durable store says so — with the hook's share split out from
    the tick's. Issue #950: the fill observer's broker read no longer runs in the hook (see
    :func:`test_a_slow_broker_read_stretches_no_pass`), so the slow hook here is a stand-in
    (:class:`_SlowHook`); what this pins is the scheduler's measurement, which still guards
    every hook.

    Without this row the only trace of a slow hook is a ``STALE`` field, which looks exactly
    like a late producer (``scheduler.py``'s own post-pass-hook paragraph).

    Mutation: drop the ``pass_budget`` wiring in ``build_tick_scheduler`` -> no row -> red.
    """
    _wire_tick_source(config_dir, tmp_path)
    _deploy(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    date = _ack(runtime)["trading_date"]
    assert date is not None and runtime.marketfeed is not None
    # A hook slower than the allowance this suite's marketfeed config declares.
    _install_slow_hook(runtime, _SlowHook(0.3))

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(2))

    overruns = _rows(runtime, "MARKETFEED_PASS_OVERRUN")
    assert len(overruns) >= 1
    row = overruns[0]
    # The threshold is the whole reserved window, interval + allowance (#949 r2 MEDIUM-3).
    assert row["budget_ms"] == _FAST_POLL_INTERVAL_MS + _JOURNAL_PASS_ALLOWANCE_MS
    assert row["pass_allowance_ms"] == _JOURNAL_PASS_ALLOWANCE_MS
    assert row["pass_ms"] > row["budget_ms"]
    # The hook's share, not the tick's, is what blew the budget — that is the whole point of
    # recording both halves.
    assert row["after_pass_ms"] >= 300
    assert row["instrument"] == fx.INSTRUMENT
    _close(runtime)


def test_a_pass_inside_the_reserved_window_leaves_no_overrun_row(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The row must not appear on a healthy session's every pass: a synthetic boot with no
    observer ticks well inside the allowance and writes nothing.

    Mutation: record unconditionally -> a row per pass -> red.

    The allowance here is deliberately enormous (30 s, still inside the conftest freshness
    budget this config is checked against): a real composed pass issues a snapshot, resolves
    through the kernel and drives the engine, so pinning "no row" against the production-shaped
    100 ms would be a bet on how loaded the host is. The arithmetic of the boundary itself is
    pinned deterministically in ``tests/marketfeed/test_scheduler.py``.
    """
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
    """A SECOND tracked ACK, under an earlier trading date, written straight to the evidence
    store.

    The observer's read phase only has more than one date when the runtime was down across a
    KST date boundary (``_due``'s own prior-day branch), which a hermetic test cannot reach any
    other way — nothing here can move the trusted trading date backwards. The payload is the
    shape ``_tracked_attempts`` reads: instrument key, attempt id, kind, ODNO, date.
    """
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
    """The observer's ``orders`` port, delegating to the real witness and then burning
    ``sleep_s`` of real time — "this read took that long in total", which is what a deadline is
    about. The sleep is AFTER the delegation on purpose: the first read must succeed and be
    slow, so the deadline falls between the two reads rather than before the first.
    """

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
    """#949 review HIGH (2). Two dates are due; the first read eats the whole poll deadline, so
    the second never starts: it is ``WitnessUnavailable`` — recorded once, nothing attributed —
    even though the broker's rows for it would have been a FULL_FILL. Then the next due poll
    reads both and the fill lands.

    This is the property that makes the deadline safe to have: it can only ever produce an
    absence. A deadline that returned "these are all the rows I got" would release capacity
    against a partial list.

    Mutations: have ``_read`` swallow the deadline instead of recording it -> no READ_FAILED row
    -> red; let the cut read return its partial rows -> the FULL_FILL lands in the first poll
    -> red on the no-attribution assertions.
    """
    _deploy(config_dir, custody_root, server, monkeypatch)
    # A deadline short enough that one slow read exhausts it.
    _retune_observer_poll_interval(config_dir, 1, poll_deadline_ms=50)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    assert _drive_crossing_tick(runtime, custody_root).flow is not None
    today = _ack(runtime)["trading_date"]
    assert today is not None
    qty = _sealed_quantity(runtime)
    observer = runtime.fill_observer
    assert observer is not None

    # An unresolved ACK from an earlier day — read FIRST (`sorted(dates)`), and it is the one
    # that gets to spend the deadline.
    # Strictly before this suite's fixed wall clock (``fx.DEFAULT_WALL_CLOCK_UNIX_MS``
    # is 2026-09-14), so it really is a prior trading day and sorts first.
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

    # Both dates were attempted; only the first reached the broker.
    assert reader.dates == [prior, today]
    assert server.requests_for(orders_today) == []
    assert report.read_failed is True
    assert report.emitted == ()
    (failure,) = _rows(runtime, "FILL_OBSERVER_READ_FAILED")
    assert failure["inquiry_date"] == today
    assert "deadline" in failure["reason"]
    # Nothing was attributed from the read that did not happen.
    assert _rows(runtime, "FILL_OBSERVED") == []
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == [
        "ACK",
        "ACK",
    ]  # ours, plus the prior-day row this test appended
    assert _rcl_releases(runtime) == 0

    # The next due poll (no longer slow) reads both dates and the fill lands.
    reader.sleep_s = 0.0
    report = observer.poll_once()
    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    # At least the fill read itself; the release path's reconciliation reads this TR too.
    assert len(server.requests_for(orders_today)) >= 1
    (observed,) = _rows(runtime, "FILL_OBSERVED")
    assert observed["broker_execution_id"] == _ODNO
    assert "FULL_FILL" in [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ]
    # Capacity is NOT released here, on purpose: this test planted a second ACK the broker has
    # no row for, which reconciliation sees as an orphan on the same scope — #939's own
    # unattributed-ODNO test pins that conservative hold. What this test is about is that the
    # fill was attributed only once the read actually happened.
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
    """#949 review HIGH, the fix: 300 ms spent inside the hook must not push the next intake
    read 300 ms later — that is what ages a bar into ``STALE``. The loop sleeps the interval
    MINUS the pass, so the PERIOD stays the configured 500 ms: the slow pass asks for a visibly
    shorter sleep, and no pass ever asks for more than the interval.

    A deliberately visible interval (500 ms, not this file's 20 ms default) so the compensated
    sleep and the uncompensated one cannot be confused. Issue #950: the observer's broker read
    left the hook, so the slow hook is a stand-in that is slow on its first pass only.

    Mutation: sleep the plain interval -> every entry is 0.5 and the ``shortened`` list is empty
    -> red (and the real loop would then run a 800 ms period against a 500 ms config).
    """
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
        # Sleep a token amount, not the compensated interval: this test is about the number
        # the loop ASKS for (its period), not about spending three real half-seconds.
        time.sleep(_REAL_SLEEP_SECONDS)

    runtime.marketfeed.run_forever(sleep=_recording_sleep, stop=_stop_after(3))

    assert len(sleeps) == 3
    # Never longer than the configured interval — compensation only ever subtracts.
    assert max(sleeps) <= 0.5
    # The polling pass paid ~300 ms of broker read out of its own sleep.
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
    """Issue #950 acceptance, through the real loop and the real composed observer: the broker
    holds every order inquiry for 1.5 s — the fill read AND the release reconciliation's read —
    and yet no pass outruns its window (no ``MARKETFEED_PASS_OVERRUN`` row against a 1 s
    allowance), while the fill is still observed, proven and released exactly once.

    The reconciliation's read is the #949 r2 MEDIUM-1 term: if the prefetch missed and the
    release path read the broker on the loop thread, that pass would take >= 1.5 s and leave a
    row. Mutation: run the FETCH inline in ``poll_if_due`` (or drop ``snapshots=`` in compose)
    -> overrun rows -> red.
    """
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
    # Both slow reads happened — the fill read and the reconciliation's — just not on the loop.
    assert len(server.requests_for(orders_path)) >= 2
    assert [
        r["egress_result_kind"] for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
    ] == ["ACK", "FULL_FILL"]
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    assert _rcl_releases(runtime) == 1
    _close(runtime)


# ===========================================================================
# 5. #969 review round 1 HIGH (Codex) — a prefetched release snapshot has an age limit
# ===========================================================================

#: The order B the broker shows after the FETCH read: same account, same instrument, attributed
#: to no ACK this runtime holds — the reconciliation's ORPHAN_BROKER_ORDER case.
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
    """#969 review r1 HIGH (Codex's failing input): FETCH reads order A fully filled, APPLY is
    delayed, and meanwhile an unattributed order B appears at the broker. The stale snapshot
    (no B) would permit the release; the current broker (B = ORPHAN_BROKER_ORDER) would not.
    Past ``release_snapshot_max_age_ms`` the snapshot is not served: the release HOLDS (no live
    read on the loop), the hold and a snapshot row say why and how old, and a fresh worker read
    is scheduled at once — which sees B and keeps holding.

    Mutation: serve the snapshot regardless of age -> the release commits against the stale
    picture -> red on ``_rcl_releases == 0``.
    """
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

    assert observer.poll_if_due().polled is False  # plan + submit
    _wait_until_fetched(observer)
    time.sleep(0.5)  # APPLY held back past the snapshot's age limit
    orphan_b = _row(
        odno=_ORPHAN_ODNO,
        date=date,
        ord_qty=Decimal(1),
        filled=Decimal(1),
        remaining=Decimal(0),
    )
    _script_broker(server, config_dir, date, [filled_a, orphan_b])

    report = observer.poll_if_due()  # APPLY of the old FETCH

    assert [k for _a, k, _d in report.emitted] == [EgressResultKind.FULL_FILL]
    assert _rcl_releases(runtime) == 0
    (held,) = _rows(runtime, "CAPACITY_RELEASE_HELD")
    assert "expired" in (held.get("detail") or "")
    (expired,) = _rows(runtime, "FILL_OBSERVER_RELEASE_SNAPSHOT")
    assert expired["verdict"] == "expired"
    assert expired["age_ms"] > expired["max_age_ms"] == 300
    assert expired["read_started_monotonic_ms"] <= expired["read_finished_monotonic_ms"]

    # The FIRST expiry of a run is re-read now, not after finality_retry_interval_ms (60 s;
    # later expiries in a run wait it out, issue #971): the next due poll plans a finality
    # re-run with a fresh worker snapshot — which sees B and holds.
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
    """The other side of the age limit: a snapshot applied inside it releases, and its row
    records the real read instants and an age within the limit."""
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
