"""tos_runtime.calendar.config — loader refusals, digest stability/sensitivity."""

from __future__ import annotations

import calendar
import datetime

import pytest
from tos_runtime.calendar.config import (
    CalendarConfigError,
    calendar_bind_digest,
    load_calendar_config,
)

from .conftest import FUTURES_CLASS, write_fixture_calendar


def test_fixture_holiday_is_actually_a_thursday() -> None:
    """Self-check on the fixture's own claim (never trust a hand-authored"""
    assert datetime.date(2026, 1, 1).weekday() == 3


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


@pytest.mark.parametrize("key", ["calendar_version", "tz_id", "closed_phase"])
def test_named_tbd_placeholder_required_scalar_refuses(tmp_path, key: str) -> None:
    """W-A A-0 round 2: an operator typing the literal placeholder string ``"TBD"``"""
    base = {
        "calendar_version": '"v1"',
        "tz_id": '"Asia/Seoul"',
        "closed_phase": '"CLOSED"',
    }
    base[key] = '"TBD"'
    lines = [f"{k}: {v}" for k, v in base.items()] + [
        "holidays: []",
        "sessions: {}",
        "futures_expiry: {}",
    ]
    path = write_fixture_calendar(tmp_path, text="\n".join(lines) + "\n")
    with pytest.raises(CalendarConfigError, match="template placeholder"):
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
        '      start: "9:00"\n'
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
        '      end: "16:00"\n'
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
        '      start: "15:00"\n'
        '      end: "16:00"\n'
        "      days: [MON]\n"
        "      crosses_midnight: false\n"
        "futures_expiry: {}\n"
    )
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="overlapping"):
        load_calendar_config(path)


def test_adjacent_non_overlapping_windows_are_accepted(tmp_path) -> None:
    """Back-to-back windows (one ends exactly when the next starts) must NOT"""
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
    """The fixture's own NIGHT window (23:00->05:00, every weekday) spills"""
    assert any(w.phase == "NIGHT" for w in fixture_calendar.sessions[FUTURES_CLASS])


def _calendar_with_ordinal(ordinal: object) -> str:
    """A minimal calendar whose futures class has a regular window (so only"""
    return (
        'calendar_version: "ordinal-v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  futures:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "08:45"\n'
        '      end: "15:45"\n'
        "      days: [MON, TUE, WED, THU, FRI]\n"
        "      crosses_midnight: false\n"
        "futures_expiry:\n"
        "  futures:\n"
        '    weekday: "THU"\n'
        f"    ordinal: {ordinal}\n"
        "    months: [1, 2]\n"
        '    expired_phase: "EXPIRED"\n'
    )


@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_ordinal_one_through_four_is_accepted(tmp_path, ordinal: int) -> None:
    """Every month has at least four of each weekday, so 1..4 always resolves."""
    path = write_fixture_calendar(tmp_path, text=_calendar_with_ordinal(ordinal))
    cfg = load_calendar_config(path)
    assert cfg.futures_expiry["futures"].ordinal == ordinal


@pytest.mark.parametrize("ordinal", [0, 5, 6, -1])
def test_ordinal_outside_one_through_four_refuses(tmp_path, ordinal: int) -> None:
    """``ordinal: 5`` used to load and then raise ``IndexError`` deep inside"""
    path = write_fixture_calendar(tmp_path, text=_calendar_with_ordinal(ordinal))
    with pytest.raises(CalendarConfigError, match="ordinal"):
        load_calendar_config(path)


def test_every_month_has_four_of_each_weekday_but_not_always_five() -> None:
    """The fact the 1..4 bound rests on, computed rather than asserted from a"""
    counts = []
    for year in range(2026, 2031):
        for month in range(1, 13):
            for weekday in range(7):
                days = [
                    day
                    for day in calendar.Calendar().itermonthdates(year, month)
                    if day.month == month and day.weekday() == weekday
                ]
                counts.append(len(days))
    assert min(counts) == 4
    assert max(counts) == 5


_NIGHT_ONLY_FUTURES = (
    'calendar_version: "expiry-reach-v1"\n'
    'tz_id: "Asia/Seoul"\n'
    'closed_phase: "CLOSED"\n'
    "holidays: []\n"
    "sessions:\n"
    "  futures:\n"
    '    - phase: "NIGHT"\n'
    '      start: "18:00"\n'
    '      end: "05:00"\n'
    "      days: [MON, TUE, WED, THU, FRI]\n"
    "      crosses_midnight: true\n"
    "futures_expiry:\n"
    "  futures:\n"
    '    weekday: "THU"\n'
    "    ordinal: 2\n"
    "    months: [3, 6, 9, 12]\n"
    '    expired_phase: "EXPIRED"\n'
)

_NO_WINDOWS_FUTURES = (
    'calendar_version: "expiry-reach-v1"\n'
    'tz_id: "Asia/Seoul"\n'
    'closed_phase: "CLOSED"\n'
    "holidays: []\n"
    "sessions:\n"
    "  futures: []\n"
    "futures_expiry:\n"
    "  futures:\n"
    '    weekday: "THU"\n'
    "    ordinal: 2\n"
    "    months: [3, 6, 9, 12]\n"
    '    expired_phase: "EXPIRED"\n'
)

