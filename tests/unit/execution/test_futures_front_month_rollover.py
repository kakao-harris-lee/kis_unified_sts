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


def _schedule_yaml(monkeypatch, rollover: dict | None, *, futures_open="08:45"):
    from shared.config.loader import ConfigLoader

    futures: dict = {"regular": {"open": futures_open, "close": "15:45"}}
    if rollover is not None:
        futures["front_month_rollover"] = rollover
    data = {"market_schedule": {"futures": futures}}
    monkeypatch.setattr(ConfigLoader, "load", lambda *_a, **_k: data)


@pytest.mark.parametrize("poll", [0, -5])
def test_schedule_non_positive_poll_falls_back_to_default(monkeypatch, caplog, poll):
    _schedule_yaml(monkeypatch, {"check_time": "08:20", "poll_interval_seconds": poll})
    with caplog.at_level(logging.WARNING, logger=fi.__name__):
        schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule.poll_interval_seconds == 60.0
    assert schedule.check_time == time(8, 20)  # the valid key is still honoured
    assert "poll_interval_seconds" in caplog.text


@pytest.mark.parametrize("check_time", ["08:45", "09:10"])
def test_schedule_warns_when_check_is_not_before_the_open(
    monkeypatch, caplog, check_time
):
    _schedule_yaml(monkeypatch, {"check_time": check_time, "poll_interval_seconds": 60})
    with caplog.at_level(logging.WARNING, logger=fi.__name__):
        schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule.check_time.strftime("%H:%M") == check_time
    assert "is not before the futures open 08:45 KST" in caplog.text


def test_schedule_before_the_open_does_not_warn(monkeypatch, caplog):
    _schedule_yaml(monkeypatch, {"check_time": "08:44", "poll_interval_seconds": 30})
    with caplog.at_level(logging.WARNING, logger=fi.__name__):
        schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule == FrontMonthRolloverSchedule(
        check_time=time(8, 44), poll_interval_seconds=30.0
    )
    assert caplog.records == []


def test_schedule_missing_block_uses_defaults_at_info(monkeypatch, caplog):
    _schedule_yaml(monkeypatch, None)
    with caplog.at_level(logging.INFO, logger=fi.__name__):
        schedule = FrontMonthRolloverSchedule.from_yaml()
    assert schedule == FrontMonthRolloverSchedule()
    assert "front_month_rollover not configured" in caplog.text
    assert all(r.levelno == logging.INFO for r in caplog.records)


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


# --------------------------------------------------------------------------- #
# Watch task resilience (review F2)
# --------------------------------------------------------------------------- #


def _raising_once_then(*instants: datetime):
    """now_fn that raises on its first call, then behaves like ``_clock``."""
    later = _clock(*instants)
    calls = 0

    def _now() -> datetime:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("clock unavailable")
        return later()

    return _now


def _failure_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "front-month check failed" in r.message]


@pytest.mark.asyncio
async def test_watch_survives_a_raising_clock_and_still_rolls(caplog):
    daemon = _FakeDaemon()

    with caplog.at_level(logging.INFO, logger=fi.__name__):
        code = await asyncio.wait_for(
            run_with_front_month_watch(
                daemon.run,
                daemon.stop,
                _F200_SEPT,
                daemon_name="test-daemon",
                schedule=_EVERY_TICK,
                environ=_NO_OVERRIDE,
                now_fn=_raising_once_then(datetime(2026, 9, 11, 8, 31, tzinfo=KST)),
            ),
            timeout=5,
        )

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert daemon.stop_calls == 1
    (failure,) = _failure_records(caplog)
    assert failure.exc_info is not None  # logged with its traceback
    assert "front-month rolled: A01609 -> A01612" in caplog.text


@pytest.mark.asyncio
async def test_shutdown_after_an_earlier_watch_error_exits_zero(caplog):
    """A clean SIGTERM must not re-raise a watch failure and exit 1."""
    daemon = _FakeDaemon()
    polls = 0
    raising = _raising_once_then(datetime(2026, 9, 11, 8, 0, tzinfo=KST))

    def _now() -> datetime:
        nonlocal polls
        polls += 1
        if polls == 5:  # the signal arrives before the check time
            asyncio.get_running_loop().call_soon(daemon._stop.set)
        return raising()

    with caplog.at_level(logging.INFO, logger=fi.__name__):
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
    assert len(_failure_records(caplog)) == 1
    assert "front-month check recovered" in caplog.text


@pytest.mark.asyncio
async def test_failed_stop_is_retried_on_the_next_poll():
    daemon = _FakeDaemon()
    real_stop = daemon.stop
    attempts = 0

    async def _flaky_stop() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("redis blip during stop")
        await real_stop()

    code = await asyncio.wait_for(
        run_with_front_month_watch(
            daemon.run,
            _flaky_stop,
            _F200_SEPT,
            daemon_name="test-daemon",
            schedule=_EVERY_TICK,
            environ=_NO_OVERRIDE,
            now_fn=_clock(datetime(2026, 9, 11, 8, 30, tzinfo=KST)),
        ),
        timeout=5,
    )

    assert code == FRONT_MONTH_ROLL_EXIT_CODE
    assert attempts == 2
