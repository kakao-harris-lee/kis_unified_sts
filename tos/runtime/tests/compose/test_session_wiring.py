"""Compose e2e tests for :mod:`tos_runtime.compose._session_wiring` /"""

from __future__ import annotations

import datetime
import json
import re
import zoneinfo
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.model import WallClockReading
from tos_runtime.calendar.owner import SessionCalendarMismatch
from tos_runtime.calendar.phase import session_phase_at
from tos_runtime.calendar.ports import AbsentWallClockReference, FixedWallClockReference
from tos_runtime.compose._session_wiring import RetiredConfigPresent
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime

from . import _fixtures as fx
from .conftest import approve_constructed_intent
from .test_compose_root import (
    _action_flow_inputs_for,
    _aggregate_inputs,
    _compose,
    _LiveRuntimeFacts,
    _reach_trusted,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]
_SRC = _RUNTIME_ROOT / "src"

_MONDAY_2026_09_14_10_00_KST_UNIX_MS = fx.DEFAULT_WALL_CLOCK_UNIX_MS
_MONDAY_2026_09_14_22_00_KST_UNIX_MS = 1_789_390_800_000
_SATURDAY_2026_09_19_10_00_KST_UNIX_MS = 1_789_779_600_000


class _SteppingWallClock:
    """A settable ``WallClockReference`` test double -- the test flips"""

    def __init__(self, unix_ms: int) -> None:
        self.unix_ms = unix_ms

    def read(self) -> WallClockReading:
        return WallClockReading(unix_ms=self.unix_ms, source_label="stepping-test")


