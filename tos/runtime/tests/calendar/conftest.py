"""Hermetic fixtures for tos_runtime.calendar tests (D1.4: tmp_path only, no"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from tos_runtime.calendar.config import CalendarConfig, load_calendar_config

STOCK_CLASS = "krx-stock-fixture"
FUTURES_CLASS = "krx-futures-fixture"
UNKNOWN_CLASS = "unknown-instrument-class"

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
    """Write ``text`` (default: the standard fixture calendar) to a fresh"""
    path = tmp_path / "calendar.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def fixture_calendar_path(tmp_path: Path) -> Path:
    return write_fixture_calendar(tmp_path)


@pytest.fixture
def fixture_calendar(fixture_calendar_path: Path) -> CalendarConfig:
    return load_calendar_config(fixture_calendar_path)
