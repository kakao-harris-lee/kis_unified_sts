"""Broker-flat entry release through the composed KIS mock stock runtime (2026-11-19)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.broker_flat_release import (
    BROKER_FLAT_RELEASE_HELD_KIND,
    BROKER_FLAT_RELEASE_KIND,
    broker_flat_release_command_id,
)
from tos_runtime.posttrade.fill_observer import FILL_OBSERVER_CONFIG_NAME

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_kis_mock_close_risk_e2e import (
    _capture_published,
    _PacedClock,
    _script_order_ack,
    _script_witness,
    _speed_observer_polls,
    _wait_for_publish,
)
from .test_kis_mock_e2e_honesty import _ORDER_PATH, _sealed_mock_deployment
from .test_kis_mock_fill_finality_e2e import _ODNO, _close, _row, _rows, _witness_paths

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ENVIRONMENT_LABEL = "non-live-test"


def _set_flag(config_dir: Path, enabled: bool | None, settle_ms: int) -> None:
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw.pop("broker_flat_release", None)
    raw["broker_flat_release_settle_ms"] = settle_ms
    if enabled is not None:
        raw["broker_flat_release"] = enabled
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _poll_until_released(runtime, observer, published, max_polls: int = 8) -> int:
    """Publish held double reads until the entry is released; return how many it took."""
    for count in range(1, max_polls + 1):
        _wait_for_publish(observer, published, len(published))
        if _entry_states(runtime) == [CapacityState.RELEASED]:
            return count
    raise AssertionError(f"not released after {max_polls} flat polls")


def _poll_flat(observer, published, polls: int) -> None:
    """``polls`` more published held double reads (settle, first flat, confirming flat, ...)."""
    for _ in range(polls):
        _wait_for_publish(observer, published, len(published))


def _entry_states(runtime) -> list[CapacityState]:
    return [state for _rid, state, _seq, _scope in runtime.rcl_log.reservation_rows()]


def _filled_entry(
    config_dir, data_dir, custody_root, monkeypatch, server, flag, settle_ms=1
):
    """Boot, OPEN, fill: the scope holds one POSITION_CONSUMED entry and the broker 1 lot."""
    clock = _PacedClock()
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    _script_order_ack(server, _ODNO)
    fx.write_band_strategy_file(config_dir)
    _speed_observer_polls(config_dir)
    _set_flag(config_dir, flag, settle_ms)
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        _ENVIRONMENT_LABEL,
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        transport_kind=TransportKind.KIS_MOCK,
        monotonic_source=clock,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    observer = runtime.fill_observer
    assert observer is not None
    published, _bridge = _capture_published(observer)
    assert runtime.session_facts is not None
    date = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
    assert date is not None
    _script_witness(server, config_dir, date=date, rows=[], holdings=())
    event = fx.crossing_event(seq=1)
    discovery = runtime.run_once((event,))[0]
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    quantity = construction.derivation.quantity
    assert quantity is not None and quantity > 0
    assert discovery.pipeline is not None and discovery.pipeline.proposal is not None
    proposal_digest = discovery.pipeline.proposal.canonical_digest
    intent_digest = construction.intent.canonical_digest
    assert proposal_digest is not None and intent_digest is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=intent_digest,
    )
    open_row = _row(
        odno=_ODNO, date=date, ord_qty=quantity, filled=quantity, remaining=Decimal(0)
    )
    _script_witness(
        server,
        config_dir,
        date=date,
        rows=[open_row],
        holdings=((fx.INSTRUMENT, quantity),),
    )
    result = runtime.run_once((event,))[0]
    assert result.flow is not None and result.flow.handed_off is True
    _wait_for_publish(observer, published, len(published))
    assert _entry_states(runtime) == [CapacityState.POSITION_CONSUMED]
    return runtime, observer, published, date, open_row


@pytest.mark.parametrize("flag", [True, False, None], ids=["on", "off", "absent"])
def test_a_flat_broker_releases_the_entry_only_when_enabled(
    flag: bool | None,
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    runtime, observer, published, date, open_row = _filled_entry(
        config_dir_with_risk_state, data_dir, custody_root, monkeypatch, server, flag
    )
    try:
        assert (observer.broker_flat_release is not None) is bool(flag)
        _script_witness(
            server, config_dir_with_risk_state, date=date, rows=[open_row], holdings=()
        )
        if flag:
            assert _poll_until_released(runtime, observer, published) >= 3
            assert _entry_states(runtime) == [CapacityState.RELEASED]
            (row,) = _rows(runtime, BROKER_FLAT_RELEASE_KIND)
            (reservation_id,) = [
                rid for rid, _s, _q, _sc in runtime.rcl_log.reservation_rows()
            ]
            assert row["reservation_id"] == reservation_id
            assert runtime.rcl_log.command_committed(
                broker_flat_release_command_id(reservation_id)
            )
            _wait_for_publish_or_idle(observer)
            assert len(_rows(runtime, BROKER_FLAT_RELEASE_KIND)) == 1
        else:
            _poll_flat(observer, published, 4)
            assert observer.broker_flat_release is None
            assert _entry_states(runtime) == [CapacityState.POSITION_CONSUMED]
            assert _rows(runtime, BROKER_FLAT_RELEASE_KIND) == []
        assert len(server.requests_for(_ORDER_PATH)) == 1
    finally:
        _close(runtime)


def _wait_for_publish_or_idle(observer) -> None:
    """A few more passes: once released, no held-position read is even planned."""
    for _ in range(50):
        observer.poll_if_due()


def test_a_failed_balance_read_holds_and_the_next_flat_read_releases(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    runtime, observer, published, date, open_row = _filled_entry(
        config_dir_with_risk_state, data_dir, custody_root, monkeypatch, server, True
    )
    try:
        balance_path, _order_path = _witness_paths(config_dir_with_risk_state, date)
        server.set_response(balance_path, status=500, body={"rt_cd": "1"})
        _wait_for_publish(observer, published, len(published))
        assert _entry_states(runtime) == [CapacityState.POSITION_CONSUMED]
        assert _rows(runtime, BROKER_FLAT_RELEASE_KIND) == []

        _script_witness(
            server, config_dir_with_risk_state, date=date, rows=[open_row], holdings=()
        )
        assert _poll_until_released(runtime, observer, published) >= 3
        assert _entry_states(runtime) == [CapacityState.RELEASED]
        assert len(_rows(runtime, BROKER_FLAT_RELEASE_KIND)) == 1
    finally:
        _close(runtime)


def test_a_broker_still_holding_the_lot_releases_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    runtime, observer, published, _date, _row_ = _filled_entry(
        config_dir_with_risk_state, data_dir, custody_root, monkeypatch, server, True
    )
    try:
        for _ in range(2):
            _wait_for_publish(observer, published, len(published))
        assert _entry_states(runtime) == [CapacityState.POSITION_CONSUMED]
        assert _rows(runtime, BROKER_FLAT_RELEASE_KIND) == []
    finally:
        _close(runtime)


def test_flat_reads_inside_the_settle_window_release_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """review-1114 M1: right after the entry's FULL_FILL the balance may not show the buy yet."""
    runtime, observer, published, date, open_row = _filled_entry(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        monkeypatch,
        server,
        True,
        settle_ms=600_000,
    )
    try:
        _script_witness(
            server, config_dir_with_risk_state, date=date, rows=[open_row], holdings=()
        )
        _poll_flat(observer, published, 4)
        assert _entry_states(runtime) == [CapacityState.POSITION_CONSUMED]
        assert _rows(runtime, BROKER_FLAT_RELEASE_KIND) == []
        verdicts = [
            row["verdict"] for row in _rows(runtime, BROKER_FLAT_RELEASE_HELD_KIND)
        ]
        assert verdicts == ["NOT_FLAT", "SETTLING"]
    finally:
        _close(runtime)
