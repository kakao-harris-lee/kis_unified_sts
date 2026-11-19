"""Broker-flat release of a held entry reservation (operator decision 2026-11-19, option B)."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState
from tos.workload import RuntimeIdentity
from tos_runtime.posttrade.broker_flat_release import (
    BROKER_FLAT_RELEASE_HELD_KIND,
    BROKER_FLAT_RELEASE_KIND,
    BrokerFlatRelease,
    BrokerFlatVerdict,
    broker_flat_release_command_id,
)
from tos_runtime.posttrade.entry_recovery import pending_recovery_attempt_ids
from tos_runtime.posttrade.fill_fetch import HeldPositionSnapshot
from tos_runtime.posttrade.fill_observer_config import (
    FillObserverConfigError,
    load_fill_observer_config,
)
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.riskstate.held_position import RclTip

from . import test_release_consumer as cycle
from .conftest import Rig

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_TODAY = "20261119"
_START_MS = 1_000_000
_MAX_AGE_MS = 20_000
_SETTLE_MS = 5_000
_CONFIRM_MS = 2_000
_READ_SPAN_MS = 1_000
_ENTRY = "res-flat-entry"


class _Clock:
    def __init__(self) -> None:
        self.ms = _START_MS

    def advance(self, delta_ms: int) -> None:
        self.ms += delta_ms


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


def _flat_read(*positions: tuple[str, Decimal]) -> WitnessSnapshot:
    return WitnessSnapshot(
        observed_at_generation=None,
        orders=(),
        positions=positions,
        positions_complete=True,
        independent_of_evidence_store=True,
    )


def _tip(rcl_log: SqliteCommitLog) -> tuple[int, int | None]:
    epoch = rcl_log.current_epoch()
    assert epoch is not None
    return epoch, rcl_log.read_linearizable(writer_epoch=epoch).last_seq


def _snapshot(
    rcl_log: SqliteCommitLog,
    clock: _Clock,
    *,
    first: object = None,
    confirmation: object = None,
    started_ms: int | None = None,
    tip: tuple[int, int | None] | None = None,
) -> HeldPositionSnapshot:
    """A held double read that STARTED one read span before ``clock`` (now)."""
    started = clock.ms - _READ_SPAN_MS if started_ms is None else started_ms
    return HeldPositionSnapshot(
        scope=WitnessScope(
            account=cycle._ACCOUNT,
            instrument_keys=(
                InstrumentKey(account=cycle._ACCOUNT, instrument=cycle._INSTRUMENT),
            ),
        ),
        today=_TODAY,
        generation=None,
        tip=_tip(rcl_log) if tip is None else tip,
        token=1,
        first=_flat_read() if first is None else first,  # type: ignore[arg-type]
        confirmation=(
            _flat_read() if confirmation is None else confirmation  # type: ignore[arg-type]
        ),
        first_balance_read_started_ms=started,
        confirmation_balance_read_started_ms=started + 500,
        read_finished_ms=started + 900,
    )


def _release(
    rig: Rig,
    clock: _Clock,
    *,
    in_flight: Callable[[], bool] = lambda: False,
    tip_compatible: Callable[[RclTip, RclTip], bool] = lambda _a, _b: False,
) -> BrokerFlatRelease:
    return BrokerFlatRelease(
        rcl_log=rig.rcl_log,
        evidence_store=rig.evidence_store,
        scheme=_SCHEME,
        account=cycle._ACCOUNT,
        instrument=cycle._INSTRUMENT,
        today=lambda: _TODAY,
        now_ms=lambda: clock.ms,
        max_age_ms=_MAX_AGE_MS,
        in_flight=in_flight,
        tip_compatible=tip_compatible,
        settle_ms=_SETTLE_MS,
        confirm_interval_ms=_CONFIRM_MS,
    )


def _confirmed(
    release: BrokerFlatRelease,
    rig: Rig,
    clock: _Clock,
    *,
    tip: tuple[int, int | None] | None = None,
) -> BrokerFlatVerdict:
    """Drive a consumed entry through settle and confirmation; return the third poll's verdict."""
    assert release(_snapshot(rig.rcl_log, clock, tip=tip)) is BrokerFlatVerdict.SETTLING
    clock.advance(_SETTLE_MS + _READ_SPAN_MS)
    assert (
        release(_snapshot(rig.rcl_log, clock, tip=tip))
        is BrokerFlatVerdict.AWAITING_CONFIRMATION
    )
    clock.advance(_CONFIRM_MS)
    return release(_snapshot(rig.rcl_log, clock, tip=tip))


