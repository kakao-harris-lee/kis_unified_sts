"""Compose-relative e2e tests for ``run`` (TOS ``run`` 구동 아크 plan"""

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

_FAST_POLL_INTERVAL_MS = 20
_REAL_SLEEP_SECONDS = 0.03


def _as_of_ms(offset_ms: int = 0) -> int:
    return int(time.time() * 1000) - 1000 + offset_ms


def _write_fast_marketfeed_config(
    config_dir: Path, *, journal_path: Path, instruments: tuple[str, ...]
) -> None:
    """The SAME shape ``test_marketfeed_wiring.py``'s own ``_write_marketfeed_config`` writes,"""
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(
            {
                "instruments": list(instruments),
                "instrument_class": fx.INSTRUMENT_CLASS,
                "account": fx.ACCOUNT,
                "direction": "LONG",
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


def _valid_construction_yaml() -> dict:
    """The SAME facts ``_fixtures.construction_config()`` injects, shaped for"""
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

    runtime.marketfeed.run_forever(sleep=_real_short_sleep, stop=_stop_after_n)

    assert passes == 5
    assert runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == as_of_ms

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_run_forever_ticks_a_second_real_observation_after_the_pacing_interval(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Two DISTINCT observations, both real ``TICKED`` passes — proves the loop does not just"""
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

    runtime.marketfeed.run_forever(
        sleep=_real_short_sleep, stop=_stop_after_second_tick
    )
    assert (
        runtime.marketfeed._store.latest_as_of(instrument=fx.INSTRUMENT) == second_as_of
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


_TICK_WAIT_TIMEOUT_S = 10.0


def read_only_latest_as_of(
    db_path: Path,
    *,
    instrument: str,
    on_state: Callable[[str], None] | None = None,
) -> int | None:
    """The newest durable ``as_of_ms`` for ``instrument`` in the snapshot-store file at"""

    def _state(description: str) -> None:
        if on_state is not None:
            on_state(description)

    if not db_path.exists():
        _state("the store file does not exist yet")
        return None
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        _state(f"the store file exists but sqlite could not open it: {exc}")
        return None
    try:
        row = conn.execute(
            "SELECT MAX(as_of_ms) FROM snapshots WHERE instrument = ?", (instrument,)
        ).fetchone()
    except sqlite3.Error as exc:
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enters at the REAL argv path (``cli.main(["run", ...])``, exactly what a real launcher"""
    config_dir = config_dir_with_risk_state
    now_ms = fx.pin_system_clock(monkeypatch, fx.LAST_MINUTE_OF_DAY_UNIX_MS)
    fx.write_band_strategy_file(config_dir)
    _write_construction_yaml(config_dir)
    journal_path = tmp_path / "journal.jsonl"
    as_of_ms = now_ms() - 100
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

    last_probe_state = ["the probe never ran"]

    def _record_probe_state(description: str) -> None:
        last_probe_state[0] = description

    def _observed_tick() -> bool:
        return (
            read_only_latest_as_of(
                marketfeed_db_path,
                instrument=fx.INSTRUMENT,
                on_state=_record_probe_state,
            )
            == as_of_ms
        )

    def _send_sigint_once_ticked_or_deadline() -> None:
        """Three exit paths, in the order they can happen:"""
        deadline = time.monotonic() + _TICK_WAIT_TIMEOUT_S
        try:
            while time.monotonic() < deadline:
                if main_done.is_set():
                    return
                if _observed_tick():
                    break
                time.sleep(0.005)
        finally:
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


def test_dispatch_run_refuses_when_construction_yaml_is_missing(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    """A fully composable ``--config-dir`` (loader succeeds, ``compose_paper_runtime`` succeeds)"""
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
