"""Compose e2e test for the REAL deployed calendar config
(``config/tos_runtime/paper/calendar.yaml`` -- Phase 5 plan §11 decision 11 /
``docs/plans/2026-09-12-tos-operator-value-proposals.md`` §7, adopted; wired
by ``docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md`` §2
decision 6).

This is the ONE file this repo's compose e2e suite reads from OUTSIDE
``tmp_path`` (a read, never a write -- the hermetic write guard in
``tos/runtime/tests/conftest.py`` only confines WRITE-mode targets, so a
plain ``read_text`` on the repo path is unrestricted). Every other compose
e2e test in this directory writes a picked/fixture calendar; this file
proves the file an operator actually deploys boots and produces the right
session/maturity facts at real KST instants -- not a stand-in shaped like it.

Boundary rule (confirmed against
:func:`tos_runtime.calendar.phase._active_window_at`): a session window is
active on ``[start, end)`` -- start inclusive, end EXCLUSIVE. So the krx-
index-futures ``CONTINUOUS`` window (08:45-15:45) is no longer active AT
exactly 15:45, and the krx-stock ``AFTER_HOURS`` window (15:40-16:00) is no
longer active AT exactly 16:00.
"""

from __future__ import annotations

import zoneinfo
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar.config import CalendarConfigError
from tos_runtime.calendar.ports import FixedWallClockReference

from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

# tos/runtime/tests/compose/test_deploy_config.py -> parents[4] is the repo root
# (parents[0]=compose, [1]=tests, [2]=runtime, [3]=tos, [4]=repo root -- same
# depth-from-file arithmetic ``conftest.py``'s own ``_BROKER_SCOPES_EXAMPLE_PATH``
# and ``test_session_wiring.py``'s ``_RUNTIME_ROOT`` already use in this directory).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_CALENDAR_PATH = _REPO_ROOT / "config" / "tos_runtime" / "paper" / "calendar.yaml"

_KST = zoneinfo.ZoneInfo("Asia/Seoul")

#: This deploy file's ``calendar_version`` (must equal the ``config_dir``'s
#: ``time.yaml`` ``trading_calendar_version`` or the owner refuses to boot
#: with ``SessionCalendarMismatch`` -- plan §2 decision 3, mutation M4).
_CALENDAR_VERSION = "krx-2026.09"


def _kst_unix_ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """Unix ms for a naive KST wall-clock instant -- computed via
    ``zoneinfo`` at test time (never a hardcoded literal, team-lead
    instruction), matching the loader's own ``Asia/Seoul`` interpretation."""
    return int(datetime(year, month, day, hour, minute, tzinfo=_KST).timestamp() * 1000)


def _install_real_calendar(config_dir: Path) -> str:
    """Copy the REAL deploy file's bytes (verbatim -- header comment and
    all) into ``config_dir/calendar.yaml``, and align the fixture's
    ``time.yaml`` ``trading_calendar_version`` to match it. Returns the raw
    text so a caller can assert on the header comment."""
    real_text = _REAL_CALENDAR_PATH.read_text(encoding="utf-8")
    (config_dir / "calendar.yaml").write_text(real_text, encoding="utf-8")

    time_path = config_dir / "time.yaml"
    time_cfg = yaml.safe_load(time_path.read_text(encoding="utf-8"))
    time_cfg["trading_calendar_version"] = _CALENDAR_VERSION
    time_path.write_text(yaml.safe_dump(time_cfg, sort_keys=False), encoding="utf-8")
    return real_text


