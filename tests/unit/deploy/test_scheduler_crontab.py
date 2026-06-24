"""Structural guards for ``deploy/scheduler.crontab``.

The scheduler crontab is baked into the app image and run by supercronic
(TZ=Asia/Seoul). These tests are the merge gate for the operator directive that
backfill must run CONTINUOUSLY during off-hours windows and NEVER inside the
live session 09:00–15:30 KST (so it never competes with the live feed).

We parse the standard 5-field cron rows ourselves (no croniter dependency) and
expand the minute/hour fields enough to assert window placement. The crontab is
KST-native, so each row's hours are interpreted directly as KST.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CRONTAB = _REPO_ROOT / "deploy" / "scheduler.crontab"

# Live session backfill must avoid (KST): 09:00 through 15:30 inclusive. The
# operator directive permits 장후 backfill from ~15:40, so hour 15 is allowed only
# for minute >= 40. Hours 9–14 are forbidden outright.
_LIVE_SESSION_HOURS_STRICT = set(range(9, 15))  # 09:00–14:59 — always forbidden
_SESSION_CLOSE_HOUR = 15
_POST_CLOSE_MINUTE = 40  # 장후 backfill allowed from 15:40 KST

# Commands we treat as "bulk backfill" for the off-hours guard. These pull KIS
# market data into parquet in volume and must not contend with the live feed.
#
# NOTE: ``stock-backfill ensure-coverage`` (the #518 on-entry drain) is
# DELIBERATELY excluded — it is a lightweight, idempotent, throttled,
# max_per_cycle-bounded drain of freshly-admitted symbols that MUST run during
# market hours so a newly-admitted universe symbol is deepened the same session.
# It is not a bulk historical pull, so the off-hours guard does not apply to it.
_BACKFILL_MARKERS = (
    "backfill run",
    "stock-backfill run",
    "stock-backfill daily",
)


def _starts_in_live_session(row: CronRow) -> list[str]:
    """Return human-readable start times of ``row`` that fall in 09:00–15:30 KST."""
    bad: list[str] = []
    hours = row.hours()
    minutes = _expand_field(row.minute, 0, 59)
    for h in sorted(hours):
        if h in _LIVE_SESSION_HOURS_STRICT:
            bad.extend(f"{h:02d}:{m:02d}" for m in sorted(minutes))
        elif h == _SESSION_CLOSE_HOUR:
            bad.extend(
                f"{h:02d}:{m:02d}" for m in sorted(minutes) if m < _POST_CLOSE_MINUTE
            )
    return bad


class CronRow:
    """A parsed crontab data row (5 time fields + command)."""

    __slots__ = ("minute", "hour", "dom", "month", "dow", "command", "raw")

    def __init__(self, line: str):
        self.raw = line
        parts = line.split(None, 5)
        self.minute, self.hour, self.dom, self.month, self.dow, self.command = parts

    def hours(self) -> set[int]:
        """Expand the hour field to a concrete set of integer hours (KST)."""
        return _expand_field(self.hour, 0, 23)

    def runs_on_weekday(self) -> bool:
        """True if the day-of-week field includes any Mon–Fri (1–5)."""
        dows = _expand_field(self.dow, 0, 7)
        # cron treats both 0 and 7 as Sunday.
        return bool(dows & {1, 2, 3, 4, 5})


def _expand_field(field: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for token in field.split(","):
        step = 1
        body = token
        if "/" in token:
            body, step_s = token.split("/", 1)
            step = int(step_s)
        if body in ("*", ""):
            start, end = lo, hi
        elif "-" in body:
            start_s, end_s = body.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(body)
        out.update(range(start, end + 1, step))
    return out


def _data_rows() -> list[CronRow]:
    rows: list[CronRow] = []
    for line in _CRONTAB.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rows.append(CronRow(stripped))
    return rows


def _is_backfill(cmd: str) -> bool:
    return any(marker in cmd for marker in _BACKFILL_MARKERS)


def test_crontab_exists_and_parses():
    assert _CRONTAB.is_file(), f"missing {_CRONTAB}"
    rows = _data_rows()
    assert rows, "crontab has no schedulable rows"


def test_no_backfill_job_runs_inside_live_session():
    """Backfill must never *start* inside 09:00–15:30 KST on a weekday.

    The 장후 window opens at 15:40, so a 15:40+ job is allowed; 09:00–15:30 is the
    forbidden live-feed-contention band.
    """
    offenders: list[str] = []
    for row in _data_rows():
        if not _is_backfill(row.command):
            continue
        if not row.runs_on_weekday():
            continue
        bad = _starts_in_live_session(row)
        if bad:
            offenders.append(f"starts {bad}: {row.raw}")
    assert not offenders, (
        "backfill jobs scheduled inside the live session 09:00–15:30 KST "
        "(operator directive: off-hours only):\n  " + "\n  ".join(offenders)
    )


def test_futures_full_backfill_is_scheduled_off_hours():
    """The A01* underlying + 101S6000 continuous (``--futures``) must be scheduled.

    Pre-#518 only ``mini`` ran; the 101S6000 June=0 gap needs the full-futures
    path (``backfill run --futures``) scheduled in off-hours windows.
    """
    futures_rows = [
        r
        for r in _data_rows()
        if "backfill run" in r.command and "--futures" in r.command
    ]
    assert futures_rows, "no `backfill run --futures` (full-futures) job scheduled"
    for row in futures_rows:
        assert not _starts_in_live_session(
            row
        ), f"futures-full backfill inside live session: {row.raw}"
    # Must cover more than one off-hours window (장후/야간/장전) — continuous, not
    # a single daily pass.
    all_hours: set[int] = set()
    for row in futures_rows:
        all_hours |= row.hours()
    pre_market = all_hours & set(range(6, 9))  # 장전
    post_market = all_hours & set(range(16, 19))  # 장후
    overnight = all_hours & (set(range(19, 24)) | set(range(0, 6)))  # 야간
    covered_windows = sum(bool(w) for w in (pre_market, post_market, overnight))
    assert covered_windows >= 2, (
        "futures-full backfill should run continuously across multiple off-hours "
        f"windows; covered hours={sorted(all_hours)}"
    )


def test_stock_topup_scheduled_off_hours():
    """Stock minute + daily off-hours top-up jobs exist and avoid the session."""
    minute_rows = [r for r in _data_rows() if "stock-backfill run" in r.command]
    daily_rows = [r for r in _data_rows() if "stock-backfill daily" in r.command]
    assert minute_rows, "no off-hours `stock-backfill run` (minute top-up) job"
    assert daily_rows, "no off-hours `stock-backfill daily` top-up job"
    for row in minute_rows + daily_rows:
        assert not _starts_in_live_session(
            row
        ), f"stock top-up inside live session: {row.raw}"


def test_night_jobs_avoid_kis_maintenance_window():
    """No backfill starts in the KIS maintenance window (~23:40–00:10 KST)."""
    # We schedule on whole-hour or :NN minutes; the simplest robust guard is that
    # no backfill row starts at hour 23 with minute >= 40, nor at hour 0 minute
    # < 10. Expand minutes for the relevant hours.
    for row in _data_rows():
        if not _is_backfill(row.command):
            continue
        hours = row.hours()
        minutes = _expand_field(row.minute, 0, 59)
        if 23 in hours and any(m >= 40 for m in minutes):
            pytest.fail(f"backfill starts in KIS maintenance window: {row.raw}")
        if 0 in hours and any(m < 10 for m in minutes):
            pytest.fail(f"backfill starts in KIS maintenance window: {row.raw}")


def test_offhours_backfill_rows_are_window_tagged():
    """Every NEW off-hours backfill row carries a `# window:` provenance tag.

    The tag (장전/장후/야간) documents which window each job runs in so operators
    can reason about contention at a glance. We assert each backfill row is
    preceded (within its comment block) by a window marker.
    """
    text = _CRONTAB.read_text()
    # Find the continuous off-hours section and assert it names all three windows.
    assert (
        "장전" in text and "장후" in text and "야간" in text
    ), "scheduler crontab should document the 장전/장후/야간 off-hours windows"
    # The continuous-backfill block header must be present.
    assert re.search(
        r"continuous off-hours backfill", text, re.IGNORECASE
    ), "missing the continuous off-hours backfill section header"
