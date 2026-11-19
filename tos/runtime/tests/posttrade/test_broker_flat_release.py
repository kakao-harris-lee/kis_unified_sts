"""Broker-flat release of a held entry reservation (operator decision 2026-11-19, option B)."""

from __future__ import annotations

import json
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
_NOW_MS = 1_000_000
_MAX_AGE_MS = 20_000
_ENTRY = "res-flat-entry"


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
    *,
    first: object = None,
    confirmation: object = None,
    started_ms: int = _NOW_MS - 1_000,
) -> HeldPositionSnapshot:
    return HeldPositionSnapshot(
        scope=WitnessScope(
            account=cycle._ACCOUNT,
            instrument_keys=(
                InstrumentKey(account=cycle._ACCOUNT, instrument=cycle._INSTRUMENT),
            ),
        ),
        today=_TODAY,
        generation=None,
        tip=_tip(rcl_log),
        token=1,
        first=_flat_read() if first is None else first,  # type: ignore[arg-type]
        confirmation=(
            _flat_read() if confirmation is None else confirmation  # type: ignore[arg-type]
        ),
        first_balance_read_started_ms=started_ms,
        confirmation_balance_read_started_ms=started_ms + 500,
        read_finished_ms=started_ms + 900,
    )


def _release(
    rig: Rig,
    *,
    in_flight: bool = False,
    tip_compatible: bool = False,
) -> BrokerFlatRelease:
    return BrokerFlatRelease(
        rcl_log=rig.rcl_log,
        evidence_store=rig.evidence_store,
        scheme=_SCHEME,
        account=cycle._ACCOUNT,
        instrument=cycle._INSTRUMENT,
        today=lambda: _TODAY,
        now_ms=lambda: _NOW_MS,
        max_age_ms=_MAX_AGE_MS,
        in_flight=lambda: in_flight,
        tip_compatible=lambda _a, _b: tip_compatible,
    )


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


