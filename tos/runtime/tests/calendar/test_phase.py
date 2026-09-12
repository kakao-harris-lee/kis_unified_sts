"""tos_runtime.calendar.phase — session_phase_at / maturity_at / effective_phase_at.

Every instant is built from an explicit KST wall-clock datetime via
zoneinfo, not a raw epoch literal, so each test case is legible against the
fixture calendar in conftest.py.
"""

from __future__ import annotations

import calendar
import datetime
import zoneinfo

import pytest
from tos_runtime.calendar.phase import effective_phase_at, maturity_at, session_phase_at

from .conftest import FIXTURE_HOLIDAY, FUTURES_CLASS, STOCK_CLASS, UNKNOWN_CLASS

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


def _kst_ms(
    year: int, month: int, day: int, hour: int, minute: int, second: int = 0
) -> int:
    dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=_KST)
    return int(dt.timestamp() * 1000)


def _second_thursday(year: int, month: int) -> datetime.date:
    """Independently computed (calendar.monthrange + weekday arithmetic, NOT
    a call into tos_runtime.calendar.phase) — the whole point of this helper
    is to cross-check the module under test against a from-scratch
    calculation, not to trust the plan's cited dates."""
    first_weekday, _days_in_month = calendar.monthrange(year, month)  # Monday=0
    thursday = 3
    offset = (thursday - first_weekday) % 7
    first_thursday_day = 1 + offset
    return datetime.date(year, month, first_thursday_day + 7)


# --- self-check: the fixture's cited holiday really is a Thursday ---------


def test_fixture_holiday_date_is_a_weekday() -> None:
    assert datetime.date.fromisoformat(FIXTURE_HOLIDAY).weekday() == 3  # Thursday


# --- session_phase_at: stock class -----------------------------------------


def test_weekday_regular_open(fixture_calendar) -> None:
    # 2026-01-05 is a Monday (self-verified: weekday() == 0).
    assert datetime.date(2026, 1, 5).weekday() == 0
    instant = _kst_ms(2026, 1, 5, 10, 0)
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CONTINUOUS"
    assert fact.is_open is True
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 5, 15, 30)
    assert fact.calendar_version == fixture_calendar.calendar_version
    assert fact.source == "calendar"


def test_weekday_after_hours_closed(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 15, 35)
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CLOSED"
    assert fact.is_open is False
    # next open: Tuesday 2026-01-06 09:00
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 6, 9, 0)


def test_saturday_closed(fixture_calendar) -> None:
    assert datetime.date(2026, 1, 3).weekday() == 5  # Saturday
    instant = _kst_ms(2026, 1, 3, 10, 0)
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CLOSED"
    assert fact.is_open is False
    # next open: Monday 2026-01-05 09:00
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 5, 9, 0)


def test_holiday_closed_even_on_a_weekday(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 1, 10, 0)  # Thursday, but a holiday
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CLOSED"
    assert fact.is_open is False
    # next open: Friday 2026-01-02 09:00 (not the holiday Thursday)
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 2, 9, 0)


def test_boundary_before_open(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 8, 59, 59)
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CLOSED"
    assert fact.is_open is False
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 5, 9, 0)


def test_boundary_at_open(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 9, 0, 0)
    fact = session_phase_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.phase == "CONTINUOUS"
    assert fact.is_open is True
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 5, 15, 30)


def test_unknown_instrument_class_is_none_triple(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 10, 0)
    fact = session_phase_at(instant, UNKNOWN_CLASS, fixture_calendar)
    assert fact.phase is None
    assert fact.is_open is None
    assert fact.boundary_unix_ms is None


# --- session_phase_at: night (crossing-midnight) window --------------------


def test_night_window_evening_start_is_open(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 23, 0, 0)  # Monday 23:00
    fact = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.phase == "NIGHT"
    assert fact.is_open is True
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 6, 5, 0)


def test_night_window_next_day_early_morning_is_open(fixture_calendar) -> None:
    instant = _kst_ms(
        2026, 1, 6, 2, 0, 0
    )  # Tuesday 02:00 — spillover from Monday night
    fact = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.phase == "NIGHT"
    assert fact.is_open is True
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 6, 5, 0)


def test_night_window_after_end_is_closed_until_day_session(fixture_calendar) -> None:
    instant = _kst_ms(
        2026, 1, 6, 6, 0, 0
    )  # Tuesday 06:00 — after night ends, before day session
    fact = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.phase == "CLOSED"
    assert fact.is_open is False
    assert fact.boundary_unix_ms == _kst_ms(2026, 1, 6, 8, 45)


# --- mutation lens M1: phase must not be a constant -------------------------


