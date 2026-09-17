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

import time
from pathlib import Path

import pytest
import yaml
from tos_runtime.compose import cli
from tos_runtime.compose._transport_wiring import TransportKind

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
