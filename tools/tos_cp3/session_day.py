"""One trading day's session window, read from the tenant calendar — dated overrides included.

Issue #924. KRX moves the open and close on some days (the college-entrance-exam
day: stock and index futures each open and close an hour late; the two markets
do not shift the same way). The tenant calendar declares such a day once, under
``session_overrides``; every legacy-side reader asks THIS module for "the window
on this date", so the producer, the runner's waits and the cron wrapper's stop
time all move together and none of them carries a second copy of a time.

The runtime has its own loader for the same key
(``tos_runtime.calendar.config._parse_session_overrides``): the import firewall
keeps ``tools/`` and ``tos_runtime`` apart, so there are two readers of one file.
``tests/tools/test_cp3_session_day.py`` and
``tos/runtime/tests/calendar/test_session_overrides.py`` pin both sides against the
same fixture shape.

Imports: the standard library and ``yaml`` only. The cron wrapper and the runner
import this from a bare checkout (``PYTHONPATH=<tree>``); ``tools/tos_cp3/__init__``
is docstring-only, so nothing heavier comes with it.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import yaml

#: The calendar key the dated exceptions live under (same key the runtime reads).
OVERRIDES_KEY = "session_overrides"


class SessionDayError(RuntimeError):
    """The calendar does not name exactly one window for that session, phase and day."""


@dataclass(frozen=True)
class DayWindow:
    """One phase window on one date, naive KST times."""

    phase: str
    start: time
    end: time
    #: True when a ``session_overrides`` entry supplied this window.
    overridden: bool


def parse_hhmm(value: Any, *, where: str) -> time:
    try:
        hour_text, minute_text = str(value).split(":")
        return time(int(hour_text), int(minute_text))
    except (TypeError, ValueError) as exc:
        raise SessionDayError(f"{where}={value!r} is not HH:MM") from exc


def _override_entries(
    calendar: Mapping[str, Any], session_id: str, day: date
) -> list[Any] | None:
    """The raw override windows of *session_id* on *day*, or ``None`` when none applies."""
    raw = calendar.get(OVERRIDES_KEY, {})
    if raw is None or not isinstance(raw, Mapping):
        raise SessionDayError(
            f"{OVERRIDES_KEY} must be a mapping (an empty one means 'no dated exceptions')"
        )
    for key, override in raw.items():
        key_day = key if isinstance(key, date) else date.fromisoformat(str(key))
        if key_day != day:
            continue
        sessions = override.get("sessions") if isinstance(override, Mapping) else None
        if not isinstance(sessions, Mapping):
            raise SessionDayError(f"{OVERRIDES_KEY}[{key}] has no 'sessions' mapping")
        entries = sessions.get(session_id)
        if entries is None:
            return None
        if not isinstance(entries, list) or not entries:
            raise SessionDayError(
                f"{OVERRIDES_KEY}[{key}].sessions.{session_id} must be a non-empty list"
            )
        return entries
    return None


def windows_on(
    calendar: Mapping[str, Any], session_id: str, day: date | None
) -> tuple[DayWindow, ...]:
    """Every window of *session_id* on *day*: the override's if one applies, else the regular ones.

    ``day=None`` asks for the regular windows only.
    """
    override = None if day is None else _override_entries(calendar, session_id, day)
    if override is not None:
        entries, overridden = override, True
    else:
        sessions = calendar.get("sessions")
        if not isinstance(sessions, Mapping) or session_id not in sessions:
            raise SessionDayError(f"the calendar declares no session {session_id!r}")
        entries, overridden = sessions[session_id], False
        if not isinstance(entries, list):
            raise SessionDayError(f"sessions.{session_id} is not a list")
    windows = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise SessionDayError(f"{session_id}[{i}] is not a mapping")
        windows.append(
            DayWindow(
                phase=str(entry.get("phase")),
                start=parse_hhmm(entry.get("start"), where=f"{session_id}[{i}].start"),
                end=parse_hhmm(entry.get("end"), where=f"{session_id}[{i}].end"),
                overridden=overridden,
            )
        )
    return tuple(windows)


def phase_window(
    calendar: Mapping[str, Any], session_id: str, phase: str, day: date | None
) -> DayWindow:
    """The ONE *phase* window of *session_id* on *day* (``None``: the regular one)."""
    matching = [w for w in windows_on(calendar, session_id, day) if w.phase == phase]
    if len(matching) != 1:
        raise SessionDayError(
            f"session {session_id!r} has {len(matching)} {phase!r} window(s) on "
            f"{day or 'a regular day'}; exactly one is required"
        )
    return matching[0]


@dataclass(frozen=True)
class ProducerSession:
    """The calendar a producer config points at, and the session it names."""

    calendar_path: Path
    calendar: Mapping[str, Any]
    session_id: str
    phase: str

    def window(self, day: date | None) -> DayWindow:
        try:
            return phase_window(self.calendar, self.session_id, self.phase, day)
        except SessionDayError as exc:
            raise SessionDayError(f"{self.calendar_path}: {exc}") from exc

    def open_delay_s(self, day: date) -> int:
        """Seconds *day*'s open is later than the regular open (0 on a regular day)."""
        regular, today = self.window(None), self.window(day)
        delta = datetime.combine(day, today.start) - datetime.combine(
            day, regular.start
        )
        return max(0, int(delta.total_seconds()))

    def stop_at(self, day: date, *, after_close_min: int) -> str:
        """``HH:MM`` — *after_close_min* minutes past *day*'s close."""
        stop = datetime.combine(day, self.window(day).end) + timedelta(
            minutes=after_close_min
        )
        if stop.date() != day:
            raise SessionDayError(f"stop time {stop} is not on {day}")
        return stop.strftime("%H:%M")