def test_mutation_lens_m1_phase_is_not_a_constant(fixture_calendar) -> None:
    """Guards against session_phase_at collapsing to a hardcoded literal
    (e.g. always "CONTINUOUS") regardless of the instant: holiday, weekend,
    and after-hours must all read CLOSED while a plain weekday 10:00 reads
    CONTINUOUS."""
    open_fact = session_phase_at(
        _kst_ms(2026, 1, 5, 10, 0), STOCK_CLASS, fixture_calendar
    )
    holiday_fact = session_phase_at(
        _kst_ms(2026, 1, 1, 10, 0), STOCK_CLASS, fixture_calendar
    )
    weekend_fact = session_phase_at(
        _kst_ms(2026, 1, 3, 10, 0), STOCK_CLASS, fixture_calendar
    )
    after_hours_fact = session_phase_at(
        _kst_ms(2026, 1, 5, 15, 35), STOCK_CLASS, fixture_calendar
    )

    assert open_fact.phase == "CONTINUOUS"
    assert open_fact.is_open is True
    for closed_fact in (holiday_fact, weekend_fact, after_hours_fact):
        assert closed_fact.phase == "CLOSED"
        assert closed_fact.is_open is False
    assert {open_fact.phase, holiday_fact.phase} == {"CONTINUOUS", "CLOSED"}


# --- maturity_at -------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "month"),
    [(2026, 3), (2026, 6), (2026, 9), (2026, 12)],
)
def test_second_thursday_known_dates(fixture_calendar, year: int, month: int) -> None:
    expected = _second_thursday(year, month)
    # cross-check the hand-derived helper itself against a brute-force scan,
    # so a bug in _second_thursday can't silently rubber-stamp phase.py.
    brute_force_matches = [
        d
        for d in (
            datetime.date(year, month, day)
            for day in range(1, calendar.monthrange(year, month)[1] + 1)
        )
        if d.weekday() == 3
    ]
    assert brute_force_matches[1] == expected

    instant = _kst_ms(
        year, month, expected.day, 10, 0
    )  # mid-morning on expiry day itself
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.rule_present is True
    assert fact.expiry_date == expected


def test_non_rule_month_rolls_to_next_rule_month(fixture_calendar) -> None:
    # April is not in [3, 6, 9, 12] -> next rule month is June.
    instant = _kst_ms(2026, 4, 15, 10, 0)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.rule_present is True
    assert fact.expiry_date == _second_thursday(2026, 6)
    assert fact.expired is False


def test_expired_false_before_expiry_date(fixture_calendar) -> None:
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day - 1, 10, 0)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.expired is False


def test_expired_false_before_last_window_end_on_expiry_day(fixture_calendar) -> None:
    expiry = _second_thursday(2026, 3)
    # the fixture's non-crossing regular window for FUTURES_CLASS ends 15:45
    instant = _kst_ms(expiry.year, expiry.month, expiry.day, 15, 44, 59)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.expired is False


def test_expired_true_exactly_at_last_window_end_on_expiry_day(
    fixture_calendar,
) -> None:
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day, 15, 45, 0)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.expired is True


def test_expired_true_day_after_expiry(fixture_calendar) -> None:
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day + 1, 0, 0, 0)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.expired is True


def test_maturity_rule_absent_returns_none_triple(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 10, 0)
    fact = maturity_at(instant, STOCK_CLASS, fixture_calendar)
    assert fact.rule_present is False
    assert fact.expiry_date is None
    assert fact.expired is None


def test_maturity_unknown_instrument_class(fixture_calendar) -> None:
    instant = _kst_ms(2026, 1, 5, 10, 0)
    fact = maturity_at(instant, UNKNOWN_CLASS, fixture_calendar)
    assert fact.rule_present is False
    assert fact.expiry_date is None
    assert fact.expired is None


# --- effective_phase_at ------------------------------------------------------


def test_effective_phase_at_returns_expired_phase_after_expiry(
    fixture_calendar,
) -> None:
    expiry = _second_thursday(2026, 3)
    day_after = expiry + datetime.timedelta(days=1)
    instant = _kst_ms(day_after.year, day_after.month, day_after.day, 10, 0)

    # sanity: the underlying session phase would otherwise be an open regular
    # session (day_after must be a weekday session day, not itself expired).
    underlying = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert underlying.phase == "CONTINUOUS"
    assert underlying.is_open is True

    effective = effective_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert effective.phase == "EXPIRED"
    assert effective.is_open is False
    assert effective.boundary_unix_ms == underlying.boundary_unix_ms


def test_effective_phase_at_matches_session_phase_before_expiry(
    fixture_calendar,
) -> None:
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day - 1, 10, 0)
    effective = effective_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    underlying = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert effective == underlying
