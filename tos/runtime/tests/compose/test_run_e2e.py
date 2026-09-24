"""Compose-relative e2e tests for ``run`` (TOS ``run`` 구동 아크 plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W1 lane C).

**(1) The first compose-relative e2e of ``run_forever``.** Existing coverage of
:meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.run_forever` is either fully faked
(``tests/marketfeed/test_scheduler.py:262`` — a stand-in scheduler/driver, no real compose) or a
single ``tick_once()`` call against a real composed runtime
(``tests/compose/test_marketfeed_wiring.py``, e.g.
``test_tick_once_ticks_with_the_real_resolver_and_the_admitted_price_travels_with_its_digest``).
Nothing before this file drives the ACTUAL ``while not stop(): tick_once(); sleep(...)`` loop
against a real :class:`~tos_runtime.compose._types.ComposedRuntime`.

**(1b) the ``cli.main(["run", ...])`` argv path itself, ticking for real** (reviewer HIGH, PR
#725: the tests above call ``run_forever`` directly on a ``_compose()``d runtime, never through
``dispatch_run``/``main`` — the ONLY test that reaches ``dispatch_run``'s success path used to
monkeypatch ``compose_paper_runtime`` with a fake scheduler, so reverting ``main``'s dispatch to
the pre-wave ``return 0`` killed just one test). ``test_cli_main_run_argv_path_composes_and_
actually_ticks`` enters at the real argv path against a real composed runtime and a real tick
source on disk, bounded by a real ``SIGINT`` from a background thread (the only bound
``dispatch_run`` itself supports), and confirms a durable tick landed by reopening the on-disk
snapshot store file after ``main()`` returns.

**(2) ``_dispatch_run``'s own refusal paths, against real files on disk** (module docstring of
:mod:`tos_runtime.compose.cli` — the module-level unit tests in ``test_cli.py`` monkeypatch
``compose_paper_runtime``/``load_construction_config``; this file exercises the real functions):
a missing ``construction.yaml``, a still-``"TBD"`` leaf in it, and no wired tick source
(``marketfeed.yaml``/``critical_input_policy.yaml`` absent from an otherwise-composable
``--config-dir``).

Hermetic (D1.4): every file lives under ``tmp_path``; no network, no ambient env — the SAME
autouse guards ``test_marketfeed_wiring.py`` uses.
"""

from __future__ import annotations

import os
import signal
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from tos_runtime.compose import cli
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME

