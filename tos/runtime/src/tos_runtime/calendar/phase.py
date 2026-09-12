"""Pure session-phase and futures-maturity functions over a
:class:`~tos_runtime.calendar.config.CalendarConfig` (Phase 5 W5 plan §2
decision 1).

Every function here is a pure function of ``(instant_unix_ms,
instrument_class, cfg)`` — no I/O, no clock read, no hidden state. The caller
(a later lane's ``SessionFactsOwner``) supplies the instant; this module only
judges what the calendar DATA says about that instant. It never asserts
admissibility itself — the kernel's own ``session_phase_admits`` (a venue
predicate the runtime never reimplements) is the sole authority on whether an
observed phase token permits an action; this module only produces the
opaque phase token the calendar defines (module docstring of
:mod:`tos_runtime.calendar.config`).
"""

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
]

#: How many calendar days forward a "closed -> next window open" boundary
#: search looks before giving up and reporting ``boundary_unix_ms=None``. A
#: calendar with sessions defined at all will always find a next occurrence
#: well within a week; this bound only guards against a pathological config
#: (e.g. every window's ``days`` set built from a typo that never matches)
#: silently spinning forever instead of honestly reporting "not found".
_BOUNDARY_SEARCH_HORIZON_DAYS = 8

_SOURCE = "calendar"


def _to_local(instant_unix_ms: int, tz: zoneinfo.ZoneInfo) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(instant_unix_ms / 1000.0, tz=tz)


def _to_unix_ms(instant_local: datetime.datetime) -> int:
    return int(instant_local.timestamp() * 1000)


def _active_window_at(
    instant_local: datetime.datetime,
    windows: tuple[SessionWindow, ...],
    holidays: frozenset[datetime.date],
) -> tuple[SessionWindow, datetime.datetime, datetime.datetime] | None:
    """Return ``(window, occurrence_start, occurrence_end)`` for the one
    window occurrence ``instant_local`` falls inside, or ``None`` if none
    does. Only occurrences whose START day is not a holiday are considered
    (module docstring on :class:`~tos_runtime.calendar.config.SessionWindow`:
    day membership is judged by the start day)."""
    tz = instant_local.tzinfo
    today = instant_local.date()
    yesterday = today - datetime.timedelta(days=1)
    for window in windows:
        if today.weekday() in window.days and today not in holidays:
            start_dt = datetime.datetime.combine(today, window.start, tzinfo=tz)
            end_date = (
                today + datetime.timedelta(days=1) if window.crosses_midnight else today
            )
            end_dt = datetime.datetime.combine(end_date, window.end, tzinfo=tz)
            if start_dt <= instant_local < end_dt:
                return window, start_dt, end_dt
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
    windows: tuple[SessionWindow, ...],
    holidays: frozenset[datetime.date],
) -> datetime.datetime | None:
    """Return the earliest window-occurrence start strictly after
    ``instant_local``, searching forward up to
    :data:`_BOUNDARY_SEARCH_HORIZON_DAYS` calendar days, or ``None`` if none
    is found in that horizon."""
    tz = instant_local.tzinfo
    for offset in range(_BOUNDARY_SEARCH_HORIZON_DAYS + 1):
        day = instant_local.date() + datetime.timedelta(days=offset)
        if day in holidays:
            continue
        day_candidates = [
            datetime.datetime.combine(day, window.start, tzinfo=tz)
            for window in windows
            if day.weekday() in window.days
        ]
        day_candidates = [dt for dt in day_candidates if dt > instant_local]
        if day_candidates:
            return min(day_candidates)
    return None


def session_phase_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> PhaseFact:
    """The session-phase fact for ``instrument_class`` at ``instant_unix_ms``.

    Unknown ``instrument_class`` (not a key in ``cfg.sessions`` at all) ->
    ``PhaseFact(None, None, None, ...)`` — never guessed. A KNOWN class with
    an explicit empty window list is a different, deliberate fact: always
    ``cfg.closed_phase``.
    """
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
    windows = cfg.sessions[instrument_class]
    active = _active_window_at(instant_local, windows, cfg.holidays)
    if active is not None:
        window, _start_dt, end_dt = active
        return PhaseFact(
            phase=window.phase,
            is_open=True,
            boundary_unix_ms=_to_unix_ms(end_dt),
            source=_SOURCE,
            calendar_version=cfg.calendar_version,
        )
    next_start = _next_window_start(instant_local, windows, cfg.holidays)
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
    cal = calendar.Calendar()
    matches = [
        day
        for day in cal.itermonthdates(year, month)
        if day.month == month and day.weekday() == weekday
    ]
    return matches[ordinal - 1]


def _next_rule_month(year: int, month: int, months: frozenset[int]) -> tuple[int, int]:
    """The next ``(year, month)`` at or after ``(year, month + 1)`` whose
    month number is in ``months``."""
    y, m = year, month
    for _ in range(12):
        m += 1
        if m > 12:
            m = 1
            y += 1
        if m in months:
            return y, m
    # Unreachable when `months` is non-empty (loader requires >=1 entry),
    # but never silently loop forever if it somehow were empty.
    raise ValueError("ExpiryRule.months is empty — no rule month exists")


def _last_regular_window_end(
    day: datetime.date, windows: tuple[SessionWindow, ...], tz: zoneinfo.ZoneInfo
) -> datetime.datetime | None:
    """The end-of-day instant of the LATEST non-crossing window whose start
    day is ``day``'s weekday, or ``None`` if the instrument class has no such
    window (e.g. no session config at all for that class)."""
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
    """The futures-maturity fact for ``instrument_class`` at
    ``instant_unix_ms``.

    ``rule_present=False`` (with ``expiry_date``/``expired`` both ``None``)
    means ``cfg.futures_expiry`` has no rule for this class at all — never
    guessed. When a rule exists but its instant is exactly the expiry date,
    ``expired`` flips to ``True`` only after that class's last regular
    (non-crossing) session window ends that day (plan §2 decision 1); if no
    such window exists for the class, the whole expiry day counts as not yet
    expired (there is no other fact to judge the moment from).
    """
    rule: ExpiryRule | None = cfg.futures_expiry.get(instrument_class)
    if rule is None:
        return MaturityFact(expiry_date=None, expired=None, rule_present=False)
    tz = zoneinfo.ZoneInfo(cfg.tz_id)
    instant_local = _to_local(instant_unix_ms, tz)
    today = instant_local.date()
    if today.month in rule.months:
        expiry_date = _nth_weekday_of_month(
            today.year, today.month, rule.weekday, rule.ordinal
        )
    else:
        year, month = _next_rule_month(today.year, today.month, rule.months)
        expiry_date = _nth_weekday_of_month(year, month, rule.weekday, rule.ordinal)
    if today > expiry_date:
        expired: bool | None = True
    elif today < expiry_date:
        expired = False
    else:
        windows = cfg.sessions.get(instrument_class, ())
        last_end = _last_regular_window_end(expiry_date, windows, tz)
        expired = False if last_end is None else instant_local >= last_end
    return MaturityFact(expiry_date=expiry_date, expired=expired, rule_present=True)


def effective_phase_at(
    instant_unix_ms: int, instrument_class: str, cfg: CalendarConfig
) -> PhaseFact:
    """``session_phase_at``, except once ``maturity_at(...).expired is True``
    the phase becomes the expiry rule's ``expired_phase`` (plan §2 decision
    7) — this is the token a later lane feeds to the kernel; the KERNEL
    decides admissibility by set membership, this module never says
    "admissible" itself."""
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
