"""Hermetic fixtures for tos_runtime.calendar tests (D1.4: tmp_path only, no
external network, no ambient env — same discipline as
tos/runtime/tests/compose/conftest.py).

The calendar VALUES below (session windows, holiday, expiry rule) are
FIXTURE DATA authored for this test suite, derived from the legacy KST facts
recorded in scratchpad/w5-survey-legacy.md §1-3 (e.g. KRX stock regular
09:00-15:30, futures regular 08:45-15:45, night session, quarterly
second-Thursday expiry) — they are NOT the operator-signed production
calendar (Phase 5 W5 plan §2 decision 1/§6 ②, which is still all named-TBD
`null` in tos/runtime/config/calendar.example.yaml).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from tos_runtime.calendar.config import CalendarConfig, load_calendar_config

STOCK_CLASS = "krx-stock-fixture"
FUTURES_CLASS = "krx-futures-fixture"
UNKNOWN_CLASS = "unknown-instrument-class"

#: 2026-01-01 is a Thursday (verified by test_config.py itself, not trusted
#: here) — a deliberately-chosen holiday that ALSO falls on what would
#: otherwise be a regular trading weekday, so the holiday-overrides-weekday
#: case is exercised.
FIXTURE_HOLIDAY = "2026-01-01"

FIXTURE_CALENDAR_YAML = textwrap.dedent(f"""\
    calendar_version: "w5-fixture-v1"
    tz_id: "Asia/Seoul"
    closed_phase: "CLOSED"
    holidays:
      - "{FIXTURE_HOLIDAY}"
    sessions:
      {STOCK_CLASS}:
        - phase: "CONTINUOUS"
          start: "09:00"
          end: "15:30"
          days: [MON, TUE, WED, THU, FRI]
          crosses_midnight: false
      {FUTURES_CLASS}:
        - phase: "CONTINUOUS"
          start: "08:45"
          end: "15:45"
          days: [MON, TUE, WED, THU, FRI]
          crosses_midnight: false
        - phase: "NIGHT"
          start: "23:00"
          end: "05:00"
          days: [MON, TUE, WED, THU, FRI]
          crosses_midnight: true
    futures_expiry:
      {FUTURES_CLASS}:
        weekday: "THU"
        ordinal: 2
        months: [3, 6, 9, 12]
        expired_phase: "EXPIRED"
    """)


def write_fixture_calendar(tmp_path: Path, text: str = FIXTURE_CALENDAR_YAML) -> Path:
    """Write ``text`` (default: the standard fixture calendar) to a fresh
    file under ``tmp_path`` and return its path."""
    path = tmp_path / "calendar.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def fixture_calendar_path(tmp_path: Path) -> Path:
    return write_fixture_calendar(tmp_path)


@pytest.fixture
def fixture_calendar(fixture_calendar_path: Path) -> CalendarConfig:
    return load_calendar_config(fixture_calendar_path)