from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_marketfeed_wiring import (
    _observation_line,
    _write_critical_input_policy,
    _write_journal,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Small on purpose (unlike test_marketfeed_wiring.py's 1000ms production-shaped default) — the
#: pacing gate (``decide_tick``'s own ``SKIPPED_INTERVAL``) compares against the REAL wall clock
#: (``TrustworthyTimeService`` uses ``LocalSystemClockReader``, never the injected
#: ``wall_clock`` fixture — see that file's own comment), so a fast hermetic test that wants
#: MULTIPLE real ``TICKED`` passes needs a real, short, injected sleep between passes rather
#: than a multi-second one.
_FAST_POLL_INTERVAL_MS = 20
_REAL_SLEEP_SECONDS = 0.03


def _as_of_ms(offset_ms: int = 0) -> int:
    return int(time.time() * 1000) - 1000 + offset_ms


def _write_fast_marketfeed_config(
    config_dir: Path, *, journal_path: Path, instruments: tuple[str, ...]
) -> None:
    """The SAME shape ``test_marketfeed_wiring.py``'s own ``_write_marketfeed_config`` writes,
    with a configurable (small) ``poll_interval_ms`` — that helper hardcodes 1000ms, too slow
    for this file's multi-tick loop test to drive with a real (not multi-second) sleep.
    """
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(
            {
                "instruments": list(instruments),
                "instrument_class": fx.INSTRUMENT_CLASS,
                "account": fx.ACCOUNT,
                "direction": "LONG",
                "quantity_basis": "RISK",
                "unit": "contract",
                # W2 lane (2026-09-17) — intake_kind is now required and never defaults
                # (_marketfeed_wiring.py module docstring); this suite exercises the
                # journal-backed intake exclusively, so it is pinned explicitly here.
                "intake_kind": "journal",
                "journal_path": str(journal_path),
                "poll_interval_ms": _FAST_POLL_INTERVAL_MS,
                "snapshot_age_bound": 20,
                "interval_width": 10,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _valid_construction_yaml() -> dict:
    """The SAME facts ``_fixtures.construction_config()`` injects, shaped for
    ``construction.yaml`` (``tos_runtime.compose._construction_config`` loader)."""
    return {
        "account": fx.ACCOUNT,
        "instrument": fx.INSTRUMENT,
        "action_class": "NEW_LONG",
        "instrument_class": fx.INSTRUMENT_CLASS,
        "outbound_side": fx.SIDE,
        "price_field_key": "close",
        "shape_price_field_key": "close",
    }


def _write_construction_yaml(config_dir: Path, overrides: dict | None = None) -> None:
    content = _valid_construction_yaml()
    if overrides:
        content.update(overrides)
    (config_dir / "construction.yaml").write_text(
        yaml.safe_dump(content, sort_keys=False), encoding="utf-8"
    )


def _run_args(config_dir: Path, data_dir: Path, custody_root: Path) -> cli.Args:
    return cli.Args(
        config_dir=config_dir,
        data_dir=data_dir,
        custody_root=custody_root,
        environment_label="non-live-test",
        transport=TransportKind.SYNTHETIC,
    )


# ----------------------------------------------------------------------------
# (1) the first compose-relative e2e of `run_forever`
# ----------------------------------------------------------------------------


def test_run_forever_drives_a_real_tick_against_a_composed_runtime_and_stops(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    as_of_ms = _as_of_ms()
    _write_journal(
        journal_path,
        [_observation_line(raw_event_id="raw-run-forever", as_of_ms=as_of_ms)],
    )
    _write_critical_input_policy(config_dir)
    _write_fast_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    passes = 0

    def _stop_after_n() -> bool:
        nonlocal passes
        passes += 1
        return passes > 4

    def _real_short_sleep(_seconds: float) -> None:
        time.sleep(_REAL_SLEEP_SECONDS)

    # The one journaled observation TICKS on the first pass; every subsequent pass sees the
    # SAME (already-issued) observation and resolves SKIPPED_NOT_NEWER (decide_tick's own
    # per-observation distinctness check, module docstring) — proving the loop keeps running
    # (not that it stops after one pass) without depending on the real-wall-clock pacing gate
    # at all.
    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after_n)

    assert passes == 5
    assert runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == as_of_ms

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_run_forever_ticks_a_second_real_observation_after_the_pacing_interval(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Two DISTINCT observations, both real ``TICKED`` passes — proves the loop does not just
    tolerate repeated no-op passes (the test above) but actually advances the durable store
    twice across real ``run_forever`` iterations, spaced by a real (short) injected sleep that
    clears the pacing gate (``_FAST_POLL_INTERVAL_MS``)."""
    journal_path = tmp_path / "journal.jsonl"
    first_as_of = _as_of_ms()
    second_as_of = _as_of_ms(500)
    _write_journal(
        journal_path,
        [
            _observation_line(raw_event_id="raw-1", as_of_ms=first_as_of),
        ],
    )
    _write_critical_input_policy(config_dir)
    _write_fast_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    passes = 0

    def _stop_after_first_tick() -> bool:
        nonlocal passes
        passes += 1
        return passes > 2

    def _real_short_sleep(_seconds: float) -> None:
        time.sleep(_REAL_SLEEP_SECONDS)

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after_first_tick)
    assert (
        runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == first_as_of
    )

    # Append a second, strictly-newer observation to the SAME journal file (the real intake
    # re-reads it on every poll — JsonLinesObservationJournal has no in-memory cursor of its
    # own beyond `after_as_of_ms`), then resume the SAME loop.
    _write_journal(
        journal_path,
        [
            _observation_line(raw_event_id="raw-1", as_of_ms=first_as_of),
            _observation_line(raw_event_id="raw-2", as_of_ms=second_as_of),
        ],
    )
    passes = 0

    def _stop_after_second_tick() -> bool:
        nonlocal passes
        passes += 1
        return passes > 2

    # TrustworthyTimeService.wall_clock_now() (time/service.py:668-682) returns the LAST
    # evaluate() cycle's own frozen snapshot, never a live re-read of the system clock — so the
    # pacing gate's `now_ms` needs a fresh evaluate() cycle to see real elapsed time at all
    # (compose itself only runs two boot-time cycles, module docstring of `_reach_trusted`).
    # A real deployment's own health-refresh loop calls this periodically; this test does the
    # SAME real call, once, rather than depending on `run_forever` itself to do it (it does
    # not — refreshing trust is the time service's own job, out of this loop's scope).
    runtime.time_service.evaluate()
    runtime.marketfeed.run_forever(
        sleep=_real_short_sleep, stop=_stop_after_second_tick
    )
    assert (
        runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == second_as_of
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ----------------------------------------------------------------------------
# (1b) the `cli.main(["run", ...])` argv path itself — reviewer HIGH (PR #725):
# every other test in this file either calls `run_forever` directly on a `_compose()`d
# runtime (never through `dispatch_run`/`main` at all) or drives `dispatch_run` down a
# REFUSAL path that never reaches `run_forever`. Reverting `main`'s `return
# _dispatch_run(args)` back to the pre-wave `return 0` must turn THIS test red — that is
# the headline claim ("run composes and drives") and no other test in the suite pins it.
# ----------------------------------------------------------------------------


#: How long the sender thread waits for a real tick before giving up on OBSERVING one and
#: instead sending ``SIGINT`` unconditionally, purely to unstick a hung ``run_forever`` so this
#: test fails normally instead of hanging the suite (see ``_send_sigint_once_ticked_or_deadline``
#: and the "known flake class" paragraph in this test's own docstring for the full reasoning).
_TICK_WAIT_TIMEOUT_S = 10.0


def read_only_latest_as_of(
    db_path: Path,
    *,
    instrument: str,
    on_state: Callable[[str], None] | None = None,
) -> int | None:
    """The newest durable ``as_of_ms`` for ``instrument`` in the snapshot-store file at
    ``db_path`` — read WITHOUT ever writing durable content to it. ``None`` when the file, the
    table, or a matching row is not there (yet).

    **Why this may not simply construct a** :class:`~tos_runtime.marketfeed.store
    .SqliteSnapshotStore` **(the defect this helper exists to close; review-797, one observed CI
    failure on PR #797).** That constructor is a WRITER, not a reader: ``store.py:230-243``
    captures ``file_is_fresh(conn)``, runs its three ``CREATE TABLE``/``CREATE INDEX`` statements
    and then calls :func:`~tos_runtime.operations.schema_ledger.ensure_schema_current`, which on a
    ``was_fresh=True`` file stamps ``PRAGMA user_version`` and ``INSERT``s the genesis
    ``schema_ledger`` row (``schema_ledger.py:167-181``). A probe doing that on the SAME path a
    composing runtime is opening at that moment makes BOTH parties observe ``was_fresh=True`` —
    the probe wins the race to the ``INSERT``, and compose's own construction dies on
    ``sqlite3.IntegrityError: UNIQUE constraint failed: schema_ledger.version``, surfacing as
    ``run: refused — compose_paper_runtime raised IntegrityError: ...``. A "read-only probe" that
    writes is not a read-only probe. ``tests/compose/test_store_probe_isolation.py`` pins both
    halves of this deterministically.

    ``mode=ro`` (a URI connection, ``uri=True``) is what makes it structurally read-only rather
    than read-only by convention: sqlite itself refuses every CONTENT write on such a connection
    — no table, no row, no ``user_version`` — so no future edit to this helper can quietly
    reintroduce the genesis write. It is not "touches nothing": reading a WAL database still
    updates that database's ``-shm`` read marks, as ANY reader must, ``SqliteSnapshotStore
    .latest_as_of`` included. That is exactly the line ``test_store_probe_isolation
    ._CONTENT_FILE_SUFFIXES`` draws when it asserts byte-equality over the database and its
    ``-wal`` and deliberately not over the ``-shm``. It reads a WAL database another live
    connection owns exactly as ``SqliteSnapshotStore`` itself would.

    The URI is built with :meth:`pathlib.Path.as_uri`, never ``f"file:{db_path}?mode=ro"``: that
    naive form breaks on any path containing a URI-special character, and it breaks SILENTLY —
    measured, a path holding ``?`` makes sqlite read the truncated prefix as a DIFFERENT
    (auto-created, empty) database and answer ``no such table: snapshots`` instead of failing,
    i.e. it would report "no tick yet" forever. ``as_uri`` percent-encodes those characters.

    The table/column names are :class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore`'s own
    (``snapshots (instrument TEXT, as_of_ms INTEGER, ...)``, ``store.py:120-128``) and the query
    is character-for-character the one :meth:`~tos_runtime.marketfeed.store.SqliteSnapshotStore
    .latest_as_of` runs (``store.py:367-369``) — this reads the same durable truth the store
    would report, it does not reimplement a second notion of "latest".

    Args:
        db_path: The snapshot store's sqlite file (``data_dir / MARKETFEED_FILE_NAME``).
        instrument: The ``snapshots.instrument`` value to bound the query by.
        on_state: Optional observer, called with a one-line description of HOW this call ended
            — which of the "not there (yet)" states it hit, or that it really read a value. A
            polling caller keeps the last one so its own timeout message can say whether the
            probe ever even opened the file: "the runtime never created the store" and "the
            store was there and the row never arrived" are different failures, and a bare
            "no tick observed" conflates them.

    Returns:
        The stored ``MAX(as_of_ms)`` for ``instrument``, or ``None`` when the file does not
        exist yet, exists but carries no ``snapshots`` table yet (the store is mid-construction),
        or carries no row for ``instrument``.
    """

    def _state(description: str) -> None:
        if on_state is not None:
            on_state(description)

    if not db_path.exists():
        _state("the store file does not exist yet")
        return None
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        # The file existed for the `exists()` check but is not openable as a database yet.
        _state(f"the store file exists but sqlite could not open it: {exc}")
        return None
    try:
        row = conn.execute(
            "SELECT MAX(as_of_ms) FROM snapshots WHERE instrument = ?", (instrument,)
        ).fetchone()
    except sqlite3.Error as exc:
        # Every "the composing runtime has not finished creating this file" state, of which
        # there is more than one class and they are NOT all `OperationalError`: "no such table:
        # snapshots" (DDL not committed yet) IS an ``OperationalError``, but a half-written
        # header reads as ``sqlite3.DatabaseError: file is not a database``, which is
        # ``OperationalError``'s SIBLING, not its subclass (measured). Catching only
        # ``OperationalError`` would let that one escape — into the sender THREAD, where an
        # escaping exception prints a traceback and kills the poller rather than failing a
        # test. ``sqlite3.Error`` is the whole family, and returning ``None`` is honest for all
        # of it: "no tick observed yet". Nothing is silently passed over — a file that never
        # becomes readable ends as a failed ``assert _observed_tick()`` naming the timeout AND,
        # via ``on_state``, the last thing sqlite actually said about the file.
        _state(f"the store file opened but could not be queried: {exc}")
        return None
    finally:
        conn.close()
    if row is None or row[0] is None:
        _state(f"the store file opened and queried cleanly; no {instrument!r} row yet")
        return None
    _state(f"read a durable as_of for {instrument!r}")
    return int(row[0])


def test_cli_main_run_argv_path_composes_and_actually_ticks(
    tmp_path: Path,
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Enters at the REAL argv path (``cli.main(["run", ...])``, exactly what a real launcher
    invokes) against a REAL ``compose_paper_runtime`` and a REAL tick source configured on disk
    — no monkeypatched ``compose_paper_runtime``, no fake scheduler. The loop is bounded the
    ONLY way ``dispatch_run`` itself supports (module docstring of
    ``tos_runtime.compose._run_dispatch`` — SIGINT/SIGTERM flip the injected stop predicate
    between passes): a background thread sends a real ``SIGINT`` to this process.

    **Known flake class — a real-signal-from-a-thread test — and why this shape survives it**
    (team-lead directive, PR #725 delta review). The FIRST implementation of this test used a
    fixed ``time.sleep(0.15)`` before sending ``SIGINT``. That crashed the WHOLE pytest session
    with an uncaught ``KeyboardInterrupt`` — not a clean failure of this test alone — under two
    distinct conditions found while building it:

    1. Composition legitimately taking longer than the guessed sleep (no promised upper bound
       on ``compose_paper_runtime``'s own wall-clock cost).
    2. The reviewer's own mutation 4 (revert ``main()``'s dispatch back to a bare ``return 0``):
       ``cli.main()`` then returns almost instantly, well before the sleep elapses, so the
       DEFAULT Python ``SIGINT`` handler (raises ``KeyboardInterrupt``) is still installed —
       ``install_run_stop_signal_handlers`` never got a chance to run — and the signal lands
       asynchronously wherever the main thread happens to be by the time the sleep expires:
       pytest's own teardown, or the NEXT test's setup, not this test's own assertions.

    A fixed sleep cannot distinguish "compose is still running" from "compose already finished
    (or never started)" — it only ever guesses elapsed wall-clock time, and that guess is wrong
    in both directions under load. The fix is to poll a REAL condition instead of guessing a
    duration: the sender opens its own independent READ-ONLY connection to the SAME durable
    store file the final assertion reads (``read_only_latest_as_of`` — a second connection from
    a second thread, which never crosses a ``sqlite3`` thread-affinity rule because the store
    only ever touches its own connection from its own thread, and which cannot disturb the
    composing runtime because ``mode=ro`` makes sqlite refuse every CONTENT write on it — the
    ``-shm`` read marks any reader updates are the one thing that still moves; see that
    helper's docstring for the genesis race a store-CONSTRUCTING probe caused here) and sends
    ``SIGINT`` only once it observes the real tick has already landed, OR — bounded by :data:`_TICK_WAIT_TIMEOUT_S` — gives up waiting and
    sends ``SIGINT`` anyway so a genuinely stuck ``run_forever`` still gets unstuck rather than
    hanging the process forever; see :func:`_send_sigint_once_ticked_or_deadline`'s own
    docstring for the exact state machine and why each branch is safe. **If a future person is
    tempted to replace this polling with a fixed sleep "to simplify it": don't — that is
    reintroducing the exact bug this paragraph documents.**

    Evidence of an actual tick is read back from the durable snapshot STORE FILE
    (``data_dir / MARKETFEED_FILE_NAME``), reopened fresh after ``main()`` returns — never the
    in-process ``composed`` object (``cli.main`` returns only an exit code, by design; a second,
    independent connection to the same on-disk sqlite file is exactly the durability guarantee
    ``run`` is supposed to provide)."""
    config_dir = config_dir_with_risk_state
    fx.write_band_strategy_file(config_dir)
    _write_construction_yaml(config_dir)
    journal_path = tmp_path / "journal.jsonl"
    as_of_ms = _as_of_ms()
    _write_journal(
        journal_path,
        [_observation_line(raw_event_id="raw-cli-main-argv", as_of_ms=as_of_ms)],
    )
    _write_critical_input_policy(config_dir)
    _write_fast_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    marketfeed_db_path = data_dir / MARKETFEED_FILE_NAME
    main_done = threading.Event()

    # The last thing the probe managed to do with the file, for the timeout message below: a
    # test that only says "no tick observed" cannot distinguish "compose never created the
    # store" from "the store was there and the row never arrived".
    last_probe_state = ["the probe never ran"]

    def _record_probe_state(description: str) -> None:
        last_probe_state[0] = description

    def _observed_tick() -> bool:
        # READ-ONLY, by sqlite's own enforcement — never `SqliteSnapshotStore(...)`, whose
        # constructor writes the schema-ledger genesis row and races compose's own. See
        # `read_only_latest_as_of`'s docstring for the full mechanism.
        return (
            read_only_latest_as_of(
                marketfeed_db_path,
                instrument=fx.INSTRUMENT,
                on_state=_record_probe_state,
            )
            == as_of_ms
        )

    def _send_sigint_once_ticked_or_deadline() -> None:
        """Three exit paths, in the order they can happen:

        1. **Tick observed** (the expected path): breaks out of the poll loop and sends
           ``SIGINT`` — guarded by one more ``main_done`` check right before ``os.kill``, since
           ``main()`` could in principle finish between the ``break`` and the signal (an
           extremely narrow window; harmless either way, see branch 2).
        2. **``main_done`` set while still polling**: ``cli.main()`` already returned on its
           own — a mutated/broken ``dispatch_run`` that returns without ever composing (e.g.
           reviewer mutation 4) makes this happen almost instantly. Checked at the TOP of every
           iteration (5ms poll interval — the same value the loop sleeps for below, so the
           worst-case detection latency after ``main()`` returns is one iteration, not the full
           ``_TICK_WAIT_TIMEOUT_S`` deadline). Returns WITHOUT sending anything — sending a
           signal into an already-exited call risks hitting an already-restored default
           handler, the exact original bug.
        3. **Deadline reached with no tick ever observed and ``main()`` still running**: this
           is the "hung ``run_forever``" case a naive "give up and send nothing" would leave
           parked forever (nothing else in this test process would ever ask it to stop) — that
           was this function's own behavior before this hardening pass, and it is exactly the
           silent-hang risk a load-sensitive signal test must not have. Sending ``SIGINT`` here
           unconditionally (guarded only by the same ``main_done`` check) lets ``cli.main()``
           return normally, so the test proceeds to its own assertions instead of wedging the
           whole suite — the final ``assert _observed_tick()`` then fails with a message naming
           the timeout, a normal test failure instead of a hang.

        The poll loop no longer swallows exceptions. It used to (``except Exception: pass``)
        because the probe CONSTRUCTED a store and therefore raised on mid-construction file
        states — the very writes behind the genesis race ``read_only_latest_as_of`` now closes.
        That probe is total: every "not there yet" state is a ``None`` return, so an exception
        escaping here is a real defect and must stay visible. The ``finally`` preserves branch
        3's unstick guarantee for that case too — ``cli.main()`` still gets its ``SIGINT``, so an
        unexpected error fails this test instead of wedging the suite.
        """
        deadline = time.monotonic() + _TICK_WAIT_TIMEOUT_S
        try:
            while time.monotonic() < deadline:
                if main_done.is_set():
                    return  # branch 2 — the `finally` guard sends nothing in this case
                if _observed_tick():
                    break  # branch 1
                time.sleep(0.005)
        finally:
            # branch 1 (break) reaches here too, deliberately — this guard is the ONLY place
            # any exit path actually sends the signal.
            if not main_done.is_set():
                os.kill(os.getpid(), signal.SIGINT)

    sender = threading.Thread(target=_send_sigint_once_ticked_or_deadline, daemon=True)
    sender.start()
    try:
        exit_code = cli.main(
            [
                "run",
                "--config-dir",
                str(config_dir),
                "--data-dir",
                str(data_dir),
                "--custody-root",
                str(custody_root),
                "--environment-label",
                "non-live-test",
            ]
        )
    finally:
        main_done.set()
        sender.join(timeout=_TICK_WAIT_TIMEOUT_S + 1)

    assert exit_code == 0
    assert "run: stopped" in capsys.readouterr().out
    assert _observed_tick(), (
        f"no tick observed within {_TICK_WAIT_TIMEOUT_S}s of `cli.main(['run', ...])` "
        "returning — either compose never wired the tick source, or the sender's deadline "
        "SIGINT fired before a real tick could land (see _send_sigint_once_ticked_or_deadline). "
        f"Last probe of {marketfeed_db_path}: {last_probe_state[0]}"
    )


# ----------------------------------------------------------------------------
# (2) `_dispatch_run`'s own refusal paths, against real files on disk
# ----------------------------------------------------------------------------


def test_dispatch_run_refuses_when_construction_yaml_is_missing(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # config_dir already carries every OTHER file compose_paper_runtime needs (conftest.py's
    # own fixture) — deliberately no construction.yaml, so the loader is the FIRST thing that
    # can refuse, never reaching compose_paper_runtime at all.
    assert not (config_dir / "construction.yaml").exists()

    exit_code = cli._dispatch_run(_run_args(config_dir, data_dir, custody_root))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "construction.yaml" in err
    assert "not found" in err


def test_dispatch_run_refuses_on_a_still_tbd_leaf(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_construction_yaml(config_dir, overrides={"outbound_side": "TBD"})

    exit_code = cli._dispatch_run(_run_args(config_dir, data_dir, custody_root))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "outbound_side" in err
    assert "TBD" in err


def test_dispatch_run_refuses_when_no_tick_source_is_wired(
    tmp_path: Path,
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fully composable ``--config-dir`` (loader succeeds, ``compose_paper_runtime`` succeeds)
    but with no ``marketfeed.yaml``/``critical_input_policy.yaml`` at all — the exact "legitimate
    compose state, illegitimate `run` state" plan §2 decision 3 names."""
    config_dir = config_dir_with_risk_state
    fx.write_band_strategy_file(config_dir)
    _write_construction_yaml(config_dir)
    assert not (config_dir / "marketfeed.yaml").exists()
    assert not (config_dir / "critical_input_policy.yaml").exists()

    exit_code = cli._dispatch_run(_run_args(config_dir, data_dir, custody_root))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "marketfeed" in err
    assert "marketfeed.yaml" in err
    assert "critical_input_policy.yaml" in err