def _write_narrow_calendar(
    config_dir: Path, *, calendar_version: str = "cal-compose-0"
) -> None:
    """Override the shared conftest.py calendar with a REALISTIC narrow window"""
    (config_dir / "calendar.yaml").write_text(
        yaml.safe_dump(
            {
                "calendar_version": calendar_version,
                "tz_id": "Asia/Seoul",
                "holidays": [],
                "sessions": {
                    fx.INSTRUMENT_CLASS: [
                        {
                            "phase": "CONTINUOUS",
                            "start": "09:00",
                            "end": "15:30",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": False,
                        }
                    ]
                },
                "closed_phase": "CLOSED",
                "futures_expiry": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _verify_item_payloads(runtime) -> list[dict]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'VERIFY_ITEM' ORDER BY rowid"
    ).fetchall()
    return [json.loads(row[0])["payload"] for row in rows]


def _kind_count(runtime, kind: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def _drive_crossing_tick(runtime, custody_root: Path):
    """Two-``run_once`` admission dance (mirrors every other compose e2e test"""
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=proposal_digest,
    )
    results2 = runtime.run_once((event,))
    return results2[0]


def test_fixed_weekday_admits_step3_and_satisfies_item12(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """``_compose()``'s own default (module docstring in test_compose_root.py)"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.session_facts is not None
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "ADMIT"

    verdicts = _verify_item_payloads(runtime)
    (item12,) = (
        v
        for v in verdicts
        if v["item"] == "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    )
    assert item12["outcome"] == "SATISFIED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_after_hours_instant_denies_step3_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_narrow_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_MONDAY_2026_09_14_22_00_KST_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CLOSED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_weekend_instant_denies_step3_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_narrow_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_SATURDAY_2026_09_19_10_00_KST_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CLOSED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_absent_wall_clock_denies_step3_and_records_absent_once(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=AbsentWallClockReference(),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) is None

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "UNKNOWN"
    assert runtime.transport.requests == ()
    assert _kind_count(runtime, "SESSION_FACTS_SOURCE_ABSENT") == 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_calendar_version_mismatch_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """``time.yaml``'s ``trading_calendar_version`` is ``"cal-compose-0"``"""
    _write_narrow_calendar(config_dir, calendar_version="a-different-calendar-version")
    with pytest.raises(SessionCalendarMismatch):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_leftover_egress_attestations_file_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation M9: a stale ``egress_attestations.yaml`` (retired, plan §2"""
    (config_dir / "egress_attestations.yaml").write_text(
        yaml.safe_dump({"venue_session_account_facts_current": {"attested": True}}),
        encoding="utf-8",
    )
    with pytest.raises(RetiredConfigPresent):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_session_facts_observed_does_not_grow_across_repeated_reads(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    assert _kind_count(runtime, "SESSION_FACTS_OBSERVED") <= 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_session_open_expectation_fields_are_recorded_and_never_consumed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SESSION_FACTS_OBSERVED'"
    ).fetchall()
    assert len(rows) >= 1
    payload = json.loads(rows[0][0])["payload"]
    assert payload["open_expectation_evaluated"] is False

    runtime.rcl_log.close()
    runtime.evidence_store.close()


_OPEN_EXPECTATION_FIELD_MENTION = re.compile(r"open_expectation_evaluated")


def test_no_runtime_module_consumes_open_expectation_fields_for_admission() -> None:
    """Plan §2 decision 3 (b): the open-expectation fields folded into"""
    allowed = {_SRC / "tos_runtime" / "calendar" / "owner.py"}
    offenders = []
    for path in _SRC.rglob("*.py"):
        if path in allowed:
            continue
        if _OPEN_EXPECTATION_FIELD_MENTION.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []


def test_venue_phase_is_re_read_per_attempt_not_captured_at_construction(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Two SEPARATE attempts, the wall clock moved across the window boundary"""
    _write_narrow_calendar(config_dir)
    clock = _SteppingWallClock(_MONDAY_2026_09_14_10_00_KST_UNIX_MS)
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root, wall_clock=clock)
    _reach_trusted(runtime)

    result1 = runtime.run_once((fx.crossing_event(seq=1),))[0]
    assert result1.flow is not None
    verdict_by_step_1 = {v.step.value: v for v in result1.flow.verdicts}
    assert verdict_by_step_1["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "ADMIT"

    clock.unix_ms = _MONDAY_2026_09_14_22_00_KST_UNIX_MS

    result2 = runtime.run_once((fx.crossing_event(seq=2),))[0]
    assert result2.flow is not None
    verdict_by_step_2 = {v.step.value: v for v in result2.flow.verdicts}
    assert verdict_by_step_2["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_production_default_wall_clock_boots_with_real_session_facts(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calls ``compose_paper_runtime`` directly (bypassing this suite's own"""
    fx.pin_system_clock(monkeypatch, fx.LAST_MINUTE_OF_DAY_UNIX_MS)
    fx.write_band_strategy_file(config_dir)
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        transport_kind=TransportKind.SYNTHETIC,
    )
    facts.runtime = runtime
    _reach_trusted(runtime)

    assert runtime.session_facts is not None
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"
    assert _kind_count(runtime, "SESSION_FACTS_SOURCE_ABSENT") == 0
    assert _kind_count(runtime, "TIME_WALL_CLOCK_EXPOSED") == 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_production_default_dates_egress_results_through_a_fresh_trusted_reference(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan 2026-09-26 egress trading date, review finding 1: the session phase may keep reading"""
    from tos_runtime.calendar.ports import FreshTrustedWallClockReference

    fx.pin_system_clock(monkeypatch, fx.LAST_MINUTE_OF_DAY_UNIX_MS)
    fx.write_band_strategy_file(config_dir)
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        transport_kind=TransportKind.SYNTHETIC,
    )
    facts.runtime = runtime
    _reach_trusted(runtime)
    assert runtime.session_facts is not None
    reference = runtime.session_facts._trading_date_wall_clock
    assert isinstance(reference, FreshTrustedWallClockReference)
    assert reference._max_age_ms == 60_000
    date = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
    observed_ms = runtime.time_service.wall_clock_now()
    assert observed_ms is not None
    assert observed_ms >= fx.LAST_MINUTE_OF_DAY_UNIX_MS
    expected = datetime.datetime.fromtimestamp(
        observed_ms / 1000, tz=zoneinfo.ZoneInfo("Asia/Seoul")
    ).strftime("%Y%m%d")
    assert expected in ("20260914", "20260915")
    assert date == expected
    runtime.rcl_log.close()
    runtime.evidence_store.close()


@pytest.mark.parametrize(
    "local_time",
    [
        datetime.time(0, 0, 0, 0),
        datetime.time(10, 0, 0, 0),
        datetime.time(23, 58, 59, 999_000),
        datetime.time(23, 59, 0, 0),
        datetime.time(23, 59, 30, 0),
        datetime.time(23, 59, 59, 999_000),
    ],
)
def test_shared_compose_calendar_admits_every_instant_of_the_day(
    config_dir: Path, local_time: datetime.time
) -> None:
    """``conftest.py``'s ``calendar.yaml`` is deliberately permissive so that every"""
    calendar = load_calendar_config(config_dir / "calendar.yaml")
    instant_local = datetime.datetime.combine(
        datetime.date(2026, 9, 14),
        local_time,
        tzinfo=zoneinfo.ZoneInfo(calendar.tz_id),
    )
    fact = session_phase_at(
        int(instant_local.timestamp() * 1000), fx.INSTRUMENT_CLASS, calendar
    )
    assert (fact.phase, fact.is_open) == (fx.SESSION_PHASE, True)