def _consumed_entry(rig: Rig) -> None:
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id=_ENTRY,
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="release-attempt-flat-entry",
    )


def _state(rig: Rig, reservation_id: str = _ENTRY) -> CapacityState | None:
    for row_id, state, _seq, _scope in rig.rcl_log.reservation_rows():
        if row_id == reservation_id:
            return state
    return None


def _rows(rig: Rig, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(raw)["payload"]
        for (raw,) in rig.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq", (kind,)
        )
    ]


def test_a_confirmed_flat_releases_once_with_an_evidence_row(
    rig: Rig, clock: _Clock
) -> None:
    _consumed_entry(rig)
    release = _release(rig, clock)
    assert _confirmed(release, rig, clock) is BrokerFlatVerdict.RELEASED
    assert _state(rig) is CapacityState.RELEASED
    (row,) = _rows(rig, BROKER_FLAT_RELEASE_KIND)
    assert row["reservation_id"] == _ENTRY
    assert row["command_id"] == broker_flat_release_command_id(_ENTRY)
    assert rig.rcl_log.committed_command(broker_flat_release_command_id(_ENTRY))

    clock.advance(_CONFIRM_MS)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.NOT_ELIGIBLE
    assert len(_rows(rig, BROKER_FLAT_RELEASE_KIND)) == 1


