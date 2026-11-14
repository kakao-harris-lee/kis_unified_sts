"""Pure session-phase and futures-maturity functions over a"""

from __future__ import annotations

import calendar
import datetime
import zoneinfo

from tos_runtime.calendar.config import CalendarConfig, ExpiryRule, SessionWindow
from tos_runtime.calendar.model import MaturityFact, PhaseFact

__all__ = [
    "session_phase_at",
    "maturity_at",
    "effective_phase_at",
    "trading_date_at",
]

_BOUNDARY_SEARCH_HORIZON_DAYS = 8

_SOURCE = "calendar"


def _to_local(instant_unix_ms: int, tz: zoneinfo.ZoneInfo) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(instant_unix_ms / 1000.0, tz=tz)


def _to_unix_ms(instant_local: datetime.datetime) -> int:
    return int(instant_local.timestamp() * 1000)


def _active_window_at(
    instant_local: datetime.datetime,
    instrument_class: str,
    cfg: CalendarConfig,
) -> tuple[SessionWindow, datetime.datetime, datetime.datetime] | None:
    """Return ``(window, occurrence_start, occurrence_end)`` for the one"""
    tz = instant_local.tzinfo
    holidays = cfg.holidays
    today = instant_local.date()
    yesterday = today - datetime.timedelta(days=1)
    for window in cfg.windows_on(today, instrument_class):
        if today.weekday() in window.days and today not in holidays:
            start_dt = datetime.datetime.combine(today, window.start, tzinfo=tz)
            end_date = (
                today + datetime.timedelta(days=1) if window.crosses_midnight else today
            )
            end_dt = datetime.datetime.combine(end_date, window.end, tzinfo=tz)
            if start_dt <= instant_local < end_dt:
                return window, start_dt, end_dt
    for window in cfg.windows_on(yesterday, instrument_class):
        if (
            window.crosses_midnight
            and yesterday.weekday() in window.days
            and yesterday not in holidays
        ):
            start_dt = datetime.datetime.combine(yesterday, window.start, tzinfo=tz)
            end_dt = datetime.datetime.combine(today, window.end, tzinfo=tz)
            if start_dt <= instant_local < end_dt:
                return window, start_dt, end_dt
    return None


def _next_window_start(
    instant_local: datetime.datetime,
    instrument_class: str,
    cfg: CalendarConfig,
) -> datetime.datetime | None:
    """Return the earliest window-occurrence start strictly after"""
    tz = instant_local.tzinfo
    for offset in range(_BOUNDARY_SEARCH_HORIZON_DAYS + 1):
        day = instant_local.date() + datetime.timedelta(days=offset)
        if day in cfg.holidays:
            continue
        day_candidates = [
            datetime.datetime.combine(day, window.start, tzinfo=tz)
            for window in cfg.windows_on(day, instrument_class)
            if day.weekday() in window.days
        ]
        day_candidates = [dt for dt in day_candidates if dt > instant_local]
        if day_candidates:
            return min(day_candidates)
    return None


def trading_date_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> str | None:
    """The KST trading date (``YYYYMMDD``) an order acknowledged at ``instant_unix_ms`` belongs"""
    if instrument_class not in cfg.sessions:
        return None
    tz = zoneinfo.ZoneInfo(cfg.tz_id)
    active = _active_window_at(_to_local(instant_unix_ms, tz), instrument_class, cfg)
    if active is None:
        return None
    window, start_dt, _end_dt = active
    if window.crosses_midnight:
        return None
    return start_dt.strftime("%Y%m%d")


