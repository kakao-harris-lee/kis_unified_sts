"""KST-native trading-calendar configuration loader (Phase 5 W5 plan §2"""

from __future__ import annotations

import datetime
import hashlib
import json
import zoneinfo
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "CalendarConfigError",
    "SessionWindow",
    "ExpiryRule",
    "CalendarConfig",
    "SessionOverride",
    "load_calendar_config",
    "calendar_bind_digest",
]


class CalendarConfigError(RuntimeError):
    """Raised when the calendar config is missing, malformed, carries an"""


_DAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_DAY_INDEX: Mapping[str, int] = {name: i for i, name in enumerate(_DAY_NAMES)}

_TBD_STR = "TBD"


@dataclass(frozen=True)
class SessionWindow:
    """One session window for one instrument class."""

    phase: str
    start: datetime.time
    end: datetime.time
    days: frozenset[int]
    crosses_midnight: bool


@dataclass(frozen=True)
class ExpiryRule:
    """A futures-expiry rule for one instrument class: the expiry date in a"""

    weekday: int
    ordinal: int
    months: frozenset[int]
    expired_phase: str


@dataclass(frozen=True)
class SessionOverride:
    """A date-specific replacement of one or more classes' session windows"""

    day: datetime.date
    reason: str
    sessions: Mapping[str, tuple[SessionWindow, ...]]