def _install_mutated_calendar(config_dir: Path, *, null_key: str) -> None:
    """Same real values, but with ``null_key`` flipped to ``null`` -- for the
    fail-closed negative (mutation lens M6: a required scalar left
    named-TBD must refuse to boot, never silently default)."""
    mapping = yaml.safe_load(_REAL_CALENDAR_PATH.read_text(encoding="utf-8"))
    assert null_key in mapping and mapping[null_key] is not None
    mapping[null_key] = None
    (config_dir / "calendar.yaml").write_text(
        yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8"
    )

    time_path = config_dir / "time.yaml"
    time_cfg = yaml.safe_load(time_path.read_text(encoding="utf-8"))
    time_cfg["trading_calendar_version"] = _CALENDAR_VERSION
    time_path.write_text(yaml.safe_dump(time_cfg, sort_keys=False), encoding="utf-8")


def test_real_calendar_file_carries_its_approval_provenance() -> None:
    """The deploy file must cite its approval source (plan §11 decision 11)
    -- a value with no provenance header is indistinguishable from an
    unapproved one (README.md's own rule)."""
    text = _REAL_CALENDAR_PATH.read_text(encoding="utf-8")
    assert "§11 결정 11" in text
    assert "krx-2026.09" in text


def test_regular_session_instant_is_continuous_for_both_classes(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Monday 2026-09-07 10:00 KST (before the Sept-10 expiry day, so no
    expiry override applies) -- inside both classes' regular ``CONTINUOUS``
    windows (09:00-15:30 stock, 08:45-15:45 futures)."""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 10, 0)),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CONTINUOUS"
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CONTINUOUS"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_between_continuous_and_after_hours_is_closed_for_stock(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """15:35 KST, same Monday (2026-09-07) -- stock's ``CONTINUOUS`` window
    ends at 15:30 (end-exclusive) and ``AFTER_HOURS`` does not start until
    15:40, so 15:35 falls in the gap: ``closed_phase``. Futures'
    ``CONTINUOUS`` window (08:45-15:45) is still active at 15:35."""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 15, 35)),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CLOSED"
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CONTINUOUS"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_after_hours_boundary_stock_open_futures_closed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """15:50 KST, same Monday (2026-09-07) -- stock's ``AFTER_HOURS`` window
    (15:40-16:00) is active; futures' ``CONTINUOUS`` window ended at 15:45
    (end-exclusive), so futures has already fallen to ``closed_phase``."""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 15, 50)),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3("krx-stock") == "AFTER_HOURS"
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CLOSED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_substitute_holiday_is_closed_for_both_classes(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """2026-08-17 (대체휴일, a Monday) 10:00 KST -- a listed holiday, so both
    classes are ``closed_phase`` for the whole day regardless of the
    time-of-day window table."""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 8, 17, 10, 0)),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CLOSED"
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CLOSED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_futures_expiry_day_after_close_is_expired_stock_is_not(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """2026-09-10 (the second Thursday of September -- the configured
    ``krx-index-futures`` expiry rule month/ordinal/weekday) 16:00 KST, after
    that class's last regular session window (08:45-15:45) has ended:
    ``maturity_fact.expired`` flips ``True`` and the effective phase becomes
    the rule's ``expired_phase`` (``EXPIRED``). ``krx-stock`` has no expiry
    rule at all (``futures_expiry`` only names ``krx-index-futures``), so it
    is judged purely by its own session windows -- at 16:00 its
    ``AFTER_HOURS`` window (15:40-16:00) has also just ended (end-exclusive),
    so it is ``closed_phase``, never ``EXPIRED``."""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 10, 16, 0)),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "EXPIRED"
    assert (
        runtime.session_facts.observe("krx-index-futures").maturity_fact.expired is True
    )
    assert runtime.session_facts.phase_for_step3("krx-stock") != "EXPIRED"
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CLOSED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_real_calendar_with_null_tz_id_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation lens M6: the real values with exactly ONE required scalar
    (``tz_id``) flipped to ``null`` (named-TBD) must refuse to boot with
    :class:`~tos_runtime.calendar.config.CalendarConfigError`, never fall
    back to a silent default timezone."""
    _install_mutated_calendar(config_dir, null_key="tz_id")

    with pytest.raises(CalendarConfigError):
        _compose(tmp_path, config_dir, data_dir, custody_root)
