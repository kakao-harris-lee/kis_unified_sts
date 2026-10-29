"""#924 — the legacy-side reader of dated session overrides (tools/tos_cp3/session_day.py).

One reader for the producer, the band launch, the runner's first-row bound and the cron
wrapper's stop time. The override date (2026-12-03) is FICTITIOUS — tests only.
The runtime's own loader of the same key is pinned in
``tos/runtime/tests/calendar/test_session_overrides.py``.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from tools.tos_cp3 import session_day
from tools.tos_cp3.live_producer import band_line
from tools.tos_cp3.live_producer.calendar import load_runtime_calendar
from tools.tos_cp3.live_producer.config import LiveProducerRefused

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIPPED = _REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml"
DAY = date(2026, 12, 3)
REGULAR = date(2026, 12, 4)


def _calendar(tmp_path: Path, overrides: dict | None = None) -> Path:
    data = yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))
    data["session_overrides"] = (
        {
            DAY.isoformat(): {
                "reason": "test fixture — fictitious late open",
                "sessions": {
                    "krx-index-futures": [
                        {
                            "phase": "CONTINUOUS",
                            "start": "09:45",
                            "end": "16:45",
                            "crosses_midnight": False,
                        }
                    ],
                },
            }
        }
        if overrides is None
        else overrides
    )
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _producer_config(tmp_path: Path, calendar: Path) -> Path:
    path = tmp_path / "producer.yaml"
    path.write_text(
        f"calendar_yaml: {calendar}\n"
        "calendar_session_id: krx-index-futures\n"
        "calendar_session_phase: CONTINUOUS\n",
        encoding="utf-8",
    )
    return path


def test_override_day_window_and_regular_fallback(tmp_path: Path) -> None:
    session = session_day.load_producer_session(
        _producer_config(tmp_path, _calendar(tmp_path)), repo_root=_REPO_ROOT
    )
    late = session.window(DAY)
    assert (late.start.isoformat(), late.end.isoformat(), late.overridden) == (
        "09:45:00",
        "16:45:00",
        True,
    )
    regular = session.window(REGULAR)
    assert (regular.start.isoformat(), regular.end.isoformat(), regular.overridden) == (
        "08:45:00",
        "15:45:00",
        False,
    )
    assert session.window(None) == regular
    assert session.open_delay_s(DAY) == 3600
    assert session.open_delay_s(REGULAR) == 0
    assert session.stop_at(DAY, after_close_min=5) == "16:50"
    assert session.stop_at(REGULAR, after_close_min=5) == "15:50"


def test_the_shipped_calendar_has_no_dated_overrides() -> None:
    session = session_day.load_producer_session(
        _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml", repo_root=_REPO_ROOT
    )
    assert session.calendar["session_overrides"] == {}
    assert session.stop_at(REGULAR, after_close_min=5) == "15:50"


def test_band_open_follows_the_override(tmp_path: Path) -> None:
    config = _producer_config(tmp_path, _calendar(tmp_path))
    open_ms, stamp = band_line.session_open_ms(config, repo_root=_REPO_ROOT, day=DAY)
    assert stamp == "20261203"
    assert open_ms == int(
        datetime(2026, 12, 3, 9, 45, tzinfo=band_line.KST).timestamp() * 1000
    )


def test_producer_calendar_window_by_day(tmp_path: Path) -> None:
    cal = load_runtime_calendar(_calendar(tmp_path), covered_years=[2026])
    assert (
        cal.window("krx-index-futures", "CONTINUOUS", DAY).end.isoformat() == "16:45:00"
    )
    assert (
        cal.window("krx-index-futures", "CONTINUOUS", REGULAR).end.isoformat()
        == "15:45:00"
    )
    assert cal.window("krx-index-futures", "CONTINUOUS").start.isoformat() == "08:45:00"


@pytest.mark.parametrize(
    "overrides",
    [
        {DAY.isoformat(): {"reason": "x"}},  # no sessions mapping
        {DAY.isoformat(): {"reason": "x", "sessions": {"krx-index-futures": []}}},
        {
            DAY.isoformat(): {
                "reason": "x",
                "sessions": {
                    "krx-index-futures": [
                        {"phase": "CONTINUOUS", "start": "9h", "end": "16:45"}
                    ]
                },
            }
        },
        {"2026-12-25": {"reason": "x", "sessions": {}}},  # also a holiday
    ],
)
def test_producer_calendar_refuses_a_malformed_override_at_load(
    tmp_path: Path, overrides: dict
) -> None:
    with pytest.raises(LiveProducerRefused):
        load_runtime_calendar(_calendar(tmp_path, overrides), covered_years=[2026])


def test_cli_prints_one_value(tmp_path: Path) -> None:
    config = _producer_config(tmp_path, _calendar(tmp_path))

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-P",
                "-m",
                "tools.tos_cp3.session_day",
                *args,
                "--producer-config",
                str(config),
                "--repo-root",
                str(_REPO_ROOT),
            ],
            cwd=tmp_path,
            env={"PYTHONPATH": str(_REPO_ROOT)},
            capture_output=True,
            text=True,
            check=False,
        )

    assert (
        run("stop-at", "--date", "2026-12-03", "--after-close-min", "5").stdout
        == "16:50\n"
    )
    assert run("open-delay", "--date", "2026-12-03").stdout == "3600\n"
    assert run("open-delay", "--date", "2026-12-04").stdout == "0\n"
    shown = run("show", "--date", "2026-12-03").stdout
    assert (
        shown.strip() == "krx-index-futures CONTINUOUS 2026-12-03 09:45-16:45 OVERRIDE"
    )
    bad = run("stop-at", "--date", "2026-12-03")
    assert bad.returncode == 2 and "after-close-min" in bad.stderr


def _raw_calendar(tmp_path: Path, overrides_yaml: str) -> Path:
    base = _SHIPPED.read_text(encoding="utf-8").replace("session_overrides: {}\n", "")
    path = tmp_path / "calendar.yaml"
    path.write_text(base + overrides_yaml, encoding="utf-8")
    return path


_WIN = '[{phase: CONTINUOUS, start: "%s", end: "%s", crosses_midnight: false}]'


@pytest.mark.parametrize("second_key", ["2026-12-03", '"2026-12-03"'])
def test_a_repeated_override_date_is_refused_by_both_tools_loaders(
    tmp_path: Path, second_key: str
) -> None:
    """Review #963 MEDIUM, the exact input: a quoted and an unquoted (or a repeated)
    key for one date. The runtime refuses it too (test_session_overrides.py)."""
    calendar = _raw_calendar(
        tmp_path,
        "session_overrides:\n"
        '  "2026-12-03":\n    reason: a\n    sessions:\n      krx-index-futures: '
        + _WIN % ("09:45", "16:45")
        + f"\n  {second_key}:\n    reason: b\n    sessions:\n      krx-index-futures: "
        + _WIN % ("10:45", "17:45")
        + "\n",
    )
    with pytest.raises(LiveProducerRefused, match="repeats date"):
        load_runtime_calendar(calendar, covered_years=[2026])
    with pytest.raises(session_day.SessionDayError, match="repeats date"):
        session_day.load_producer_session(
            _producer_config(tmp_path, calendar), repo_root=_REPO_ROOT
        )


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (
            "    sessions:\n      krx-index-futures: " + _WIN % ("09:45", "16:45"),
            "reason",
        ),
        (
            "    reason: x\n    sessions:\n      krx-bond: "
            + _WIN % ("09:45", "16:45"),
            "do not declare",
        ),
        (
            "    reason: x\n    sessions:\n      krx-index-futures: "
            '[{phase: AUCTION, start: "09:45", end: "16:45", crosses_midnight: false}]',
            "not one of",
        ),
        (
            "    reason: x\n    sessions:\n      krx-index-futures: "
            '[{phase: CONTINUOUS, start: "09:45", end: "16:45", days: [THU], crosses_midnight: false}]',
            "days",
        ),
        (
            "    reason: x\n    sessions:\n      krx-index-futures: "
            '[{phase: CONTINUOUS, start: "18:00", end: "05:00", crosses_midnight: true}]',
            "crosses_midnight",
        ),
    ],
)
def test_tools_refuses_what_the_runtime_refuses(
    tmp_path: Path, body: str, match: str
) -> None:
    calendar = _raw_calendar(
        tmp_path, '"session_overrides":\n  "2026-12-03":\n' + body + "\n"
    )
    with pytest.raises(session_day.SessionDayError, match=match):
        session_day.load_producer_session(
            _producer_config(tmp_path, calendar), repo_root=_REPO_ROOT
        )
    with pytest.raises(LiveProducerRefused, match=match):
        load_runtime_calendar(calendar, covered_years=[2026])


# --- holidays (review-1003 MEDIUM) -------------------------------------------------


def test_a_datetime_holiday_entry_is_refused_by_both_readers(tmp_path: Path) -> None:
    """review-1003 MEDIUM, the exact input: an unquoted ``2026-01-01 00:00:00``.

    YAML loads that as a ``datetime``, which **is** a ``date`` subclass — so an
    ``isinstance(entry, date)`` pass keeps it, and ``date(2026, 1, 1) not in
    holidays`` is then True because a ``date`` never equals a ``datetime``. The
    declared closed day silently becomes a trading day in BOTH readers: the
    producer would walk a seed day the exchange was shut on, and the streak would
    expect a session that cannot exist. It is refused instead, naming the entry.
    """
    calendar = _raw_calendar(tmp_path, "session_overrides: {}\n")
    text = calendar.read_text(encoding="utf-8").replace(
        '  - "2026-01-01"', "  - 2026-01-01 00:00:00"
    )
    calendar.write_text(text, encoding="utf-8")
    loaded = yaml.safe_load(text)["holidays"][0]
    assert isinstance(loaded, datetime)  # the input this test is about

    with pytest.raises(session_day.SessionDayError, match="2026-01-01 00:00:00"):
        session_day.holidays_of({"holidays": [loaded]})
    with pytest.raises(LiveProducerRefused, match="2026-01-01 00:00:00"):
        load_runtime_calendar(calendar, covered_years=[2026])


def test_a_plain_date_holiday_entry_is_still_accepted() -> None:
    # YAML's own unquoted date form (`- 2026-01-01`) loads as a `date` and stays.
    holidays = session_day.holidays_of({"holidays": [date(2026, 1, 1), "2026-03-01"]})
    assert holidays == frozenset({date(2026, 1, 1), date(2026, 3, 1)})
    assert session_day.is_trading_day(date(2026, 1, 1), holidays) is False
