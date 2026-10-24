"""Dated session overrides (issue #924) — loader shape, phase shift, digest.

The override date used here (2026-12-03, a Thursday) is FICTITIOUS: no KRX notice
moves that day. The real exam-day entry is added only once KRX publishes it.

Hermetic (D1.4): every case writes its own YAML under tmp_path.
"""

from __future__ import annotations

import datetime
import zoneinfo
from pathlib import Path

import pytest
from tos_runtime.calendar.config import (
    CalendarConfigError,
    calendar_bind_digest,
    load_calendar_config,
)
from tos_runtime.calendar.phase import (
    maturity_at,
    session_phase_at,
    trading_date_at,
)

KST = zoneinfo.ZoneInfo("Asia/Seoul")
DAY = datetime.date(2026, 12, 3)  # Thursday — fictitious override day
NEXT = datetime.date(2026, 12, 4)  # Friday — a regular day
EXPIRY = datetime.date(2026, 12, 10)  # second Thursday of December

_BASE = """calendar_version: "t-924"
tz_id: "Asia/Seoul"
closed_phase: "CLOSED"
holidays: ["2026-12-25"]
sessions:
  krx-stock:
    - {phase: PRE_OPEN,   start: "08:30", end: "08:40", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
    - {phase: CONTINUOUS, start: "09:00", end: "15:30", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
  krx-index-futures:
    - {phase: CONTINUOUS, start: "08:45", end: "15:45", days: [MON,TUE,WED,THU,FRI], crosses_midnight: false}
futures_expiry:
  krx-index-futures: {weekday: THU, ordinal: 2, months: [12], expired_phase: EXPIRED}
"""

_OVERRIDE = """session_overrides:
  "2026-12-03":
    reason: "test fixture — fictitious late open"
    sessions:
      krx-stock:
        - {phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}
      krx-index-futures:
        - {phase: CONTINUOUS, start: "09:45", end: "16:45", crosses_midnight: false}
"""


def _write(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "calendar.yaml"
    path.write_text(_BASE + extra, encoding="utf-8")
    return path


def _ms(day: datetime.date, hh: int, mm: int) -> int:
    return int(
        datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=KST).timestamp()
        * 1000
    )


@pytest.fixture
def cfg(tmp_path):
    return load_calendar_config(_write(tmp_path, _OVERRIDE))


def test_override_day_opens_and_closes_late_per_market(cfg) -> None:
    # stock: 09:30 is closed (would have been CONTINUOUS), 10:00 opens, 16:29 still open
    at_0930 = session_phase_at(_ms(DAY, 9, 30), "krx-stock", cfg)
    assert (at_0930.phase, at_0930.is_open) == ("CLOSED", False)
    assert at_0930.boundary_unix_ms == _ms(DAY, 10, 0)
    assert session_phase_at(_ms(DAY, 10, 0), "krx-stock", cfg).phase == "CONTINUOUS"
    late = session_phase_at(_ms(DAY, 16, 29), "krx-stock", cfg)
    assert late.is_open and late.boundary_unix_ms == _ms(DAY, 16, 30)
    assert session_phase_at(_ms(DAY, 16, 30), "krx-stock", cfg).is_open is False
    # futures shift differently: 09:45-16:45
    assert session_phase_at(_ms(DAY, 9, 0), "krx-index-futures", cfg).is_open is False
    assert session_phase_at(_ms(DAY, 9, 45), "krx-index-futures", cfg).is_open is True
    assert session_phase_at(_ms(DAY, 16, 44), "krx-index-futures", cfg).is_open is True
    assert trading_date_at(_ms(DAY, 16, 0), "krx-index-futures", cfg) == "20261203"


def test_override_replaces_the_whole_class_list(cfg) -> None:
    """The stock PRE_OPEN window is not in the override list, so it is gone that day."""
    assert session_phase_at(_ms(DAY, 8, 35), "krx-stock", cfg).is_open is False


def test_regular_days_are_unchanged(cfg, tmp_path) -> None:
    (tmp_path / "plain").mkdir()
    plain = load_calendar_config(_write(tmp_path / "plain"))
    for hh, mm in ((8, 35), (8, 45), (9, 0), (15, 29), (15, 30), (15, 44), (15, 45)):
        for cls in ("krx-stock", "krx-index-futures"):
            assert session_phase_at(_ms(NEXT, hh, mm), cls, cfg) == session_phase_at(
                _ms(NEXT, hh, mm), cls, plain
            )