@dataclass(frozen=True)
class CalendarConfig:
    """The fully loaded, validated KST trading calendar."""

    calendar_version: str
    tz_id: str
    holidays: frozenset[datetime.date]
    sessions: Mapping[str, tuple[SessionWindow, ...]]
    closed_phase: str
    futures_expiry: Mapping[str, ExpiryRule]
    session_overrides: Mapping[datetime.date, SessionOverride] = field(
        default_factory=dict
    )

    def windows_on(
        self, day: datetime.date, instrument_class: str
    ) -> tuple[SessionWindow, ...]:
        """The windows that apply to ``instrument_class`` on ``day``: the"""
        override = self.session_overrides.get(day)
        if override is not None and instrument_class in override.sessions:
            return override.sessions[instrument_class]
        return self.sessions.get(instrument_class, ())


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
    if value == _TBD_STR:
        raise CalendarConfigError(
            f"{path}: {ctx} {key!r} is still the template placeholder {_TBD_STR!r} — "
            "operator-fill before activation"
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
    """Decompose a window into (weekday, start_minute, end_minute) segments,"""
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


def _check_expiry_rules_have_regular_windows(
    sessions: Mapping[str, tuple[SessionWindow, ...]],
    futures_expiry: Mapping[str, ExpiryRule],
    path: Path,
) -> None:
    """Refuse a ``futures_expiry`` rule whose instrument class has no regular"""
    for instrument_class in sorted(futures_expiry):
        rule = futures_expiry[instrument_class]
        windows = sessions.get(instrument_class, ())
        if not any(
            not window.crosses_midnight and rule.weekday in window.days
            for window in windows
        ):
            weekday_name = _DAY_NAMES[rule.weekday]
            shapes = (
                ", ".join(
                    f"{window.phase!r} {window.start}-{window.end} "
                    f"days={sorted(_DAY_NAMES[day] for day in window.days)} "
                    f"crosses_midnight={window.crosses_midnight}"
                    for window in windows
                )
                or "<no session windows at all>"
            )
            raise CalendarConfigError(
                f"{path}: futures_expiry[{instrument_class!r}] declares an "
                f"expiry rule on {weekday_name} but that instrument class has "
                "no regular (crosses_midnight=false) session window running on "
                f"{weekday_name} — refusing: the rule could never report the "
                "class expired, so its 'expired_phase' token would be silently "
                f"unreachable. Its windows are: {shapes}"
            )


def _parse_expiry_rule(raw: Any, ctx: str, path: Path) -> ExpiryRule:
    if not isinstance(raw, dict):
        raise CalendarConfigError(f"{path}: {ctx} must be a mapping")
    weekday_token = raw.get("weekday")
    weekday = _parse_day_token(weekday_token, ctx, path)
    ordinal = raw.get("ordinal")
    if (
        not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or not (1 <= ordinal <= 4)
    ):
        raise CalendarConfigError(
            f"{path}: {ctx} 'ordinal' must be an int in 1..4, got {ordinal!r} "
            "— refusing: a month is not guaranteed a fifth occurrence of a "
            "weekday, so an ordinal of 5 cannot be resolved in every rule month"
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


def _repeated_override_dates(text: str) -> list[str]:
    """Dates repeated as ``session_overrides`` keys, read from the YAML node tree."""
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    if not isinstance(root, yaml.MappingNode):
        return []
    for key_node, value_node in root.value:
        if getattr(key_node, "value", None) == "session_overrides" and isinstance(
            value_node, yaml.MappingNode
        ):
            seen: set[str] = set()
            repeated: list[str] = []
            for date_node, _ in value_node.value:
                key = str(date_node.value).strip()
                if key in seen:
                    repeated.append(key)
                seen.add(key)
            return repeated
    return []


def _parse_override_windows(
    raw_windows: list[Any],
    cls_ctx: str,
    path: Path,
    *,
    day: datetime.date,
    regular_phases: set[str],
) -> tuple[SessionWindow, ...]:
    """One class's override windows on ``day`` (shape rules: :func:`_parse_session_overrides`)."""
    windows = []
    for i, raw_window in enumerate(raw_windows):
        w_ctx = f"{cls_ctx}[{i}]"
        if not isinstance(raw_window, dict):
            raise CalendarConfigError(f"{path}: {w_ctx} must be a mapping")
        if "days" in raw_window:
            raise CalendarConfigError(
                f"{path}: {w_ctx} carries 'days' — an override applies "
                "to its own date only"
            )
        window = _parse_session_window(
            {**raw_window, "days": [_DAY_NAMES[day.weekday()]]}, w_ctx, path
        )
        if window.crosses_midnight:
            raise CalendarConfigError(
                f"{path}: {w_ctx} crosses midnight — dated overrides "
                "cover one calendar day only"
            )
        if window.phase not in regular_phases:
            raise CalendarConfigError(
                f"{path}: {w_ctx} phase {window.phase!r} is not one the "
                f"class's regular windows produce ({sorted(regular_phases)})"
            )
        windows.append(window)
    return tuple(windows)


def _parse_session_overrides(
    raw: Any,
    path: Path,
    *,
    sessions: Mapping[str, tuple[SessionWindow, ...]],
    holidays: frozenset[datetime.date],
) -> Mapping[datetime.date, SessionOverride]:
    """Parse the optional ``session_overrides`` mapping (issue #924)."""
    if not isinstance(raw, dict):
        raise CalendarConfigError(
            f"{path}: 'session_overrides' must be a mapping of 'YYYY-MM-DD' -> "
            "override — refusing (null is a named-TBD gap; {} is accepted as "
            "a deliberate 'no dated exceptions' value)"
        )
    overrides: dict[datetime.date, SessionOverride] = {}
    for raw_day, raw_override in raw.items():
        ctx = f"session_overrides[{raw_day!r}]"
        if isinstance(raw_day, datetime.date):
            day = raw_day
        else:
            try:
                day = datetime.date.fromisoformat(str(raw_day))
            except ValueError as exc:
                raise CalendarConfigError(
                    f"{path}: {ctx} key is not a valid 'YYYY-MM-DD' date"
                ) from exc
        if day in overrides:
            raise CalendarConfigError(
                f"{path}: {ctx} repeats date {day} — one entry per date "
                "(review #963: a quoted and an unquoted key both survive loading)"
            )
        if day in holidays:
            raise CalendarConfigError(
                f"{path}: {ctx} is also listed in 'holidays' — a closed day "
                "has no session to override"
            )
        if not isinstance(raw_override, dict):
            raise CalendarConfigError(f"{path}: {ctx} must be a mapping")
        reason = _require_str_field(raw_override, "reason", path, ctx)
        raw_sessions = raw_override.get("sessions")
        if not isinstance(raw_sessions, dict) or not raw_sessions:
            raise CalendarConfigError(
                f"{path}: {ctx} 'sessions' must be a non-empty mapping of "
                "instrument class -> windows"
            )
        by_class: dict[str, tuple[SessionWindow, ...]] = {}
        for instrument_class, raw_windows in raw_sessions.items():
            cls_ctx = f"{ctx}.sessions[{instrument_class!r}]"
            if instrument_class not in sessions:
                raise CalendarConfigError(
                    f"{path}: {cls_ctx} names a class the regular 'sessions' "
                    f"do not declare (has {sorted(sessions)})"
                )
            if not isinstance(raw_windows, list) or not raw_windows:
                raise CalendarConfigError(
                    f"{path}: {cls_ctx} must be a non-empty list — a day with "
                    "no session belongs in 'holidays'"
                )
            by_class[instrument_class] = _parse_override_windows(
                raw_windows,
                cls_ctx,
                path,
                day=day,
                regular_phases={w.phase for w in sessions[instrument_class]},
            )
        _check_overlaps(by_class, path)
        overrides[day] = SessionOverride(day=day, reason=reason, sessions=by_class)
    return overrides


def _validate_tz_id(tz_id: str, path: Path) -> None:
    try:
        zoneinfo.ZoneInfo(tz_id)
    except zoneinfo.ZoneInfoNotFoundError as exc:
        raise CalendarConfigError(
            f"{path}: tz_id {tz_id!r} could not be resolved by zoneinfo — "
            "check that the system tzdata database is installed (plan §6 ③)"
        ) from exc


def load_calendar_config(path: Path) -> CalendarConfig:
    """Load + fail-closed-validate a KST trading calendar from ``path``"""
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
    _check_expiry_rules_have_regular_windows(sessions, futures_expiry, path)
    repeated = _repeated_override_dates(text)
    if repeated:
        raise CalendarConfigError(
            f"{path}: 'session_overrides' repeats date(s) {repeated} — one entry per date"
        )
    session_overrides = _parse_session_overrides(
        raw.get("session_overrides", {}),
        path,
        sessions=sessions,
        holidays=holidays,
    )

    return CalendarConfig(
        calendar_version=calendar_version,
        tz_id=tz_id,
        holidays=holidays,
        sessions=sessions,
        closed_phase=closed_phase,
        futures_expiry=futures_expiry,
        session_overrides=session_overrides,
    )


def _window_projection(window: SessionWindow) -> dict[str, Any]:
    return {
        "phase": window.phase,
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "days": sorted(window.days),
        "crosses_midnight": window.crosses_midnight,
    }


def calendar_bind_digest(cfg: CalendarConfig) -> str:
    """A stable sha256 digest over the loaded, validated calendar content"""
    canonical: dict[str, Any] = {
        "calendar_version": cfg.calendar_version,
        "tz_id": cfg.tz_id,
        "closed_phase": cfg.closed_phase,
        "holidays": sorted(d.isoformat() for d in cfg.holidays),
        "sessions": {
            instrument_class: [_window_projection(window) for window in windows]
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
    if cfg.session_overrides:
        canonical["session_overrides"] = {
            day.isoformat(): {
                "reason": override.reason,
                "sessions": {
                    instrument_class: [_window_projection(w) for w in windows]
                    for instrument_class, windows in sorted(override.sessions.items())
                },
            }
            for day, override in sorted(cfg.session_overrides.items())
        }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