_CLASS_ABSENT_FROM_SESSIONS = (
    'calendar_version: "expiry-reach-v1"\n'
    'tz_id: "Asia/Seoul"\n'
    'closed_phase: "CLOSED"\n'
    "holidays: []\n"
    "sessions: {}\n"
    "futures_expiry:\n"
    "  futures:\n"
    '    weekday: "THU"\n'
    "    ordinal: 2\n"
    "    months: [3, 6, 9, 12]\n"
    '    expired_phase: "EXPIRED"\n'
)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(_NIGHT_ONLY_FUTURES, id="night-only"),
        pytest.param(_NO_WINDOWS_FUTURES, id="no-windows"),
        pytest.param(_CLASS_ABSENT_FROM_SESSIONS, id="class-absent-from-sessions"),
    ],
)
def test_expiry_rule_without_regular_window_refuses(tmp_path, text: str) -> None:
    """``maturity_at`` flips ``expired`` at the end of the class's last"""
    path = write_fixture_calendar(tmp_path, text=text)
    with pytest.raises(CalendarConfigError, match="no regular"):
        load_calendar_config(path)


def test_expiry_rule_with_regular_window_alongside_night_window_is_accepted(
    tmp_path,
) -> None:
    """The refusal above must be about the ABSENCE of a regular window, not"""
    text = _NIGHT_ONLY_FUTURES.replace(
        "  futures:\n" '    - phase: "NIGHT"\n',
        "  futures:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "08:45"\n'
        '      end: "15:45"\n'
        "      days: [MON, TUE, WED, THU, FRI]\n"
        "      crosses_midnight: false\n"
        '    - phase: "NIGHT"\n',
    )
    cfg = load_calendar_config(write_fixture_calendar(tmp_path, text=text))
    assert "futures" in cfg.futures_expiry
    assert any(not w.crosses_midnight for w in cfg.sessions["futures"])


def _calendar_with_window_days(days: str) -> str:
    """A futures class whose ONE regular window runs on ``days``, under a"""
    return (
        'calendar_version: "weekday-reach-v1"\n'
        'tz_id: "Asia/Seoul"\n'
        'closed_phase: "CLOSED"\n'
        "holidays: []\n"
        "sessions:\n"
        "  futures:\n"
        '    - phase: "CONTINUOUS"\n'
        '      start: "08:45"\n'
        '      end: "15:45"\n'
        f"      days: {days}\n"
        "      crosses_midnight: false\n"
        "futures_expiry:\n"
        "  futures:\n"
        '    weekday: "THU"\n'
        "    ordinal: 2\n"
        "    months: [3, 6, 9, 12]\n"
        '    expired_phase: "EXPIRED"\n'
    )


def test_regular_window_not_running_on_the_rule_weekday_refuses(tmp_path) -> None:
    """review-799 round 2: having *a* non-crossing window is not enough — it"""
    path = write_fixture_calendar(tmp_path, text=_calendar_with_window_days("[MON]"))
    with pytest.raises(CalendarConfigError) as excinfo:
        load_calendar_config(path)
    message = str(excinfo.value)
    assert "futures" in message
    assert "THU" in message
    assert "MON" in message


def test_regular_window_covering_the_rule_weekday_is_accepted(tmp_path) -> None:
    """The mirror of the refusal above: the same rule with a MON..FRI window"""
    text = _calendar_with_window_days("[MON, TUE, WED, THU, FRI]")
    cfg = load_calendar_config(write_fixture_calendar(tmp_path, text=text))
    rule = cfg.futures_expiry["futures"]
    assert rule.weekday == 3
    assert any(
        not window.crosses_midnight and rule.weekday in window.days
        for window in cfg.sessions["futures"]
    )


def test_thursday_only_regular_window_is_enough_for_a_thursday_rule(tmp_path) -> None:
    """A single-day window is fine as long as it IS the rule's weekday — the"""
    cfg = load_calendar_config(
        write_fixture_calendar(tmp_path, text=_calendar_with_window_days("[THU]"))
    )
    assert cfg.futures_expiry["futures"].weekday == 3


def test_no_expiry_rule_means_no_regular_window_requirement(tmp_path) -> None:
    """A class with only a night window and NO expiry rule stays legal — the"""
    text = _NIGHT_ONLY_FUTURES.replace(
        "futures_expiry:\n"
        "  futures:\n"
        '    weekday: "THU"\n'
        "    ordinal: 2\n"
        "    months: [3, 6, 9, 12]\n"
        '    expired_phase: "EXPIRED"\n',
        "futures_expiry: {}\n",
    )
    cfg = load_calendar_config(write_fixture_calendar(tmp_path, text=text))
    assert cfg.futures_expiry == {}
    assert all(w.crosses_midnight for w in cfg.sessions["futures"])


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
        'holidays: ["2026-01-02"]\n'
        "sessions: {}\n"
        "futures_expiry: {}\n"
    )
    changed_path = write_fixture_calendar(tmp_path, text=changed_text)
    changed_cfg = load_calendar_config(changed_path)
    assert calendar_bind_digest(changed_cfg) != base_digest
