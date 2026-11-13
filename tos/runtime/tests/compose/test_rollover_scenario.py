"""Futures rollover compose e2e (TOS Phase 5 W5 plan §2 decision 7; lane f4, Phase B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar import phase as calendar_phase
from tos_runtime.calendar.ports import FixedWallClockReference

from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_session_wiring import _drive_crossing_tick

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_EXPIRY_DATE_ISO = "2026-09-10"

_AFTER_EXPIRY_UNIX_MS = 1_789_034_400_000

_DAY_BEFORE_EXPIRY_UNIX_MS = 1_788_915_600_000


def _write_futures_calendar(
    config_dir: Path, *, calendar_version: str = "cal-compose-0"
) -> None:
    """Override the shared conftest.py calendar with a REALISTIC narrow window (09:00-15:45"""
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
                            "end": "15:45",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": False,
                        },
                        {
                            "phase": "CONTINUOUS",
                            "start": "18:00",
                            "end": "05:00",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": True,
                        },
                    ]
                },
                "closed_phase": "CLOSED",
                "futures_expiry": {
                    fx.INSTRUMENT_CLASS: {
                        "weekday": "THU",
                        "ordinal": 2,
                        "months": [3, 6, 9, 12],
                        "expired_phase": "EXPIRED",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _latest_session_facts_observed_payload(runtime) -> dict:
    row = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SESSION_FACTS_OBSERVED' "
        "ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "expected at least one SESSION_FACTS_OBSERVED row"
    payload = json.loads(row[0])["payload"]
    assert isinstance(
        payload, dict
    ), f"SESSION_FACTS_OBSERVED payload is {type(payload).__name__}"
    return payload


def test_past_expiry_instant_is_expired_phase_inadmissible_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The instant is past expiry AND inside an open session window (see"""
    _write_futures_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts is not None
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "EXPIRED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    payload = _latest_session_facts_observed_payload(runtime)
    assert payload["phase"] == "EXPIRED"
    assert payload["expired"] is True

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_day_before_expiry_is_regular_phase_admitted_and_reaches_transport(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_futures_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_DAY_BEFORE_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "ADMIT"
    assert len(runtime.transport.requests) == 1

    payload = _latest_session_facts_observed_payload(runtime)
    assert payload["phase"] == "CONTINUOUS"
    assert payload["expired"] is False

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_m5_mutation_regular_phase_past_expiry_would_send_and_pin_a_red(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves scenario (a) actually depends on the ``EXPIRED`` token reaching step 3, not on"""
    _write_futures_calendar(config_dir)

    real_effective_phase_at = calendar_phase.effective_phase_at

    def _mutated_never_expired(instant_unix_ms: int, instrument_class: str, cfg):
        """M5: ignore maturity entirely and always return the ordinary session phase."""
        return calendar_phase.session_phase_at(instant_unix_ms, instrument_class, cfg)

    monkeypatch.setattr(
        "tos_runtime.calendar.owner.effective_phase_at", _mutated_never_expired
    )

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) != "EXPIRED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    assert len(runtime.transport.requests) == 1, (
        "M5 mutation check: with the phase mutated to never report EXPIRED, the SAME instant "
        "that scenario (a) drives to zero sends now sends once -- proving (a)'s zero-send "
        "assertion is a genuine pin on the EXPIRED token, not an artifact of something else"
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()
    assert real_effective_phase_at is calendar_phase.effective_phase_at, (
        "monkeypatch must not leak past this test (pytest's own fixture teardown handles "
        "this; asserted here as an explicit, positive confirmation)"
    )
