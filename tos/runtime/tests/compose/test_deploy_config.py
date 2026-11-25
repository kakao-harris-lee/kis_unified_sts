"""Compose e2e test for the REAL deployed calendar config"""

from __future__ import annotations

import zoneinfo
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar.config import CalendarConfigError
from tos_runtime.calendar.ports import FixedWallClockReference

from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_CALENDAR_PATH = _REPO_ROOT / "config" / "tos_runtime" / "paper" / "calendar.yaml"

_KST = zoneinfo.ZoneInfo("Asia/Seoul")

_CALENDAR_VERSION = "krx-2026.11"


def _kst_unix_ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """Unix ms for a naive KST wall-clock instant -- computed via"""
    return int(datetime(year, month, day, hour, minute, tzinfo=_KST).timestamp() * 1000)


def _install_real_calendar(config_dir: Path) -> str:
    """Copy the REAL deploy file's bytes (verbatim -- header comment and"""
    real_text = _REAL_CALENDAR_PATH.read_text(encoding="utf-8")
    (config_dir / "calendar.yaml").write_text(real_text, encoding="utf-8")

    time_path = config_dir / "time.yaml"
    time_cfg = yaml.safe_load(time_path.read_text(encoding="utf-8"))
    time_cfg["trading_calendar_version"] = _CALENDAR_VERSION
    time_path.write_text(yaml.safe_dump(time_cfg, sort_keys=False), encoding="utf-8")
    return real_text


def _install_mutated_calendar(config_dir: Path, *, null_key: str) -> None:
    """Same real values, but with ``null_key`` flipped to ``null`` -- for the"""
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
    """The deploy file must cite its approval source (plan §11 decision 11)"""
    text = _REAL_CALENDAR_PATH.read_text(encoding="utf-8")
    assert "§11 결정 11" in text
    assert f'calendar_version: "{_CALENDAR_VERSION}"' in text
    assert "운영자 2026-09-24" in text


def test_regular_session_instant_is_continuous_for_both_classes(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Monday 2026-09-07 10:00 KST (before the Sept-10 expiry day, so no"""
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
    """15:35 KST, same Monday (2026-09-07) -- stock's ``CONTINUOUS`` window"""
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
    """15:50 KST, same Monday (2026-09-07) -- stock's ``AFTER_HOURS`` window"""
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
    """2026-08-17 (대체휴일, a Monday) 10:00 KST -- a listed holiday, so both"""
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
    """2026-09-10 (the second Thursday of September -- the configured"""
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


@pytest.mark.parametrize(
    ("month", "day", "next_expiry"),
    [
        (9, 11, date(2026, 10, 8)),
        (9, 28, date(2026, 10, 8)),
        (9, 30, date(2026, 10, 8)),
        (10, 1, date(2026, 10, 8)),
        (12, 11, date(2027, 1, 14)),
    ],
)
def test_real_calendar_after_expiry_is_regular_phase_not_expired(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    month: int,
    day: int,
    next_expiry: date,
) -> None:
    """The deployed file, at the instants the defect actually broke: a"""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, month, day, 10, 0)),
    )
    _reach_trusted(runtime)
    facts = runtime.session_facts.observe("krx-index-futures")
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CONTINUOUS"
    assert facts.maturity_fact.expired is False
    assert facts.maturity_fact.expiry_date == next_expiry
    assert facts.maturity_fact.expiry_date > date(2026, month, day)

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_real_calendar_mini_october_expiry_day_before_and_after_close(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """2026-10-08 is the second Thursday of October and the expiry of the mini"""
    _install_real_calendar(config_dir)
    for hour, expect_expired, expect_phase in (
        (15, False, "CONTINUOUS"),
        (16, True, "EXPIRED"),
    ):
        runtime = _compose(
            tmp_path / f"h{hour}",
            config_dir,
            data_dir,
            custody_root,
            wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 10, 8, hour, 0)),
        )
        _reach_trusted(runtime)
        facts = runtime.session_facts.observe("krx-index-futures")
        assert facts.maturity_fact.expired is expect_expired, hour
        assert facts.maturity_fact.expiry_date == date(2026, 10, 8), hour
        assert (
            runtime.session_facts.phase_for_step3("krx-index-futures") == expect_phase
        ), hour

        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_real_calendar_day_after_mini_october_expiry_rolls_to_november(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The day after the October expiry rolls to 2026-11-12 (November's second"""
    _install_real_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 10, 9, 10, 0)),
    )
    _reach_trusted(runtime)
    facts = runtime.session_facts.observe("krx-index-futures")
    assert facts.maturity_fact.expired is False
    assert facts.maturity_fact.expiry_date == date(2026, 11, 12)
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CLOSED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_real_calendar_declares_every_month_a_rule_month(
    config_dir: Path,
) -> None:
    """The deployed value itself (operator revision 2026-09-24): the mini lists"""
    text = _REAL_CALENDAR_PATH.read_text(encoding="utf-8")
    rule = yaml.safe_load(text)["futures_expiry"]["krx-index-futures"]
    assert sorted(rule["months"]) == list(range(1, 13))
    assert rule["weekday"] == "THU"
    assert rule["ordinal"] == 2
    assert rule["expired_phase"] == "EXPIRED"


def test_real_calendar_with_null_tz_id_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation lens M6: the real values with exactly ONE required scalar"""
    _install_mutated_calendar(config_dir, null_key="tz_id")

    with pytest.raises(CalendarConfigError):
        _compose(tmp_path, config_dir, data_dir, custody_root)
