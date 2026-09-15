"""KST-native trading-calendar configuration loader (Phase 5 W5 plan §2
decision 1, ``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``).

**Calendar is data, phase judgement is the kernel's** — this module only
loads and validates the calendar's DATA (holidays, session windows, futures
expiry rules); it never judges admissibility itself. Session-phase TOKENS
(``phase: str`` on a window, ``closed_phase``, ``expired_phase``) are opaque
strings the config defines — this module never validates them against a
runtime enum, matching the kernel's own ``tos.venue.vocabulary.SessionPhase``,
which is deliberately not an enum (W5 survey §0 "세션 위상" row).

Fail-closed discipline, same idiom every ``tos_runtime.*.config`` loader in
this codebase follows (W5 survey §8; see e.g.
:mod:`tos_runtime.compose._egress_attestations`'s ``load_egress_attestations`
for the pattern this module copies): a missing file, a non-mapping top
level, a missing required key, or a required scalar left ``null``
(named-TBD) all refuse to load — never a silent default. ``holidays`` and
each per-class session-window list must be an EXPLICIT list (``[]`` is
accepted as a deliberate "there are none" value; ``null`` is refused as
still-TBD).

The `require_*_field` helpers in :mod:`tos_runtime.safety._policy_loader` are
NOT reused here (W5 survey §8: that module's helpers are scoped to
``safety/`` only, and no W4/W5-adjacent module imports them) — this module
re-implements its own inline validation, following the established
per-package convention.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import zoneinfo
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "CalendarConfigError",
    "SessionWindow",
    "ExpiryRule",
    "CalendarConfig",
    "load_calendar_config",
    "calendar_bind_digest",
]


class CalendarConfigError(RuntimeError):
    """Raised when the calendar config is missing, malformed, carries an
    unfilled (named-TBD) required field, an unresolvable ``tz_id``, an
    invalid date/time/day token, or overlapping session windows — fail-closed
    at load, never a silent default."""


#: Day-of-week vocabulary this loader accepts in ``days``/``weekday`` fields
#: (Monday=0 .. Sunday=6, matching ``datetime.date.weekday()``). This is a
#: PARSING vocabulary only (three-letter day names are a common, unambiguous
#: YAML spelling) — it is not a runtime phase-token enum and carries no
#: session-domain meaning of its own.
_DAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_DAY_INDEX: Mapping[str, int] = {name: i for i, name in enumerate(_DAY_NAMES)}


@dataclass(frozen=True)
class SessionWindow:
    """One session window for one instrument class.

    ``days`` is the set of weekdays (0=Mon..6=Sun) this window's occurrence
    STARTS on — for a window with ``crosses_midnight=True``, the occurrence
    that starts on day D runs until ``end`` on day D+1 (day membership is
    judged by the START day, never the day the instant itself falls on;
    plan §2 decision 1).
    """

    phase: str
    start: datetime.time
    end: datetime.time
    days: frozenset[int]
    crosses_midnight: bool


@dataclass(frozen=True)
class ExpiryRule:
    """A futures-expiry rule for one instrument class: the expiry date in a
    rule month is the ``ordinal``-th occurrence of ``weekday`` in that month
    (e.g. weekday=THU, ordinal=2 -> "second Thursday")."""

    weekday: int
    ordinal: int
    months: frozenset[int]
    expired_phase: str


@dataclass(frozen=True)
class CalendarConfig:
    """The fully loaded, validated KST trading calendar."""

    calendar_version: str
    tz_id: str
    holidays: frozenset[datetime.date]
    sessions: Mapping[str, tuple[SessionWindow, ...]]
    closed_phase: str
    futures_expiry: Mapping[str, ExpiryRule]


def _require_mapping(raw: Any, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CalendarConfigError(
            f"{path}: calendar config file must be a top-level mapping"
        )
    return raw


def _require_str_field(
    raw: dict[str, Any], key: str, path: Path, ctx: str = "calendar config"
) -> str:
    if key not in raw:
        raise CalendarConfigError(f"{path}: {ctx} missing required key {key!r}")
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise CalendarConfigError(
            f"{path}: {ctx} {key!r} is still null (named-TBD) or not a "
            "non-empty string — refusing to start until an operator fills "
            "it in"
        )
    return value


def _parse_day_token(token: Any, ctx: str, path: Path) -> int:
    if not isinstance(token, str) or token.upper() not in _DAY_INDEX:
        raise CalendarConfigError(
            f"{path}: {ctx} has an invalid weekday token {token!r} — must be "
            f"one of {_DAY_NAMES!r}"
        )
    return _DAY_INDEX[token.upper()]


def _parse_days(raw_days: Any, ctx: str, path: Path) -> frozenset[int]:
    if not isinstance(raw_days, list):
        raise CalendarConfigError(
            f"{path}: {ctx} 'days' must be an explicit list — refusing "
            "(null/missing is a named-TBD gap, not a silent 'every day')"
        )
    return frozenset(_parse_day_token(token, ctx, path) for token in raw_days)


def _parse_time_field(raw: Any, ctx: str, field: str, path: Path) -> datetime.time:
    if not isinstance(raw, str):
        raise CalendarConfigError(
            f"{path}: {ctx} {field!r} must be an 'HH:MM' string, got {raw!r}"
        )
    try:
        return datetime.time.fromisoformat(raw)
    except ValueError as exc:
        raise CalendarConfigError(
            f"{path}: {ctx} {field!r} is not a valid 'HH:MM' time: {raw!r}"
        ) from exc


def _require_bool_field(raw: dict[str, Any], key: str, ctx: str, path: Path) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise CalendarConfigError(
            f"{path}: {ctx} is missing a bool {key!r} field (or it is still "
            "null/named-TBD)"
        )
    return value


def _parse_session_window(raw: Any, ctx: str, path: Path) -> SessionWindow:
    if not isinstance(raw, dict):
        raise CalendarConfigError(f"{path}: {ctx} must be a mapping")
    phase = _require_str_field(raw, "phase", path, ctx)
    start = _parse_time_field(raw.get("start"), ctx, "start", path)
    end = _parse_time_field(raw.get("end"), ctx, "end", path)
    crosses_midnight = _require_bool_field(raw, "crosses_midnight", ctx, path)
    days = _parse_days(raw.get("days"), ctx, path)
    if crosses_midnight:
        if not (end < start):
            raise CalendarConfigError(
                f"{path}: {ctx} has crosses_midnight=true but end ({end}) is "
                f"not before start ({start}) — a crossing window must end "
                "strictly before it starts"
            )
    else:
        if not (end > start):
            raise CalendarConfigError(
                f"{path}: {ctx} has crosses_midnight=false but end ({end}) "
                f"is not after start ({start})"
            )
    return SessionWindow(
        phase=phase, start=start, end=end, days=days, crosses_midnight=crosses_midnight
    )


def _window_segments(window: SessionWindow) -> list[tuple[int, int, int]]:
    """Decompose a window into (weekday, start_minute, end_minute) segments,
    anchored to the day it STARTS on (module docstring). A crossing window
    contributes two segments: the evening piece on its start day, and the
    morning piece on the following day."""
    start_min = window.start.hour * 60 + window.start.minute
    end_min = window.end.hour * 60 + window.end.minute
    segments = []
    for day in window.days:
        if window.crosses_midnight:
            segments.append((day, start_min, 24 * 60))
            segments.append(((day + 1) % 7, 0, end_min))
        else:
            segments.append((day, start_min, end_min))
    return segments


def _check_overlaps(
    sessions: Mapping[str, tuple[SessionWindow, ...]], path: Path
) -> None:
    for instrument_class, windows in sessions.items():
        by_day: dict[int, list[tuple[int, int, str]]] = {}
        for window in windows:
            for day, start_min, end_min in _window_segments(window):
                by_day.setdefault(day, []).append((start_min, end_min, window.phase))
        for day, entries in by_day.items():
            for i in range(len(entries)):
                a_start, a_end, a_phase = entries[i]
                for j in range(i + 1, len(entries)):
                    b_start, b_end, b_phase = entries[j]
                    if a_start < b_end and b_start < a_end:
                        raise CalendarConfigError(
                            f"{path}: instrument class {instrument_class!r} "
                            f"has overlapping session windows on weekday "
                            f"index {day} between phases {a_phase!r} and "
                            f"{b_phase!r}"
                        )


def _parse_sessions(raw: Any, path: Path) -> Mapping[str, tuple[SessionWindow, ...]]:
    if not isinstance(raw, dict):
        raise CalendarConfigError(
            f"{path}: 'sessions' must be an explicit mapping — refusing "
            "(null/missing is a named-TBD gap, not a silent 'no classes')"
        )
    sessions: dict[str, tuple[SessionWindow, ...]] = {}
    for instrument_class, raw_windows in raw.items():
        if not isinstance(raw_windows, list):
            raise CalendarConfigError(
                f"{path}: sessions[{instrument_class!r}] must be an explicit "
                "list — refusing (null is a named-TBD gap; [] is accepted as "
                "a deliberate 'no windows, always closed_phase' value)"
            )
        windows = tuple(
            _parse_session_window(
                raw_window, f"sessions[{instrument_class!r}][{i}]", path
            )
            for i, raw_window in enumerate(raw_windows)
        )
        sessions[instrument_class] = windows
    _check_overlaps(sessions, path)
    return sessions


def _parse_expiry_rule(raw: Any, ctx: str, path: Path) -> ExpiryRule:
    if not isinstance(raw, dict):
        raise CalendarConfigError(f"{path}: {ctx} must be a mapping")
    weekday_token = raw.get("weekday")
    weekday = _parse_day_token(weekday_token, ctx, path)
    ordinal = raw.get("ordinal")
    if (
        not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or not (1 <= ordinal <= 5)
    ):
        raise CalendarConfigError(
            f"{path}: {ctx} 'ordinal' must be an int in 1..5, got {ordinal!r}"
        )
    raw_months = raw.get("months")
    if not isinstance(raw_months, list) or not raw_months:
        raise CalendarConfigError(
            f"{path}: {ctx} 'months' must be a non-empty explicit list of " "1..12 ints"
        )
    months = []
    for month in raw_months:
        if (
            not isinstance(month, int)
            or isinstance(month, bool)
            or not (1 <= month <= 12)
        ):
            raise CalendarConfigError(
                f"{path}: {ctx} 'months' entry {month!r} is not an int in 1..12"
            )
        months.append(month)
    expired_phase = _require_str_field(raw, "expired_phase", path, ctx)
    return ExpiryRule(
        weekday=weekday,
        ordinal=ordinal,
        months=frozenset(months),
        expired_phase=expired_phase,
    )


def _parse_futures_expiry(raw: Any, path: Path) -> Mapping[str, ExpiryRule]:
    if not isinstance(raw, dict):
        raise CalendarConfigError(
            f"{path}: 'futures_expiry' must be an explicit mapping — "
            "refusing (null is a named-TBD gap; {{}} is accepted as a "
            "deliberate 'no expiry rules' value)"
        )
    return {
        instrument_class: _parse_expiry_rule(
            raw_rule, f"futures_expiry[{instrument_class!r}]", path
        )
        for instrument_class, raw_rule in raw.items()
    }


def _parse_holidays(raw: Any, path: Path) -> frozenset[datetime.date]:
    if not isinstance(raw, list):
        raise CalendarConfigError(
            f"{path}: 'holidays' must be an explicit list of 'YYYY-MM-DD' "
            "strings — refusing (null/missing is a named-TBD gap, not a "
            "silent 'no holidays')"
        )
    dates = []
    for entry in raw:
        if not isinstance(entry, str):
            raise CalendarConfigError(
                f"{path}: holidays entry {entry!r} is not a 'YYYY-MM-DD' string"
            )
        try:
            dates.append(datetime.date.fromisoformat(entry))
        except ValueError as exc:
            raise CalendarConfigError(
                f"{path}: holidays entry {entry!r} is not a valid " "'YYYY-MM-DD' date"
            ) from exc
    return frozenset(dates)


def _validate_tz_id(tz_id: str, path: Path) -> None:
    try:
        zoneinfo.ZoneInfo(tz_id)
    except zoneinfo.ZoneInfoNotFoundError as exc:
        raise CalendarConfigError(
            f"{path}: tz_id {tz_id!r} could not be resolved by zoneinfo — "
            "check that the system tzdata database is installed (plan §6 ③)"
        ) from exc


def load_calendar_config(path: Path) -> CalendarConfig:
    """Load + fail-closed-validate a KST trading calendar from ``path``
    (shaped like ``tos/runtime/config/calendar.example.yaml``).

    Raises:
        CalendarConfigError: the file is missing/unreadable/not valid
            YAML/not a mapping; any required key is absent or still ``null``
            (named-TBD); ``tz_id`` does not resolve via ``zoneinfo``; a
            session window has a malformed time/day/crossing shape; or two
            session windows for the same instrument class overlap on the
            same weekday.
    """
    if not path.is_file():
        raise CalendarConfigError(f"calendar config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CalendarConfigError(
            f"calendar config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CalendarConfigError(
            f"calendar config file is not valid YAML: {path}"
        ) from exc
    raw = _require_mapping(raw, path)

    calendar_version = _require_str_field(raw, "calendar_version", path)
    tz_id = _require_str_field(raw, "tz_id", path)
    _validate_tz_id(tz_id, path)
    closed_phase = _require_str_field(raw, "closed_phase", path)
    if "holidays" not in raw:
        raise CalendarConfigError(
            f"{path}: calendar config missing required key 'holidays'"
        )
    holidays = _parse_holidays(raw["holidays"], path)
    if "sessions" not in raw:
        raise CalendarConfigError(
            f"{path}: calendar config missing required key 'sessions'"
        )
    sessions = _parse_sessions(raw["sessions"], path)
    if "futures_expiry" not in raw:
        raise CalendarConfigError(
            f"{path}: calendar config missing required key 'futures_expiry'"
        )
    futures_expiry = _parse_futures_expiry(raw["futures_expiry"], path)

    return CalendarConfig(
        calendar_version=calendar_version,
        tz_id=tz_id,
        holidays=holidays,
        sessions=sessions,
        closed_phase=closed_phase,
        futures_expiry=futures_expiry,
    )


def calendar_bind_digest(cfg: CalendarConfig) -> str:
    """A stable sha256 digest over the loaded, validated calendar content
    (module docstring; used for the ``SESSION_CALENDAR_BOUND`` evidence a
    later lane emits). No shared canonical-digest helper exists elsewhere in
    this codebase to reuse (W5 survey §8) — this is
    ``hashlib.sha256`` over ``json.dumps(..., sort_keys=True,
    separators=(",", ":"))`` of a canonical, JSON-safe projection of
    ``cfg``'s own fields (not the raw YAML text), so the digest is
    insensitive to incidental formatting/key-order in the source file and
    sensitive to any actual content change."""
    canonical = {
        "calendar_version": cfg.calendar_version,
        "tz_id": cfg.tz_id,
        "closed_phase": cfg.closed_phase,
        "holidays": sorted(d.isoformat() for d in cfg.holidays),
        "sessions": {
            instrument_class: [
                {
                    "phase": window.phase,
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "days": sorted(window.days),
                    "crosses_midnight": window.crosses_midnight,
                }
                for window in windows
            ]
            for instrument_class, windows in sorted(cfg.sessions.items())
        },
        "futures_expiry": {
            instrument_class: {
                "weekday": rule.weekday,
                "ordinal": rule.ordinal,
                "months": sorted(rule.months),
                "expired_phase": rule.expired_phase,
            }
            for instrument_class, rule in sorted(cfg.futures_expiry.items())
        },
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
