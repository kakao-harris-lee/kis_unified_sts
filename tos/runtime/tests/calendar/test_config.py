"""tos_runtime.calendar.config — loader refusals, digest stability/sensitivity.

Hermetic (D1.4): every case writes its own YAML under tmp_path; no network,
no ambient env.
"""

from __future__ import annotations

import datetime

import pytest
from tos_runtime.calendar.config import (
    CalendarConfigError,
    calendar_bind_digest,
    load_calendar_config,
)

from .conftest import FUTURES_CLASS, write_fixture_calendar


def test_fixture_holiday_is_actually_a_thursday() -> None:
    """Self-check on the fixture's own claim (never trust a hand-authored
    comment) — 2026-01-01 must really be a weekday for the
    holiday-overrides-weekday scenarios in test_phase.py to mean anything."""
    assert datetime.date(2026, 1, 1).weekday() == 3  # Thursday


def test_loads_valid_fixture_calendar(fixture_calendar) -> None:
    assert fixture_calendar.calendar_version == "w5-fixture-v1"
    assert fixture_calendar.tz_id == "Asia/Seoul"
    assert fixture_calendar.closed_phase == "CLOSED"
    assert datetime.date(2026, 1, 1) in fixture_calendar.holidays
    assert FUTURES_CLASS in fixture_calendar.sessions
    assert FUTURES_CLASS in fixture_calendar.futures_expiry


def test_missing_file_refuses(tmp_path) -> None:
    with pytest.raises(CalendarConfigError, match="not found"):
        load_calendar_config(tmp_path / "does-not-exist.yaml")


def test_not_a_mapping_refuses(tmp_path) -> None:
    path = tmp_path / "calendar.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(CalendarConfigError, match="top-level mapping"):
        load_calendar_config(path)


def test_not_valid_yaml_refuses(tmp_path) -> None:
    path = tmp_path / "calendar.yaml"
    path.write_text("key: [unterminated\n", encoding="utf-8")
    with pytest.raises(CalendarConfigError, match="not valid YAML"):
        load_calendar_config(path)


@pytest.mark.parametrize(
    "key",
    [
        "calendar_version",
        "tz_id",
        "closed_phase",
        "holidays",
        "sessions",
        "futures_expiry",
    ],
)
def test_missing_required_key_refuses(tmp_path, key: str) -> None:
    lines = [
        line
        for line in [
            'calendar_version: "v1"',
            'tz_id: "Asia/Seoul"',
            'closed_phase: "CLOSED"',
            "holidays: []",
            "sessions: {}",
            "futures_expiry: {}",
        ]
        if not line.startswith(key + ":")
    ]
    path = write_fixture_calendar(tmp_path, text="\n".join(lines) + "\n")
    with pytest.raises(CalendarConfigError, match=key):
        load_calendar_config(path)


@pytest.mark.parametrize("key", ["calendar_version", "tz_id", "closed_phase"])
def test_null_required_scalar_refuses(tmp_path, key: str) -> None:
    base = {
        "calendar_version": '"v1"',
        "tz_id": '"Asia/Seoul"',
        "closed_phase": '"CLOSED"',
    }
    base[key] = "null"
    lines = [f"{k}: {v}" for k, v in base.items()] + [
        "holidays: []",
        "sessions: {}",
        "futures_expiry: {}",
    ]
    path = write_fixture_calendar(tmp_path, text="\n".join(lines) + "\n")
    with pytest.raises(CalendarConfigError, match="null"):
        load_calendar_config(path)


def test_null_holidays_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: null\n"
        "sessions: {}\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="holidays"):
        load_calendar_config(path)


def test_null_sessions_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions: null\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="sessions"):
        load_calendar_config(path)


def test_explicit_empty_holidays_and_sessions_are_accepted(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions: {}\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    cfg = load_calendar_config(path)
    assert cfg.holidays == frozenset()
    assert cfg.sessions == {}
    assert cfg.futures_expiry == {}


def test_unresolvable_tz_id_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Not/AZone"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions: {}\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="tzdata"):
        load_calendar_config(path)


def test_bad_time_format_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  stock:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "9:00"\n'  # missing leading zero — not valid HH:MM
        '      end: "15:30"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="not a valid 'HH:MM' time"):
        load_calendar_config(path)


def test_crosses_midnight_true_with_end_after_start_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  futures:\n"
        '    - phase: "NIGHT"\n'
        '      start: "09:00"\n'
        '      end: "16:00"\n'  # end AFTER start but crosses_midnight=true
        "      days: [MON]\n"
        "      crosses_midnight: true\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="crosses_midnight=true"):
        load_calendar_config(path)


def test_crosses_midnight_false_with_end_before_start_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  stock:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "15:30"\n'
        '      end: "09:00"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="crosses_midnight=false"):
        load_calendar_config(path)


def test_overlapping_windows_same_class_same_day_refuses(tmp_path) -> None:
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  stock:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "09:00"\n'
        '      end: "15:30"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        '    - phase: "AFTER_HOURS"\n'
        '      start: "15:00"\n'  # overlaps the first window's 09:00-15:30
        '      end: "16:00"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="overlapping"):
        load_calendar_config(path)


def test_adjacent_non_overlapping_windows_are_accepted(tmp_path) -> None:
    """Back-to-back windows (one ends exactly when the next starts) must NOT
    be flagged as overlapping — half-open interval semantics."""
    text = (
        'calendar_version: "v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  stock:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "09:00"\n'
        '      end: "15:30"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        '    - phase: "AFTER_HOURS"\n'
        '      start: "15:30"\n'
        '      end: "16:00"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    cfg = load_calendar_config(path)
    assert len(cfg.sessions["stock"]) == 2


def test_nightly_crossing_window_every_weekday_does_not_self_overlap(
    fixture_calendar,
) -> None:
    """The fixture's own NIGHT window (23:00->05:00, every weekday) spills
    into the following day's early morning — this must load without an
    overlap refusal against its own morning segment."""
    assert any(w.phase == "NIGHT" for w in fixture_calendar.sessions[FUTURES_CLASS])


def test_digest_stable_for_identical_content(tmp_path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    path_a = write_fixture_calendar(dir_a)
    path_b = write_fixture_calendar(dir_b)
    cfg_a = load_calendar_config(path_a)
    cfg_b = load_calendar_config(path_b)
    assert calendar_bind_digest(cfg_a) == calendar_bind_digest(cfg_b)


def test_digest_sensitive_to_content_change(tmp_path, fixture_calendar) -> None:
    base_digest = calendar_bind_digest(fixture_calendar)
    changed_text = (
        'calendar_version: "w5-fixture-v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        'holidays: ["2026-01-02"]\n'  # different holiday than the fixture
        "sessions: {}\n"
        "futures_expiry: {}\n"
    )
    changed_path = write_fixture_calendar(tmp_path, text=changed_text)
    changed_cfg = load_calendar_config(changed_path)
    assert calendar_bind_digest(changed_cfg) != base_digest
