"""Front-month rollover helpers (2026-09-11 A01609 expiry incident).

KOSPI200 September 2026 (A01609) expired on Thursday 2026-09-10; from 09-11 the
front is A01612 (expiry 2026-12-10). Every date here is pinned — nothing
compares against the wall clock.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time

import pytest

import shared.execution.futures_instrument as fi
from shared.execution.futures_instrument import (
    FRONT_MONTH_ROLL_EXIT_CODE,
    KST,
    FrontMonthRolloverSchedule,
    FuturesInstrumentConfig,
    front_month_changed,
    front_month_roll_message,
    resolve_futures_instrument_from_env,
    run_with_front_month_watch,
)

_EXPIRY_DAY = date(2026, 9, 10)
_DAY_AFTER = date(2026, 9, 11)
_NO_OVERRIDE: dict[str, str] = {}
_F200_SEPT = FuturesInstrumentConfig(
    symbol="A01609", product="kospi200", source="FUTURES_TRADING_PRODUCT"
)
_EVERY_TICK = FrontMonthRolloverSchedule(
    check_time=time(8, 30), poll_interval_seconds=0.0
)


# --------------------------------------------------------------------------- #
# front_month_changed
# --------------------------------------------------------------------------- #


def test_expiry_day_keeps_the_expiring_contract():
    assert (
        front_month_changed("A01609", "kospi200", _EXPIRY_DAY, environ=_NO_OVERRIDE)
        is None
    )


def test_day_after_expiry_returns_the_next_quarterly_code():
    assert (
        front_month_changed("A01609", "kospi200", _DAY_AFTER, environ=_NO_OVERRIDE)
        == "A01612"
    )


def test_mini_rolls_monthly():
    assert (
        front_month_changed("A05609", "mini", _DAY_AFTER, environ=_NO_OVERRIDE)
        == "A05610"
    )


def test_explicit_symbol_override_disables_the_roll():
    assert (
        front_month_changed(
            "A01609",
            "kospi200",
            _DAY_AFTER,
            environ={"FUTURES_STRATEGY_SYMBOL": "A01609"},
        )
        is None
    )


def test_roll_message_names_both_codes_and_the_new_expiry():
    assert front_month_roll_message("A01609", "A01612") == (
        "futures front-month rolled: A01609 -> A01612 (expiry 2026-12-10)"
    )


def test_resolver_default_date_is_kst_not_host_date(monkeypatch):
    """08:30 KST on 09-11 is still 09-10 in UTC.

    A restarted daemon must resolve the same contract the KST daily check
    compared against, or it would exit again on its first check (restart loop).
    """

    import shared.instruments.futures as instruments

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            # 2026-09-10 23:30 UTC == 2026-09-11 08:30 KST
            return datetime(2026, 9, 11, 8, 30, tzinfo=KST).astimezone(tz)

    class _UtcHostDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 10)  # what a UTC-clock host reports

    monkeypatch.setattr(fi, "datetime", _Clock)
    monkeypatch.setattr(fi, "date", _UtcHostDate)
    monkeypatch.setattr(instruments, "date", _UtcHostDate)
    instrument = resolve_futures_instrument_from_env(
        environ={"FUTURES_TRADING_PRODUCT": "kospi200"}
    )
    assert instrument.symbol == "A01612"


# --------------------------------------------------------------------------- #
# FrontMonthRolloverSchedule
# --------------------------------------------------------------------------- #


def test_schedule_reads_market_schedule_yaml():
    schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule.check_time == time(8, 30)
    assert schedule.poll_interval_seconds == 60.0


def test_schedule_falls_back_to_defaults_on_unreadable_config(monkeypatch, caplog):
    from shared.config.loader import ConfigLoader

    def _boom(*_args, **_kwargs):
        raise OSError("config missing")

    monkeypatch.setattr(ConfigLoader, "load", _boom)
    with caplog.at_level(logging.WARNING, logger=fi.__name__):
        schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule == FrontMonthRolloverSchedule()
    assert "front_month_rollover schedule unreadable" in caplog.text


# --------------------------------------------------------------------------- #
# run_with_front_month_watch (the decoupled daemons' daily check)
# --------------------------------------------------------------------------- #


class _FakeDaemon:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self.stop_calls = 0

    async def run(self) -> None:
        await self._stop.wait()

    async def stop(self) -> None:
        self.stop_calls += 1
        self._stop.set()


def _clock(*instants: datetime):
    """now_fn returning ``instants`` in order, then repeating the last one."""
    seq = list(instants)

    def _now() -> datetime:
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _now


@pytest.mark.asyncio
async def test_day_after_expiry_stops_daemon_with_roll_exit_code(caplog):
    daemon = _FakeDaemon()
    now_fn = _clock(
        datetime(2026, 9, 11, 8, 29, tzinfo=KST),  # before check_time: no check
        datetime(2026, 9, 11, 8, 30, tzinfo=KST),
    )

    with caplog.at_level(logging.WARNING, logger=fi.__name__):
        code = await asyncio.wait_for(
            run_with_front_month_watch(
                daemon.run,
                daemon.stop,
                _F200_SEPT,
                daemon_name="test-daemon",
                schedule=_EVERY_TICK,
                environ=_NO_OVERRIDE,
                now_fn=now_fn,
            ),
            timeout=5,
        )

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert daemon.stop_calls == 1
    assert (
        "futures front-month rolled: A01609 -> A01612 (expiry 2026-12-10)"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_expiry_day_checks_once_and_keeps_running(monkeypatch):
    daemon = _FakeDaemon()
    checks: list[date] = []
    real_changed = fi.front_month_changed

    def _counting_changed(symbol, product, today, *, environ=None):  # noqa: ANN001
        checks.append(today)
        return real_changed(symbol, product, today, environ=environ)

    monkeypatch.setattr(fi, "front_month_changed", _counting_changed)
    polls = 0

    def _now() -> datetime:
        nonlocal polls
        polls += 1
        if polls == 20:  # a signal arrives later the same day
            asyncio.get_running_loop().call_soon(daemon._stop.set)
        return datetime(2026, 9, 10, 8, 30 + min(polls, 29), tzinfo=KST)

    code = await asyncio.wait_for(
        run_with_front_month_watch(
            daemon.run,
            daemon.stop,
            _F200_SEPT,
            daemon_name="test-daemon",
            schedule=_EVERY_TICK,
            environ=_NO_OVERRIDE,
            now_fn=_now,
        ),
        timeout=5,
    )

    assert code == 0
    assert daemon.stop_calls == 0
    assert checks == [_EXPIRY_DAY]  # once per KST day, not once per poll


@pytest.mark.asyncio
async def test_pinned_symbol_runs_without_a_check(caplog):
    daemon = _FakeDaemon()
    pinned = FuturesInstrumentConfig(
        symbol="A01609", product="kospi200", source="FUTURES_STRATEGY_SYMBOL"
    )

    def _now() -> datetime:
        raise AssertionError("pinned contract must not be checked")

    async def _run_then_signal() -> None:
        asyncio.get_running_loop().call_soon(daemon._stop.set)
        await daemon.run()

    with caplog.at_level(logging.INFO, logger=fi.__name__):
        code = await asyncio.wait_for(
            run_with_front_month_watch(
                _run_then_signal,
                daemon.stop,
                pinned,
                daemon_name="test-daemon",
                schedule=_EVERY_TICK,
                now_fn=_now,
            ),
            timeout=5,
        )

    assert code == 0
    assert "front-month rollover check disabled" in caplog.text
