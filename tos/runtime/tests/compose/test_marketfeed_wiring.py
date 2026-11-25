"""Compose end-to-end tests for the TOS tick-source wave"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.egressgw.construction import admitted_price_from_view
from tos.time import SessionContext
from tos_runtime.calendar.ports import AbsentWallClockReference
from tos_runtime.marketfeed.policy import CriticalInputPolicyConfigError
from tos_runtime.marketfeed.ports import RawObservation, TickOutcome
from tos_runtime.marketfeed.scheduler import MultiInstrumentRefused

from ..recovery.test_drill import _mark_handling_started
from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_MAX_AGE_MS = 600_000
_POLL_INTERVAL_MS = 1_000
_JOURNAL_PASS_ALLOWANCE_MS = 100
_SNAPSHOT_AGE_BOUND = 20
_INTERVAL_WIDTH = 10
_DIRECTION = "LONG"
_QUANTITY_BASIS = "RISK"
_UNIT = "contract"


def _as_of_ms() -> int:
    """A real-clock timestamp just before "now" — see ``_MAX_AGE_MS``'s own docstring on why"""
    return int(time.time() * 1000) - 100


def _cip_fields() -> list[dict[str, Any]]:
    """The three fields the band-reversion strategy needs (``close``/``lower_band``/"""
    return [
        {
            "field_key": key,
            "unit": "KRW",
            "scale": "minor",
            "multiplier": "1",
            "sign": "POSITIVE",
            "max_age_ms": _MAX_AGE_MS,
        }
        for key in ("close", "lower_band", "upper_band")
    ]


