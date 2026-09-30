"""``tos_runtime.calendar.phase.trading_date_at`` (plan 2026-09-26 egress trading date, T-2).

The KST trading date an acknowledged order belongs to: the local date of an open window that does
not cross midnight, and ``None`` everywhere the calendar cannot say — outside every window, an
unknown class, and (operator 2026-09-26) any midnight-crossing session.
"""

from __future__ import annotations

import datetime
import zoneinfo

from tos_runtime.calendar.phase import trading_date_at

from .conftest import FIXTURE_HOLIDAY, FUTURES_CLASS, STOCK_CLASS, UNKNOWN_CLASS

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


def _kst_ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    return int(
        datetime.datetime(year, month, day, hour, minute, tzinfo=_KST).timestamp()
        * 1000
    )


def test_open_day_window_gives_the_kst_date(fixture_calendar) -> None:
    assert trading_date_at(
        _kst_ms(2026, 1, 5, 10, 0), STOCK_CLASS, fixture_calendar
    ) == ("20260105")
    assert trading_date_at(
        _kst_ms(2026, 1, 5, 8, 45), FUTURES_CLASS, fixture_calendar
    ) == ("20260105")


def test_kst_date_not_utc_date(fixture_calendar) -> None:
    """08:50 KST on 2026-01-06 is 23:50 UTC on 2026-01-05 — the date must be the KST one."""
    instant = _kst_ms(2026, 1, 6, 8, 50)
    assert datetime.datetime.fromtimestamp(instant / 1000, tz=datetime.UTC).day == 5
    assert trading_date_at(instant, FUTURES_CLASS, fixture_calendar) == "20260106"


def test_midnight_crossing_session_is_none_on_both_sides_of_midnight(
    fixture_calendar,
) -> None:
    assert (
        trading_date_at(_kst_ms(2026, 1, 5, 23, 30), FUTURES_CLASS, fixture_calendar)
        is None
    )
    assert (
        trading_date_at(_kst_ms(2026, 1, 6, 2, 0), FUTURES_CLASS, fixture_calendar)
        is None
    )


def test_outside_every_window_is_none(fixture_calendar) -> None:
    assert (
        trading_date_at(_kst_ms(2026, 1, 5, 16, 0), STOCK_CLASS, fixture_calendar)
        is None
    )
    assert (
        trading_date_at(_kst_ms(2026, 1, 3, 10, 0), STOCK_CLASS, fixture_calendar)
        is None
    )
    holiday = datetime.date.fromisoformat(FIXTURE_HOLIDAY)
    assert (
        trading_date_at(
            _kst_ms(holiday.year, holiday.month, holiday.day, 10, 0),
            STOCK_CLASS,
            fixture_calendar,
        )
        is None
    )


def test_unknown_class_is_none(fixture_calendar) -> None:
    assert (
        trading_date_at(_kst_ms(2026, 1, 5, 10, 0), UNKNOWN_CLASS, fixture_calendar)
        is None
    )