def session_phase_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> PhaseFact:
    """The session-phase fact for ``instrument_class`` at ``instant_unix_ms``."""
    if instrument_class not in cfg.sessions:
        return PhaseFact(
            phase=None,
            is_open=None,
            boundary_unix_ms=None,
            source=_SOURCE,
            calendar_version=cfg.calendar_version,
        )
    tz = zoneinfo.ZoneInfo(cfg.tz_id)
    instant_local = _to_local(instant_unix_ms, tz)
    active = _active_window_at(instant_local, instrument_class, cfg)
    if active is not None:
        window, _start_dt, end_dt = active
        return PhaseFact(
            phase=window.phase,
            is_open=True,
            boundary_unix_ms=_to_unix_ms(end_dt),
            source=_SOURCE,
            calendar_version=cfg.calendar_version,
        )
    next_start = _next_window_start(instant_local, instrument_class, cfg)
    boundary_unix_ms = _to_unix_ms(next_start) if next_start is not None else None
    return PhaseFact(
        phase=cfg.closed_phase,
        is_open=False,
        boundary_unix_ms=boundary_unix_ms,
        source=_SOURCE,
        calendar_version=cfg.calendar_version,
    )


def _nth_weekday_of_month(
    year: int, month: int, weekday: int, ordinal: int
) -> datetime.date:
    """The ``ordinal``-th ``weekday`` of ``(year, month)``."""
    cal = calendar.Calendar()
    matches = [
        day
        for day in cal.itermonthdates(year, month)
        if day.month == month and day.weekday() == weekday
    ]
    return matches[ordinal - 1]


def _next_rule_month(year: int, month: int, months: frozenset[int]) -> tuple[int, int]:
    """The next ``(year, month)`` at or after ``(year, month + 1)`` whose"""
    y, m = year, month
    for _ in range(12):
        m += 1
        if m > 12:
            m = 1
            y += 1
        if m in months:
            return y, m
    raise ValueError("ExpiryRule.months is empty — no rule month exists")


def _last_regular_window_end(
    day: datetime.date, windows: tuple[SessionWindow, ...], tz: zoneinfo.ZoneInfo
) -> datetime.datetime | None:
    """The end-of-day instant of the LATEST non-crossing window whose start"""
    ends = [
        window.end
        for window in windows
        if not window.crosses_midnight and day.weekday() in window.days
    ]
    if not ends:
        return None
    return datetime.datetime.combine(day, max(ends), tzinfo=tz)


def maturity_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> MaturityFact:
    """The futures-maturity fact for ``instrument_class`` at"""
    rule: ExpiryRule | None = cfg.futures_expiry.get(instrument_class)
    if rule is None:
        return MaturityFact(expiry_date=None, expired=None, rule_present=False)
    tz = zoneinfo.ZoneInfo(cfg.tz_id)
    instant_local = _to_local(instant_unix_ms, tz)
    today = instant_local.date()
    this_month_expiry = (
        _nth_weekday_of_month(today.year, today.month, rule.weekday, rule.ordinal)
        if today.month in rule.months
        else None
    )
    if this_month_expiry is not None and today <= this_month_expiry:
        expiry_date = this_month_expiry
    else:
        year, month = _next_rule_month(today.year, today.month, rule.months)
        expiry_date = _nth_weekday_of_month(year, month, rule.weekday, rule.ordinal)
    if today < expiry_date:
        expired: bool | None = False
    else:
        windows = cfg.windows_on(expiry_date, instrument_class)
        last_end = _last_regular_window_end(expiry_date, windows, tz)
        expired = False if last_end is None else instant_local >= last_end
    return MaturityFact(expiry_date=expiry_date, expired=expired, rule_present=True)


def effective_phase_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> PhaseFact:
    """``session_phase_at``, except once ``maturity_at(...).expired is True``"""
    phase_fact = session_phase_at(instant_unix_ms, instrument_class, cfg)
    maturity_fact = maturity_at(instant_unix_ms, instrument_class, cfg)
    if maturity_fact.expired is True:
        rule = cfg.futures_expiry[instrument_class]
        return PhaseFact(
            phase=rule.expired_phase,
            is_open=False,
            boundary_unix_ms=phase_fact.boundary_unix_ms,
            source=phase_fact.source,
            calendar_version=phase_fact.calendar_version,
        )
    return phase_fact
