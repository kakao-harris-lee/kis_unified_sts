"""``recent_trading_dates`` — the bounded scan window issue #1096's ACK date recovery reads."""

from __future__ import annotations

import textwrap

from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.phase import recent_trading_dates

from .conftest import (
    FIXTURE_HOLIDAY,
    STOCK_CLASS,
    UNKNOWN_CLASS,
    write_fixture_calendar,
)


def test_the_window_ends_at_today_and_skips_the_weekend(fixture_calendar) -> None:
    """2026-01-09 is a Friday; the four dates before it are Thu/Wed/Tue/Mon, not Sat/Sun."""
    assert recent_trading_dates("20260109", STOCK_CLASS, fixture_calendar, 5) == (
        "20260105",
        "20260106",
        "20260107",
        "20260108",
        "20260109",
    )


def test_a_holiday_inside_the_window_is_not_a_scanned_date(fixture_calendar) -> None:
    """2026-01-01 (Thu) is the fixture holiday, so the window reaches back past it."""
    assert FIXTURE_HOLIDAY == "2026-01-01"
    dates = recent_trading_dates("20260105", STOCK_CLASS, fixture_calendar, 4)
    assert dates == ("20251230", "20251231", "20260102", "20260105")
    assert "20260101" not in dates


def test_a_session_override_day_counts_as_a_trading_date(tmp_path) -> None:
    """An override replaces the day's windows; the day still trades, so the scan must read it."""
    path = write_fixture_calendar(
        tmp_path,
        textwrap.dedent(f"""\
            calendar_version: "w5-fixture-override"
            tz_id: "Asia/Seoul"
            closed_phase: "CLOSED"
            holidays: []
            sessions:
              {STOCK_CLASS}:
                - phase: "CONTINUOUS"
                  start: "09:00"
                  end: "15:30"
                  days: [MON, TUE, WED, THU, FRI]
                  crosses_midnight: false
            futures_expiry: {{}}
            session_overrides:
              "2026-01-08":
                reason: "fixture — one hour later"
                sessions:
                  {STOCK_CLASS}:
                    - phase: "CONTINUOUS"
                      start: "10:00"
                      end: "16:30"
                      crosses_midnight: false
            """),
    )
    calendar = load_calendar_config(path)
    assert "20260108" in recent_trading_dates("20260109", STOCK_CLASS, calendar, 2)


def test_an_unknown_class_a_bad_date_and_a_non_positive_count_scan_nothing(
    fixture_calendar,
) -> None:
    assert recent_trading_dates("20260109", UNKNOWN_CLASS, fixture_calendar, 5) == ()
    assert recent_trading_dates("not-a-date", STOCK_CLASS, fixture_calendar, 5) == ()
    assert recent_trading_dates("20260109", STOCK_CLASS, fixture_calendar, 0) == ()