def _write_critical_input_policy(config_dir: Path) -> None:
    (config_dir / "critical_input_policy.yaml").write_text(
        yaml.safe_dump(
            {
                "policy_id": "cip-tick-source-e2e",
                "policy_version": "v1",
                "policy_generation": 1,
                "issuer_principal_id": "iss-tick-source-e2e",
                "environment": "non-live-test",
                "decision_class": fx.DECISION_CLASS,
                "intended_use": "entry-decision",
                "fields": _cip_fields(),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_marketfeed_config(
    config_dir: Path, *, journal_path: Path, instruments: tuple[str, ...]
) -> None:
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(
            {
                "instruments": list(instruments),
                "instrument_class": fx.INSTRUMENT_CLASS,
                "account": fx.ACCOUNT,
                "direction": _DIRECTION,
                "quantity_basis": _QUANTITY_BASIS,
                "unit": _UNIT,
                "intake_kind": "journal",
                "journal_path": str(journal_path),
                "poll_interval_ms": _POLL_INTERVAL_MS,
                "journal_pass_allowance_ms": _JOURNAL_PASS_ALLOWANCE_MS,
                "time_evaluate_closed_interval_ms": 60_000,
                "snapshot_age_bound": _SNAPSHOT_AGE_BOUND,
                "interval_width": _INTERVAL_WIDTH,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _observation_line(
    *,
    raw_event_id: str,
    as_of_ms: int,
    close: int = fx.CROSSING_CLOSE,
    lower_band: int = fx.LOWER_BAND,
    upper_band: int = fx.UPPER_BAND,
) -> str:
    return json.dumps(
        {
            "raw_event_id": raw_event_id,
            "instrument": fx.INSTRUMENT,
            "as_of_ms": as_of_ms,
            "fields": {
                "close": close,
                "lower_band": lower_band,
                "upper_band": upper_band,
            },
            "source_id": "compose-e2e-journal",
            "received_ms": as_of_ms,
        }
    )


def _write_journal(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def test_tick_once_ticks_with_the_real_resolver_and_the_admitted_price_travels_with_its_digest(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=_as_of_ms())]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    result = runtime.marketfeed.tick_once()

    assert result.outcome is TickOutcome.TICKED
    assert result.queued_until_recovery is False
    assert result.value_view is not None
    assert result.value_view.values

    admitted_price = admitted_price_from_view(
        result.value_view, field_key=fx.PRICE_FIELD_KEY
    )
    assert admitted_price.value == Decimal(fx.CROSSING_CLOSE)
    assert admitted_price.value_payload_digest
    assert admitted_price.snapshot_digest

    assert runtime.construction_stage.construction is not None
    assert runtime.construction_stage.construction.derivation.price == Decimal(
        fx.CROSSING_CLOSE
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


class _RepeatingIntake:
    """A deliberately LENIENT :class:`~tos_runtime.marketfeed.ports.ObservationIntake` double"""

    def __init__(self, observation: RawObservation) -> None:
        self._observation = observation

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> tuple[RawObservation, ...]:
        del instrument, after_as_of_ms
        return (self._observation,)


def test_the_same_as_of_again_is_skipped_not_newer_with_zero_ticks(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    as_of_ms = _as_of_ms()
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=as_of_ms)]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    first = runtime.marketfeed.tick_once()
    assert first.outcome is TickOutcome.TICKED

    lenient_intake = _RepeatingIntake(
        RawObservation(
            raw_event_id="raw-1-resend",
            instrument=fx.INSTRUMENT,
            as_of_ms=as_of_ms,
            fields=(
                ("close", fx.CROSSING_CLOSE),
                ("lower_band", fx.LOWER_BAND),
                ("upper_band", fx.UPPER_BAND),
            ),
            source_id="compose-e2e-journal",
        )
    )
    runtime.marketfeed._intake = lenient_intake

    second = runtime.marketfeed.tick_once()
    assert second.outcome is TickOutcome.SKIPPED_NOT_NEWER
    assert second.queued_until_recovery is False
    assert second.value_view is None

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_session_closed_skips_the_tick(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=_as_of_ms())]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=AbsentWallClockReference(),
    )
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None
    assert runtime.session_facts.session_context(fx.INSTRUMENT_CLASS) is None

    result = runtime.marketfeed.tick_once()
    assert result.outcome is TickOutcome.SKIPPED_SESSION_CLOSED
    assert result.queued_until_recovery is False
    assert result.value_view is None

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_named_tbd_placeholder_instrument_class_refuses_to_load(
    tmp_path: Path, config_dir: Path
) -> None:
    """W-A A-0 round 2: an operator typing the literal placeholder string ``"TBD"``"""
    from tos_runtime.compose._marketfeed_wiring import (
        MarketFeedConfigError,
        load_marketfeed_config,
    )

    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    raw = yaml.safe_load((config_dir / "marketfeed.yaml").read_text())
    raw["instrument_class"] = "TBD"
    (config_dir / "marketfeed.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(MarketFeedConfigError, match="template placeholder"):
        load_marketfeed_config(config_dir / "marketfeed.yaml")


def test_a_multi_instrument_config_refuses_boot(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir,
        journal_path=journal_path,
        instruments=(fx.INSTRUMENT, "NQ"),
    )

    with pytest.raises(MultiInstrumentRefused, match="FORWARD-OBLIGATION-MS1"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_marketfeed_stays_none_when_unconfigured(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """No ``marketfeed.yaml``/``critical_input_policy.yaml`` under ``config_dir`` (the plain"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert runtime.marketfeed is None
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_half_configured_marketfeed_refuses_boot_rather_than_staying_none(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``marketfeed.yaml`` present, ``critical_input_policy.yaml`` ABSENT — a boot REFUSAL, not"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    assert not (config_dir / "critical_input_policy.yaml").exists()

    with pytest.raises(CriticalInputPolicyConfigError, match="not found"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def _kind_count(runtime, kind: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def test_a_held_recovery_barrier_queues_the_tick_instead_of_running_or_dropping_it(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Pins the CONSEQUENCE of the held-runtime branch (scheduler.py's own module docstring),"""
    journal_path = tmp_path / "journal.jsonl"
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime1 = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime1)
    _mark_handling_started(runtime1, fx.crossing_event(seq=1))

    runtime1.rcl_log.close()
    runtime1.evidence_store.close()
    runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)

    assert runtime2.driver is None
    assert runtime2.recovery is not None
    assert runtime2.recovery.ready is False

    assert runtime2.marketfeed is not None

    _write_journal(
        journal_path,
        [_observation_line(raw_event_id="raw-held-1", as_of_ms=_as_of_ms())],
    )
    inbox_count_before = runtime2.inbox.count
    evidence_count_before = _kind_count(runtime2, "MARKETFEED_QUEUED_UNTIL_RECOVERY")

    result = runtime2.marketfeed.tick_once()

    assert result.outcome is TickOutcome.TICKED
    assert result.queued_until_recovery is True
    assert runtime2.inbox.count == inbox_count_before + 1
    assert (
        _kind_count(runtime2, "MARKETFEED_QUEUED_UNTIL_RECOVERY")
        == evidence_count_before + 1
    )

    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


@pytest.mark.parametrize(
    ("context", "expected_evaluations"),
    [
        (None, 5),
        (SessionContext(phase="CONTINUOUS", is_open=True), 5),
        (SessionContext(phase="CLOSED", is_open=False), 1),
    ],
)
def test_time_pacer_backs_off_only_when_the_session_is_known_closed(
    context: SessionContext | None, expected_evaluations: int
) -> None:
    """Mutation: treat a missing session context as closed -> the unknown row evaluates once"""
    from types import SimpleNamespace

    from tos_runtime.compose._marketfeed_wiring import _time_pacer_pass

    evaluations = 0

    def evaluate() -> None:
        nonlocal evaluations
        evaluations += 1

    now = {"ms": 0}
    before_decide = _time_pacer_pass(
        SimpleNamespace(  # type: ignore[arg-type]
            instrument_class="krx-index-futures",
            time_evaluate_closed_interval_ms=60_000,
        ),
        SimpleNamespace(evaluate=evaluate),  # type: ignore[arg-type]
        SimpleNamespace(session_context=lambda _cls: context),  # type: ignore[arg-type]
        SimpleNamespace(now_ms=lambda: now["ms"]),
    )
    for _ in range(5):
        assert before_decide() is True
        now["ms"] += 1_000
    assert evaluations == expected_evaluations