def test_closed_boundary_before_the_override_day_points_at_the_late_open(cfg) -> None:
    eve = session_phase_at(
        _ms(DAY - datetime.timedelta(days=1), 20, 0), "krx-stock", cfg
    )
    assert eve.boundary_unix_ms == _ms(DAY, 10, 0)


def test_expiry_on_an_override_day_flips_at_the_shifted_close(tmp_path) -> None:
    text = _OVERRIDE.replace("2026-12-03", "2026-12-10")
    cfg = load_calendar_config(_write(tmp_path, text))
    assert maturity_at(_ms(EXPIRY, 16, 0), "krx-index-futures", cfg).expired is False
    assert maturity_at(_ms(EXPIRY, 16, 45), "krx-index-futures", cfg).expired is True


def test_windows_on_falls_back_to_regular(cfg) -> None:
    assert cfg.windows_on(NEXT, "krx-stock") == cfg.sessions["krx-stock"]
    assert cfg.windows_on(DAY, "krx-stock")[0].start == datetime.time(10, 0)
    assert cfg.windows_on(DAY, "unknown") == ()


def test_absent_or_empty_key_is_no_overrides_and_keeps_the_digest(tmp_path) -> None:
    absent = load_calendar_config(_write(tmp_path))
    empty = load_calendar_config(_write(tmp_path, "session_overrides: {}\n"))
    assert absent.session_overrides == {} and empty.session_overrides == {}
    assert calendar_bind_digest(absent) == calendar_bind_digest(empty)


def test_an_override_changes_the_digest(tmp_path, cfg) -> None:
    (tmp_path / "plain").mkdir()
    plain = load_calendar_config(_write(tmp_path / "plain"))
    assert calendar_bind_digest(cfg) != calendar_bind_digest(plain)


def test_shipped_tenant_calendars_load_with_no_dated_overrides() -> None:
    """The four shipped trees carry ``session_overrides: {}`` until KRX publishes a notice."""
    root = Path(__file__).resolve().parents[4] / "config" / "tos_runtime"
    for tree in (
        "paper",
        "cp3-setup-d-long",
        "cp3-setup-d-short",
        "cp3-setup-d-stock-005930",
    ):
        loaded = load_calendar_config(root / tree / "calendar.yaml")
        assert loaded.session_overrides == {}, tree


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("session_overrides: null\n", "must be a mapping"),
        (
            'session_overrides:\n  "2026-13-01": {reason: x, sessions: {}}\n',
            "not a valid",
        ),
        (
            'session_overrides:\n  "2026-12-25":\n    reason: x\n    sessions:\n'
            '      krx-stock: [{phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}]\n',
            "also listed in 'holidays'",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    sessions:\n'
            '      krx-stock: [{phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}]\n',
            "reason",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n'
            '      krx-bond: [{phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}]\n',
            "regular 'sessions' do not declare",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n      krx-stock: []\n',
            "non-empty list",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n'
            '      krx-stock: [{phase: CONTINUOUS, start: "10:00", end: "16:30", days: [THU], crosses_midnight: false}]\n',
            "carries 'days'",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n'
            '      krx-stock: [{phase: CONTINUOUS, start: "18:00", end: "05:00", crosses_midnight: true}]\n',
            "crosses midnight",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n'
            '      krx-stock: [{phase: AUCTION, start: "10:00", end: "16:30", crosses_midnight: false}]\n',
            "is not one the",
        ),
        (
            'session_overrides:\n  "2026-12-03":\n    reason: x\n    sessions:\n'
            "      krx-stock:\n"
            '        - {phase: CONTINUOUS, start: "10:00", end: "16:30", crosses_midnight: false}\n'
            '        - {phase: PRE_OPEN, start: "16:00", end: "16:40", crosses_midnight: false}\n',
            "overlapping",
        ),
    ],
)
def test_malformed_overrides_refuse(tmp_path, text: str, match: str) -> None:
    with pytest.raises(CalendarConfigError, match=match):
        load_calendar_config(_write(tmp_path, text))