def load_producer_session(
    producer_config: Path, *, repo_root: Path, calendar_path: Path | None = None
) -> ProducerSession:
    """Read ``calendar_yaml`` / ``calendar_session_id`` / ``calendar_session_phase``
    from a producer config and load that calendar.

    ``calendar_path`` replaces the config's own calendar path — the wrapper's
    preflight reads both files out of ``origin/main`` into temporary files.
    """
    data = yaml.safe_load(producer_config.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise SessionDayError(f"{producer_config}: not a YAML mapping")
    try:
        calendar_value = str(data["calendar_yaml"])
        session_id = str(data["calendar_session_id"])
        phase = str(data["calendar_session_phase"])
    except KeyError as exc:
        raise SessionDayError(
            f"{producer_config} does not carry {exc.args[0]!r}, so the session "
            "window cannot be read from the producer's own settings"
        ) from exc
    if calendar_path is None:
        candidate = Path(calendar_value).expanduser()
        calendar_path = candidate if candidate.is_absolute() else repo_root / candidate
    calendar = yaml.safe_load(calendar_path.read_text(encoding="utf-8"))
    if not isinstance(calendar, Mapping):
        raise SessionDayError(f"{calendar_path}: not a YAML mapping")
    return ProducerSession(
        calendar_path=calendar_path,
        calendar=calendar,
        session_id=session_id,
        phase=phase,
    )


def main(argv: list[str] | None = None) -> int:
    """``stop-at`` / ``open-delay`` / ``show`` for the shell wrappers (stdout: one value)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("stop-at", "open-delay", "show"))
    parser.add_argument("--producer-config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, default=None)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--after-close-min", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        session = load_producer_session(
            args.producer_config, repo_root=args.repo_root, calendar_path=args.calendar
        )
        if args.command == "stop-at":
            if args.after_close_min is None or args.after_close_min < 0:
                raise SessionDayError("stop-at needs --after-close-min >= 0")
            print(session.stop_at(args.date, after_close_min=args.after_close_min))
        elif args.command == "open-delay":
            print(session.open_delay_s(args.date))
        else:
            w = session.window(args.date)
            print(
                f"{session.session_id} {session.phase} {args.date} "
                f"{w.start:%H:%M}-{w.end:%H:%M} "
                f"{'OVERRIDE' if w.overridden else 'regular'}"
            )
    except (SessionDayError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"session_day: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
