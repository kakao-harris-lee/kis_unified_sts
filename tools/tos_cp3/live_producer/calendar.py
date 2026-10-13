"""Trading days and the session window — from the TENANT calendar, by decision.

⛔ Plan §3.2 forbids ``shared/collector/historical/calendar.py`` here: its
hardcoded ``KOREAN_HOLIDAYS`` is missing two 2026 substitute holidays (08-17
and 10-05), so it disagrees with ``config/market_schedule.yaml`` and with the
runtime calendar the session gate itself uses — and a seed walk that trusts it
stops on 10-05's empty response and refuses to start. The file read here is the
same one the runtime loads (``config/tos_runtime/<tenant>/calendar.yaml``).

**Why the session window comes from here and not from a literal.** The PR-1
evidence (§2.1-§2.2) establishes that the last bar of the day (15:45) can never
be completed by a successor raw row, because 15:46 is outside the session; the
only non-vacuous way to say "the session ended" is to read the window the
runtime reads. A hardcoded 15:45 would be a second source of truth that drifts
the first time the exchange moves the close.

The two halves of the equivalence this file needs are split by the firewall, so
a committed fixture is the hinge (plan §3.2, #892's shape):

* ``tos/runtime/tests/...`` — the real runtime calendar loader yields this
  trading-day list;
* ``tests/tools/test_cp3_live_producer.py`` — this module reproduces it
  byte-for-byte.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from tools.tos_cp3.live_producer.config import LiveProducerRefused


@dataclass(frozen=True)
class SessionWindow:
    """One phase window of one session id, as the tenant calendar declares it."""

    phase: str
    start: time
    end: time

    def last_bar_minute(self, day: date) -> datetime:
        """The naive-KST minute label of the session's LAST one-minute bar.

        The PR-1 evidence measured this identity on 2026-10-12: the last parsed
        bar was 15:45 and the calendar's futures CONTINUOUS window ends at
        15:45 (``last_parsed_bar_is_session_end_minute=true``).
        """
        return datetime.combine(day, self.start).replace(
            hour=self.end.hour, minute=self.end.minute
        )

    def end_boundary(self, day: date) -> datetime:
        """The naive-KST instant past which the last bar can no longer grow.

        One minute after the last bar's label: the 15:45 bar covers
        15:45:00-15:45:59, so 15:46:00 is "the session end time has elapsed",
        which the evidence §2.2 makes a REQUIRED completion condition rather
        than an option.
        """
        return self.last_bar_minute(day) + timedelta(minutes=1)


@dataclass(frozen=True)
class RuntimeCalendar:
    """The tenant calendar's holiday set, coverage and session windows."""

    path: Path
    calendar_version: str
    tz_id: str
    holidays: frozenset[date]
    #: Years this calendar is DECLARED to cover, supplied by the producer's own
    #: YAML (``calendar_covered_years``) — never inferred from the holiday
    #: dates. Plan §3.2 L2 requires an explicit refusal before the seed walk
    #: leaves the covered range rather than a silent "no holidays, so every
    #: weekday trades".
    #:
    #: ⚠ **Inference was wrong and is the reason this is declared** (review
    #: L4). Deriving the set from ``{d.year for d in holidays}`` makes ONE
    #: 2027-01-01 entry mark the whole of 2027 as covered, which is exactly the
    #: silent "every weekday trades" the refusal exists to prevent — and the
    #: tenant calendar is digest-bound, so it cannot be edited to carry the
    #: range itself. :func:`load_runtime_calendar` cross-checks the declared
    #: years against the file instead, so a year declared but absent from the
    #: holiday list is a startup refusal.
    covered_years: frozenset[int]
    sessions: dict[str, tuple[SessionWindow, ...]]

    def is_trading_day(self, day: date) -> bool:
        self.assert_covers(day)
        return day.weekday() < 5 and day not in self.holidays

    def assert_covers(self, day: date) -> None:
        if day.year not in self.covered_years:
            raise LiveProducerRefused(
                f"{self.path} covers {sorted(self.covered_years)}; {day} is "
                "outside it. A holiday set that does not cover the date would "
                "silently call a closed day a trading day (plan §3.2 L2)"
            )

    def window(self, session_id: str, phase: str) -> SessionWindow:
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
        """Yield trading days strictly before *target*, newest first.

        Walks CALENDAR days (so the budget is comparable to PR-1's
        ``max_seed_calendar_days``) and refuses as soon as the walk would leave
        the covered years.
        """
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


#: A declared covered year must carry at least this many holidays in the
#: calendar file. KRX closes far more days than this every year (the tenant
#: file lists 19 for 2026), so a year scraping past 1 is not a covered year —
#: it is a stray forward-dated entry (review L4).
MIN_HOLIDAYS_PER_COVERED_YEAR = 5


def load_runtime_calendar(
    path: Path, *, covered_years: Iterable[int]
) -> RuntimeCalendar:
    """Read the tenant calendar YAML and cross-check its declared range.

    Args:
        covered_years: the years the producer's YAML declares this calendar
            covers. Each one must actually carry holidays here, or startup is
            refused: the tenant file is digest-bound and cannot be edited to
            state its own range, so the declaration and the file are checked
            against each other instead of one being trusted (review L4).
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LiveProducerRefused(f"{path}: not a YAML mapping")

    raw_holidays = data.get("holidays")
    if not isinstance(raw_holidays, list) or not raw_holidays:
        raise LiveProducerRefused(f"{path}: 'holidays' must be a non-empty list")
    holidays = frozenset(date.fromisoformat(str(entry)) for entry in raw_holidays)

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

    version = data.get("calendar_version")
    tz_id = data.get("tz_id")
    if not isinstance(version, str) or not isinstance(tz_id, str):
        raise LiveProducerRefused(
            f"{path}: 'calendar_version' and 'tz_id' must both be strings"
        )
    declared = frozenset(int(year) for year in covered_years)
    if not declared:
        raise LiveProducerRefused(
            f"{path}: no covered years declared. Without a declared range the "
            "seed walk cannot tell 'this year has no holidays listed' from "
            "'this year is closed on no days' (plan §3.2 L2)"
        )
    per_year = Counter(day.year for day in holidays)
    thin = sorted(
        year for year in declared if per_year[year] < MIN_HOLIDAYS_PER_COVERED_YEAR
    )
    if thin:
        raise LiveProducerRefused(
            f"{path} declares {sorted(declared)} covered but carries "
            + ", ".join(f"{year}: {per_year[year]}" for year in thin)
            + f" holiday(s) — fewer than the {MIN_HOLIDAYS_PER_COVERED_YEAR} a "
            "real KRX year has. A year present only as a stray forward-dated "
            "entry would let every weekday in it read as a trading day "
            "(review L4)"
        )
    return RuntimeCalendar(
        path=path,
        calendar_version=version,
        tz_id=tz_id,
        holidays=holidays,
        covered_years=declared,
        sessions=sessions,
    )
