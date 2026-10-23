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
* §3 the paper / CP-3 LONG and SHORT loop is unchanged: no observer, so the pass polls nothing.

The e2e's journaled observation is deliberately NON-crossing (``close`` between the bands, so the
band-reversion strategy proposes nothing): the loop's real passes must not send a second order,
which is what makes "one order POST in the whole run" a meaningful assertion about the fill path.

Hermetic: the fake server binds ``127.0.0.1``, every file lives under ``tmp_path``, and the only
production patch is PR-3a's INSTANCE ``rest_base`` -> fake server (``_sealed_mock_deployment``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import yaml
from tos.rcl import CapacityState
from tos_runtime.compose._broker_posttrade_wiring import fill_observer_pass
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.posttrade.fill_observer import FILL_OBSERVER_CONFIG_NAME

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
    config_dir: Path, *, journal_path: Path, direction: str = "LONG"
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
                "poll_interval_ms": _FAST_POLL_INTERVAL_MS,
                "journal_pass_allowance_ms": 100,
                "time_evaluate_closed_interval_ms": 60_000,
                "snapshot_age_bound": 20,
                "interval_width": 10,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _wire_tick_source(
    config_dir: Path, tmp_path: Path, *, direction: str = "LONG"
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
    _write_marketfeed_config(config_dir, journal_path=journal_path, direction=direction)
    return as_of_ms


def _retune_observer_poll_interval(config_dir: Path, poll_interval_ms: int) -> None:
    """Rewrite the deployed ``fill_observer.yaml``'s ``poll_interval_ms`` (every other key kept).

    The shipped tenant value is 3000 ms — one 모의 call per rate-limit budget — so a hermetic
    loop of a few 30 ms passes sees exactly one broker read, which cannot tell "the loop keeps
    asking" from "something asked once at boot". Lowering the CONFIGURED cadence is how a test
    gets several real reads: the number still comes from the file ``poll_if_due`` reads, not from
    a second interval invented in the caller.
    """
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["poll_interval_ms"] = poll_interval_ms
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


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

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after(2))

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
