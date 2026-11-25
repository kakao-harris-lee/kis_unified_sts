"""Trading days and the session window — from the TENANT calendar, by decision."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.session_day import (
    SessionDayError,
    holidays_of,
    is_trading_day,
    validate_overrides,
    windows_on,
)


@dataclass(frozen=True)
class SessionWindow:
    """One phase window of one session id, as the tenant calendar declares it."""

    phase: str
    start: time
    end: time

    def last_bar_minute(self, day: date) -> datetime:
        """The naive-KST minute label of the session's LAST one-minute bar."""
        return datetime.combine(day, self.start).replace(
            hour=self.end.hour, minute=self.end.minute
        )

    def end_boundary(self, day: date) -> datetime:
        """The naive-KST instant past which the last bar can no longer grow."""
        return self.last_bar_minute(day) + timedelta(minutes=1)


@dataclass(frozen=True)
class RuntimeCalendar:
    """The tenant calendar's holiday set and session windows."""

    path: Path
    calendar_version: str
    tz_id: str
    holidays: frozenset[date]
    sessions: dict[str, tuple[SessionWindow, ...]]
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def is_trading_day(self, day: date) -> bool:
        """A weekday the calendar does not list as closed — in any year."""
        # SAFETY: known-holidays-only, no covered-year declaration (2026-11-20
        # operator directive). A coverage refusal here refuses EVERY session of a
        # year nobody has listed holidays for yet — measured 2027-01-04 ->
        # LiveProducerRefused at boot. Whether an unlisted day really traded is
        # settled by the rows the broker returns (frame.build_seed).
        return is_trading_day(day, self.holidays)

    def window(
        self, session_id: str, phase: str, day: date | None = None
    ) -> SessionWindow:
        """The ONE *phase* window of *session_id*."""
        if day is not None:
            try:
                dated = [
                    w for w in windows_on(self.raw, session_id, day) if w.phase == phase
                ]
            except SessionDayError as exc:
                raise LiveProducerRefused(f"{self.path}: {exc}") from exc
            if len(dated) != 1:
                raise LiveProducerRefused(
                    f"{self.path}: session {session_id!r} has {len(dated)} "
                    f"{phase!r} windows on {day}; exactly one is required"
                )
            return SessionWindow(phase=phase, start=dated[0].start, end=dated[0].end)
        windows = self.sessions.get(session_id)
        if not windows:
            raise LiveProducerRefused(
                f"{self.path} declares no session {session_id!r} "
                f"(has {sorted(self.sessions)})"
            )
        matching = [window for window in windows if window.phase == phase]
        if len(matching) != 1:
            raise LiveProducerRefused(
                f"{self.path}: session {session_id!r} has {len(matching)} "
                f"{phase!r} windows; exactly one is required"
            )
        return matching[0]

    def trading_days_before(
        self, target: date, *, max_calendar_days: int
    ) -> Iterator[date]:
        """Yield trading days strictly before *target*, newest first."""
        day = target
        for _ in range(max_calendar_days):
            day -= timedelta(days=1)
            if self.is_trading_day(day):
                yield day


def _parse_time(value: str, *, path: Path, field: str) -> time:
    try:
        hour_text, minute_text = str(value).split(":")
        return time(int(hour_text), int(minute_text))
    except (TypeError, ValueError) as exc:
        raise LiveProducerRefused(f"{path}: {field}={value!r} is not HH:MM") from exc


def load_runtime_calendar(path: Path) -> RuntimeCalendar:
    """Read the tenant calendar YAML: its holidays, overrides and windows."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise LiveProducerRefused(f"{path}: not a YAML mapping")

    try:
        holidays = holidays_of(data)
    except SessionDayError as exc:
        raise LiveProducerRefused(f"{path}: {exc}") from exc

    raw_sessions = data.get("sessions")
    if not isinstance(raw_sessions, dict) or not raw_sessions:
        raise LiveProducerRefused(f"{path}: 'sessions' must be a non-empty mapping")
    sessions: dict[str, tuple[SessionWindow, ...]] = {}
    for session_id, entries in raw_sessions.items():
        if not isinstance(entries, list):
            raise LiveProducerRefused(f"{path}: sessions.{session_id} is not a list")
        sessions[str(session_id)] = tuple(
            SessionWindow(
                phase=str(entry["phase"]),
                start=_parse_time(
                    entry["start"], path=path, field=f"sessions.{session_id}.start"
                ),
                end=_parse_time(
                    entry["end"], path=path, field=f"sessions.{session_id}.end"
                ),
            )
            for entry in entries
        )

    try:
        validate_overrides(data, text=text)
    except SessionDayError as exc:
        raise LiveProducerRefused(f"{path}: {exc}") from exc

    version = data.get("calendar_version")
    tz_id = data.get("tz_id")
    if not isinstance(version, str) or not isinstance(tz_id, str):
        raise LiveProducerRefused(
            f"{path}: 'calendar_version' and 'tz_id' must both be strings"
        )
    return RuntimeCalendar(
        path=path,
        calendar_version=version,
        tz_id=tz_id,
        holidays=holidays,
        sessions=sessions,
        raw=data,
    )
