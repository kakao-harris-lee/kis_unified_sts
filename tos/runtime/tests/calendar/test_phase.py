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


def test_expired_false_day_after_expiry_rolls_to_next_rule_month(
    fixture_calendar,
) -> None:
    """The day after a rule month's expiry, the CLASS is not matured — the next
    contract trades — so ``expired`` is ``False`` and ``expiry_date`` is the NEXT
    rule month's date, never the elapsed one.

    This test previously asserted ``expired is True`` here, pinning the
    class-level over-conservatism the 2026-09-13 runtime-operations wiring plan
    §7 recorded as a defect to carry forward ("클래스 단위 만기(월말까지
    EXPIRED)는 계약월 단위 모델로 후속"), not as intent.
    """
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day + 1, 0, 0, 0)
    fact = maturity_at(instant, FUTURES_CLASS, fixture_calendar)
    assert fact.expired is False
    assert fact.expiry_date == _second_thursday(2026, 6)


@pytest.mark.parametrize(
    ("day", "hour"),
    [
        (11, 10),  # the day after expiry, mid-session
        (28, 10),  # late in the same rule month
        (30, 10),  # the last day of the same rule month
    ],
)
def test_expired_false_every_day_after_expiry_in_a_rule_month(
    fixture_calendar, day: int, hour: int
) -> None:
    """The reported defect, at its reported dates: 2026-09-10 is the second
    Thursday of a rule month, and EVERY later instant inside September used to
    report the whole instrument class ``expired`` (so ``effective_phase_at``
    reported ``EXPIRED`` and a tick driver skipped every tick from 09-11 to
    09-30). Each of these must now report the December contract instead."""
    expiry = _second_thursday(2026, 9)
    assert expiry == datetime.date(2026, 9, 10)  # the plan's cited date, re-derived
    fact = maturity_at(_kst_ms(2026, 9, day, hour, 0), FUTURES_CLASS, fixture_calendar)
    assert fact.expired is False
    assert fact.expiry_date == _second_thursday(2026, 12)


def test_expiry_day_before_and_after_last_session_end_is_unchanged(
    fixture_calendar,
) -> None:
    """The expiry-day boundary itself is NOT changed by the roll: on 2026-09-10
    the class is not yet matured at 15:00 (inside the 08:45-15:45 regular
    window) and is matured at 16:00 (after it), with ``expiry_date`` staying on
    that day in both cases — it only rolls once the day has passed."""
    before = maturity_at(_kst_ms(2026, 9, 10, 15, 0), FUTURES_CLASS, fixture_calendar)
    after = maturity_at(_kst_ms(2026, 9, 10, 16, 0), FUTURES_CLASS, fixture_calendar)
    assert before.expired is False
    assert after.expired is True
    assert before.expiry_date == after.expiry_date == datetime.date(2026, 9, 10)


def test_expiry_roll_crosses_the_year_boundary(fixture_calendar) -> None:
    """December is the last rule month in [3, 6, 9, 12], so the day after its
    expiry must roll to MARCH OF THE NEXT YEAR — not wrap back to March 2026,
    and not report the class expired for the rest of December."""
    december_expiry = _second_thursday(2026, 12)
    assert december_expiry == datetime.date(2026, 12, 10)
    for day in (11, 31):
        fact = maturity_at(
            _kst_ms(2026, 12, day, 10, 0), FUTURES_CLASS, fixture_calendar
        )
        assert fact.expired is False, day
        assert fact.expiry_date == _second_thursday(2027, 3), day
        assert fact.expiry_date.year == 2027, day


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


def test_effective_phase_at_returns_expired_phase_after_last_session_on_expiry_day(
    fixture_calendar,
) -> None:
    """The fold still substitutes ``expired_phase`` — but only while the class
    really is matured, which (after the roll fix) is the expiry day after its
    last regular window ends.

    23:30 on the expiry day keeps this test's original strength: the fixture's
    NIGHT window (23:00->05:00) is open then, so the underlying phase is an
    OPEN session and the ``EXPIRED`` token can only come from the maturity
    fold. ``maturity_at`` judges the expiry-day flip on the last
    **non-crossing** window (15:45), which 23:30 is past.
    """
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day, 23, 30)

    underlying = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert underlying.phase == "NIGHT"
    assert underlying.is_open is True
    assert maturity_at(instant, FUTURES_CLASS, fixture_calendar).expired is True

    effective = effective_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert effective.phase == "EXPIRED"
    assert effective.is_open is False
    assert effective.boundary_unix_ms == underlying.boundary_unix_ms


def test_effective_phase_at_day_after_expiry_is_not_expired_phase(
    fixture_calendar,
) -> None:
    """The defect as the tick driver saw it: on the day after expiry the fold
    used to replace an open ``CONTINUOUS`` session with ``EXPIRED``, which the
    kernel's ``session_phase_admits`` refuses for every action — every tick from
    the day after expiry to month end was skipped. The fold must now be a
    no-op there."""
    expiry = _second_thursday(2026, 3)
    day_after = expiry + datetime.timedelta(days=1)
    instant = _kst_ms(day_after.year, day_after.month, day_after.day, 10, 0)

    underlying = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert underlying.phase == "CONTINUOUS"
    assert underlying.is_open is True

    effective = effective_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert effective.phase != "EXPIRED"
    assert effective == underlying


def test_effective_phase_at_matches_session_phase_before_expiry(
    fixture_calendar,
) -> None:
    expiry = _second_thursday(2026, 3)
    instant = _kst_ms(expiry.year, expiry.month, expiry.day - 1, 10, 0)
    effective = effective_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    underlying = session_phase_at(instant, FUTURES_CLASS, fixture_calendar)
    assert effective == underlying