def test_flat_double_read_releases_once_with_an_evidence_row(rig: Rig) -> None:
    _consumed_entry(rig)
    release = _release(rig)
    assert release(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.RELEASED
    assert _state(rig) is CapacityState.RELEASED
    (row,) = _rows(rig, BROKER_FLAT_RELEASE_KIND)
    assert row["reservation_id"] == _ENTRY
    assert row["command_id"] == broker_flat_release_command_id(_ENTRY)
    assert rig.rcl_log.committed_command(broker_flat_release_command_id(_ENTRY))

    assert release(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.NOT_ELIGIBLE
    assert len(_rows(rig, BROKER_FLAT_RELEASE_KIND)) == 1


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
def test_a_failed_read_releases_nothing_and_the_next_read_can(
    rig: Rig, first: object, confirmation: object
) -> None:
    _consumed_entry(rig)
    release = _release(rig)
    failed = _snapshot(rig.rcl_log, first=first, confirmation=confirmation)
    assert release(failed) is BrokerFlatVerdict.READ_FAILED
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    assert _rows(rig, BROKER_FLAT_RELEASE_KIND) == []

    assert release(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.RELEASED
    assert _state(rig) is CapacityState.RELEASED


def test_a_missing_confirmation_is_a_failed_read(rig: Rig) -> None:
    _consumed_entry(rig)
    snapshot = _snapshot(rig.rcl_log)
    no_confirmation = HeldPositionSnapshot(
        **{**snapshot.__dict__, "confirmation": None}
    )
    assert _release(rig)(no_confirmation) is BrokerFlatVerdict.READ_FAILED
    assert _state(rig) is CapacityState.POSITION_CONSUMED


@pytest.mark.parametrize("which", ["first", "confirmation"])
def test_a_held_share_in_either_read_releases_nothing(rig: Rig, which: str) -> None:
    _consumed_entry(rig)
    held = _flat_read((cycle._INSTRUMENT, Decimal(1)))
    snapshot = (
        _snapshot(rig.rcl_log, first=held)
        if which == "first"
        else _snapshot(rig.rcl_log, confirmation=held)
    )
    assert _release(rig)(snapshot) is BrokerFlatVerdict.NOT_FLAT
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_another_symbol_held_does_not_block(rig: Rig) -> None:
    _consumed_entry(rig)
    other = _flat_read(("000660", Decimal(3)))
    snapshot = _snapshot(rig.rcl_log, first=other, confirmation=other)
    assert _release(rig)(snapshot) is BrokerFlatVerdict.RELEASED


def test_an_in_flight_attempt_releases_nothing(rig: Rig) -> None:
    _consumed_entry(rig)
    assert (
        _release(rig, in_flight=True)(_snapshot(rig.rcl_log))
        is BrokerFlatVerdict.IN_FLIGHT
    )
    assert _state(rig) is CapacityState.POSITION_CONSUMED
    assert _rows(rig, BROKER_FLAT_RELEASE_KIND) == []


def test_an_in_flight_reader_failure_releases_nothing(rig: Rig) -> None:
    _consumed_entry(rig)

    def _boom() -> bool:
        raise RuntimeError("evidence unreadable")

    release = BrokerFlatRelease(
        **{**_release(rig).__dict__, "in_flight": _boom},
    )
    assert release(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.IN_FLIGHT
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_an_outstanding_open_or_close_reservation_is_not_eligible(rig: Rig) -> None:
    _consumed_entry(rig)
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-flat-close",
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="bind-res-flat-close",
    )
    assert _release(rig)(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.NOT_ELIGIBLE
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_a_scope_with_no_reservation_is_not_eligible(rig: Rig) -> None:
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-unbound",
        to_state=CapacityState.ATTEMPT_BOUND,
        command_id="bind-res-unbound",
    )
    assert _release(rig)(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.NOT_ELIGIBLE


def test_an_rcl_that_moved_since_the_read_was_planned_releases_nothing(
    rig: Rig,
) -> None:
    _consumed_entry(rig)
    planned = _snapshot(rig.rcl_log)
    cycle._commit_named_reservation(
        rig.rcl_log,
        reservation_id="res-elsewhere",
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="release-attempt-elsewhere",
    )
    assert _release(rig)(planned) is BrokerFlatVerdict.RCL_MOVED
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_an_approval_only_tip_advance_is_admitted(rig: Rig) -> None:
    """A moved tip is judged by the bridge's approval-only gap check (stubbed admitting)."""
    rig.rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="relc-test-cell", process_nonce="relc-test-nonce")
    )
    planned = _snapshot(rig.rcl_log)
    _consumed_entry(rig)
    seen: list[tuple[RclTip, RclTip]] = []

    def _compatible(original: RclTip, current: RclTip) -> bool:
        seen.append((original, current))
        return True

    release = BrokerFlatRelease(
        **{**_release(rig).__dict__, "tip_compatible": _compatible}
    )
    assert planned.tip is not None
    current = RclTip(*_tip(rig.rcl_log))
    assert release(planned) is BrokerFlatVerdict.RELEASED
    assert seen == [(RclTip(*planned.tip), current)]


@pytest.mark.parametrize(
    ("today", "started"),
    [("20261118", _NOW_MS - 1_000), (_TODAY, _NOW_MS - _MAX_AGE_MS - 1)],
    ids=["other-trading-date", "too-old"],
)
def test_a_stale_read_releases_nothing(rig: Rig, today: str, started: int) -> None:
    _consumed_entry(rig)
    snapshot = _snapshot(rig.rcl_log, started_ms=started)
    snapshot = HeldPositionSnapshot(**{**snapshot.__dict__, "today": today})
    assert _release(rig)(snapshot) is BrokerFlatVerdict.STALE
    assert _state(rig) is CapacityState.POSITION_CONSUMED


def test_a_broker_flat_release_ends_the_pending_entry_discharge(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
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

    assert _release(rig)(_snapshot(rig.rcl_log)) is BrokerFlatVerdict.RELEASED
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
    assert load_fill_observer_config(_observer_yaml(tmp_path)).broker_flat_release is (
        False
    )


def test_the_key_needs_the_held_position_bounds_and_a_bool(tmp_path: Path) -> None:
    held = {"held_position_poll_interval_ms": 12000, "held_position_max_age_ms": 20000}
    on = load_fill_observer_config(
        _observer_yaml(tmp_path, broker_flat_release=True, **held)
    )
    assert on.broker_flat_release is True
    with pytest.raises(FillObserverConfigError, match="held-position"):
        load_fill_observer_config(_observer_yaml(tmp_path, broker_flat_release=True))
    with pytest.raises(FillObserverConfigError, match="true or false"):
        load_fill_observer_config(
            _observer_yaml(tmp_path, broker_flat_release="yes", **held)
        )