def test_flat_reads_right_after_the_fill_release_nothing_until_settled(
    rig: Rig, clock: _Clock
) -> None:
    """review-1114 M1: a balance that has not reflected the entry's buy yet reads flat."""
    _consumed_entry(rig)
    release = _release(rig, clock)
    for _ in range(_SETTLE_MS // _READ_SPAN_MS):
        assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.SETTLING
        clock.advance(_READ_SPAN_MS)
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    assert _rows(rig, BROKER_FLAT_RELEASE_KIND) == []


def test_one_settled_flat_poll_is_not_enough(rig: Rig, clock: _Clock) -> None:
    _consumed_entry(rig)
    release = _release(rig, clock)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.SETTLING
    clock.advance(_SETTLE_MS + _READ_SPAN_MS)
    assert (
        release(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.AWAITING_CONFIRMATION
    )
    clock.advance(_CONFIRM_MS - 1)
    assert (
        release(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.AWAITING_CONFIRMATION
    )
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    clock.advance(1)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.RELEASED


@pytest.mark.parametrize(
    ("first", "confirmation"),
    [
        (WitnessUnavailable("inquire-balance timeout"), None),
        (None, WitnessUnavailable("VTTC8434R HTTP 500")),
        (
            WitnessSnapshot(observed_at_generation=None, orders=(), positions=()),
            None,
        ),
        (_flat_read((cycle._INSTRUMENT, Decimal(1))), None),
    ],
    ids=["first-failed", "confirmation-failed", "incomplete", "held"],
)
def test_a_failed_or_held_read_between_the_two_flat_polls_resets_them(
    rig: Rig, clock: _Clock, first: object, confirmation: object
) -> None:
    _consumed_entry(rig)
    release = _release(rig, clock)
    release(_snapshot(rig.rcl_log, clock))
    clock.advance(_SETTLE_MS + _READ_SPAN_MS)
    assert (
        release(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.AWAITING_CONFIRMATION
    )
    clock.advance(_CONFIRM_MS)
    broken = release(
        _snapshot(rig.rcl_log, clock, first=first, confirmation=confirmation)
    )
    assert broken in (BrokerFlatVerdict.READ_FAILED, BrokerFlatVerdict.NOT_FLAT)
    clock.advance(_CONFIRM_MS)
    assert (
        release(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.AWAITING_CONFIRMATION
    )
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    clock.advance(_CONFIRM_MS)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.RELEASED


@pytest.mark.parametrize(
    ("first", "confirmation"),
    [
        (WitnessUnavailable("inquire-balance timeout"), None),
        (None, WitnessUnavailable("VTTC8434R HTTP 500")),
        (
            WitnessSnapshot(observed_at_generation=None, orders=(), positions=()),
            None,
        ),
    ],
    ids=["first-failed", "confirmation-failed", "incomplete"],
)
def test_a_failed_read_releases_nothing(
    rig: Rig, clock: _Clock, first: object, confirmation: object
) -> None:
    _consumed_entry(rig)
    failed = _snapshot(rig.rcl_log, clock, first=first, confirmation=confirmation)
    assert _release(rig, clock)(failed) is BrokerFlatVerdict.READ_FAILED
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    assert _rows(rig, BROKER_FLAT_RELEASE_KIND) == []


def test_a_missing_confirmation_is_a_failed_read(rig: Rig, clock: _Clock) -> None:
    _consumed_entry(rig)
    snapshot = _snapshot(rig.rcl_log, clock)
    no_confirmation = HeldPositionSnapshot(
        **{**snapshot.__dict__, "confirmation": None}
    )
    assert _release(rig, clock)(no_confirmation) is BrokerFlatVerdict.READ_FAILED
    assert _state(rig) is CapacityState.POSITION_CONSUMED


@pytest.mark.parametrize("which", ["first", "confirmation"])
def test_a_held_share_in_either_read_releases_nothing(
    rig: Rig, clock: _Clock, which: str
) -> None:
    _consumed_entry(rig)
    held = _flat_read((cycle._INSTRUMENT, Decimal(1)))
    snapshot = (
        _snapshot(rig.rcl_log, clock, first=held)
        if which == "first"
        else _snapshot(rig.rcl_log, clock, confirmation=held)
    )
    assert _release(rig, clock)(snapshot) is BrokerFlatVerdict.NOT_FLAT
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_another_symbol_held_does_not_block(rig: Rig, clock: _Clock) -> None:
    _consumed_entry(rig)
    other = _flat_read(("000660", Decimal(3)))
    release = _release(rig, clock)
    for _ in range(2):
        release(_snapshot(rig.rcl_log, clock, first=other, confirmation=other))
        clock.advance(_SETTLE_MS + _READ_SPAN_MS)
    assert (
        release(_snapshot(rig.rcl_log, clock, first=other, confirmation=other))
        is BrokerFlatVerdict.RELEASED
    )


def test_an_in_flight_attempt_releases_nothing(rig: Rig, clock: _Clock) -> None:
    _consumed_entry(rig)
    release = _release(rig, clock, in_flight=lambda: True)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.IN_FLIGHT
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    assert _rows(rig, BROKER_FLAT_RELEASE_KIND) == []


def test_an_in_flight_reader_failure_releases_nothing(rig: Rig, clock: _Clock) -> None:
    _consumed_entry(rig)

    def _boom() -> bool:
        raise RuntimeError("evidence unreadable")

    release = _release(rig, clock, in_flight=_boom)
    assert release(_snapshot(rig.rcl_log, clock)) is BrokerFlatVerdict.IN_FLIGHT
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_an_outstanding_open_or_close_reservation_is_not_eligible(
    rig: Rig, clock: _Clock
) -> None:
    _consumed_entry(rig)
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-flat-close",
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="bind-res-flat-close",
    )
    assert (
        _release(rig, clock)(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.NOT_ELIGIBLE
    )
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_a_scope_with_no_reservation_is_not_eligible(rig: Rig, clock: _Clock) -> None:
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-unbound",
        to_state=CapacityState.ATTEMPT_BOUND,
        command_id="bind-res-unbound",
    )
    assert (
        _release(rig, clock)(_snapshot(rig.rcl_log, clock))
        is BrokerFlatVerdict.NOT_ELIGIBLE
    )


def test_an_rcl_that_moved_since_the_read_was_planned_releases_nothing(
    rig: Rig, clock: _Clock
) -> None:
    _consumed_entry(rig)
    planned = _snapshot(rig.rcl_log, clock)
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-elsewhere",
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="release-attempt-elsewhere",
    )
    assert _release(rig, clock)(planned) is BrokerFlatVerdict.RCL_MOVED
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_an_approval_only_tip_advance_is_admitted(rig: Rig, clock: _Clock) -> None:
    """A moved tip is judged by the bridge's approval-only gap check (stubbed admitting)."""
    rig.rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="relc-test-cell", process_nonce="relc-test-nonce")
    )
    planned_tip = _tip(rig.rcl_log)
    _consumed_entry(rig)
    seen: list[tuple[RclTip, RclTip]] = []

    def _compatible(original: RclTip, current: RclTip) -> bool:
        seen.append((original, current))
        return True

    release = _release(rig, clock, tip_compatible=_compatible)
    current = RclTip(*_tip(rig.rcl_log))
    assert _confirmed(release, rig, clock, tip=planned_tip) is (
        BrokerFlatVerdict.RELEASED
    )
    assert seen and set(seen) == {(RclTip(*planned_tip), current)}


@pytest.mark.parametrize(
    ("today", "age"),
    [("20261118", _READ_SPAN_MS), (_TODAY, _MAX_AGE_MS + 1)],
    ids=["other-trading-date", "too-old"],
)
def test_a_stale_read_releases_nothing(
    rig: Rig, clock: _Clock, today: str, age: int
) -> None:
    _consumed_entry(rig)
    snapshot = _snapshot(rig.rcl_log, clock, started_ms=clock.ms - age)
    snapshot = HeldPositionSnapshot(**{**snapshot.__dict__, "today": today})
    assert _release(rig, clock)(snapshot) is BrokerFlatVerdict.STALE
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_each_non_release_verdict_is_recorded_once_per_process(
    rig: Rig, clock: _Clock
) -> None:
    _consumed_entry(rig)
    release = _release(rig, clock)
    failed = WitnessUnavailable("timeout")
    for _ in range(3):
        release(_snapshot(rig.rcl_log, clock, first=failed))
        release(_snapshot(rig.rcl_log, clock))
    verdicts = [row["verdict"] for row in _rows(rig, BROKER_FLAT_RELEASE_HELD_KIND)]
    assert verdicts == ["READ_FAILED", "SETTLING"]


def test_an_rcl_error_holds_and_records_instead_of_raising(
    rig: Rig, clock: _Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _consumed_entry(rig)

    def _broken(*_args: object, **_kwargs: object) -> object:
        raise OSError("disk I/O error")

    monkeypatch.setattr(SqliteCommitLog, "apply_reservation_transition", _broken)
    assert _confirmed(_release(rig, clock), rig, clock) is BrokerFlatVerdict.RCL_REFUSED
    (held,) = [
        row
        for row in _rows(rig, BROKER_FLAT_RELEASE_HELD_KIND)
        if row["verdict"] == "RCL_REFUSED"
    ]
    assert "OSError" in held["detail"]


def test_a_broker_flat_release_ends_the_pending_entry_discharge(
    rig: Rig, clock: _Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Today's leaf: a pending discharge held by its proof gate stops retrying once flat."""
    payload = cycle._arrange_close(rig)

    def crash_before_entry(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated process stop before entry discharge")

    monkeypatch.setattr(FinalityReleaseConsumer, "_discharge_entry", crash_before_entry)
    with pytest.raises(RuntimeError, match="simulated process stop"):
        cycle._cycle_consumer(rig).consume(payload)
    monkeypatch.undo()
    consumer = cycle._cycle_consumer(rig)
    assert pending_recovery_attempt_ids(consumer) == (payload.attempt_id,)

    assert _confirmed(_release(rig, clock), rig, clock) is BrokerFlatVerdict.RELEASED
    assert _state(rig, cycle._entry_reservation_id()) is CapacityState.RELEASED
    restarted = cycle._cycle_consumer(rig)
    assert restarted.pending_recovery_attempt_ids() == ()
    assert restarted.resume_entry_discharge(payload.attempt_id) is True


def _observer_yaml(tmp_path: Path, **extra: object) -> Path:
    raw: dict[str, object] = {
        "order_inquiry_tr_id": "VTTC0081R",
        "order_inquiry_path": "/o",
        "balance_tr_id": "VTTC8434R",
        "balance_path": "/b",
        "max_pages": 10,
        "poll_interval_ms": 3000,
        "witness_request_timeout_s": 2.0,
        "poll_deadline_ms": 1500,
        "overdue_after_ms": 600000,
        "finality_retry_interval_ms": 60000,
        "prior_day_poll_interval_ms": 600000,
        "release_snapshot_max_age_ms": 6000,
        **extra,
    }
    path = tmp_path / "fill_observer.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_the_key_is_off_when_absent(tmp_path: Path) -> None:
    config = load_fill_observer_config(_observer_yaml(tmp_path))
    assert config.broker_flat_release is False
    assert config.loop_witness_request_timeout_s is None
    assert config.loop_witness_deadline_ms is None


def test_the_key_needs_its_bounds_and_a_bool(tmp_path: Path) -> None:
    held = {"held_position_poll_interval_ms": 12000, "held_position_max_age_ms": 20000}
    on = load_fill_observer_config(
        _observer_yaml(
            tmp_path,
            broker_flat_release=True,
            broker_flat_release_settle_ms=30000,
            **held,
        )
    )
    assert on.broker_flat_release is True
    assert on.broker_flat_release_settle_ms == 30000
    with pytest.raises(FillObserverConfigError, match="held-position"):
        load_fill_observer_config(_observer_yaml(tmp_path, broker_flat_release=True))
    with pytest.raises(FillObserverConfigError, match="settle"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, broker_flat_release=True, **held)
        )
    with pytest.raises(FillObserverConfigError, match="true or false"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, broker_flat_release="yes", **held)
        )
