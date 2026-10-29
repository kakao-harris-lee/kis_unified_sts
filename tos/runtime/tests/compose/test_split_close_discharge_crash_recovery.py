"""Issue #1004 compose crash window with the production KIS-mock risk proof path."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
from tos.rcl import CapacityState, CommandType
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.release_consumer import (
    FinalityReleaseConsumer,
    entry_release_command_id,
    release_command_id,
)
from tos_runtime.riskstate.service import RiskStateService

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from . import test_kis_mock_close_risk_e2e as riskfx
from .test_kis_mock_fill_finality_e2e import _ODNO, _close, _row, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class _SimulatedProcessCrash(BaseException):
    """Escape after releasing the close reservation and before discharging its entry."""


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    instance = FakeKisServer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def _reservation_state(runtime, reservation_id: str) -> CapacityState:
    for current_id, state, _seq, _scope in runtime.rcl_log.reservation_rows():
        if current_id == reservation_id:
            assert isinstance(state, CapacityState)
            return state
    raise AssertionError(f"reservation is absent from RCL: {reservation_id}")


def _release_transition_count(runtime, command_id: str) -> int:
    return sum(
        entry.kind == CommandType.RELEASE_RESERVATION.value
        and entry.command_id == command_id
        for entry in runtime.rcl_log.replay()
    )


def _positions(runtime) -> tuple[tuple[str, CapacityState], ...]:
    """Use the real RCL reservation projection to identify the OPEN entry row."""
    rows = runtime.rcl_log.reservation_rows()
    return tuple(
        (reservation_id, state) for reservation_id, state, _seq, _scope in rows
    )


def test_public_restart_finishes_entry_discharge_after_close_release_crash(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """A real filled OPEN and approved CLOSE leave entry recovery pending across restart."""
    clock = riskfx._PacedClock()
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    riskfx._sealed_mock_deployment(
        config_dir_with_risk_state, custody_root, server, monkeypatch
    )
    riskfx._script_order_ack(server, _ODNO)
    riskfx._write_close_strategy(config_dir_with_risk_state, monkeypatch)
    riskfx._speed_observer_polls(config_dir_with_risk_state)

    runtime = compose_paper_runtime(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        riskfx._ENVIRONMENT_LABEL,
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        transport_kind=riskfx.TransportKind.KIS_MOCK,
        monotonic_source=clock,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    runtime2 = None
    try:
        assert type(runtime.risk_state) is RiskStateService
        observer = runtime.fill_observer
        assert observer is not None and observer.snapshots is not None
        published, bridge = riskfx._capture_published(observer)
        assert runtime.session_facts is not None
        date = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
        assert date is not None

        # Discover/approve OPEN, then let the actual worker obtain an initial complete pair.
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[],
            holdings=(),
        )
        open_event = fx.crossing_event(seq=1)
        open_discovery = runtime.run_once((open_event,))[0]
        assert open_discovery.pipeline is not None
        assert open_discovery.pipeline.proposal is not None
        open_construction = runtime.construction_stage.construction
        assert open_construction is not None and open_construction.intent is not None
        open_quantity = open_construction.derivation.quantity
        assert open_quantity is not None and open_quantity > 0
        proposal_digest = open_discovery.pipeline.proposal.canonical_digest
        intent_digest = open_construction.intent.canonical_digest
        assert isinstance(proposal_digest, str)
        assert isinstance(intent_digest, str)
        riskfx.write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label=riskfx._ENVIRONMENT_LABEL,
            approved_intent_envelope_digest=intent_digest,
        )
        # No position-proof worker read is eligible before the OPEN fill has produced a durable
        # POSITION_CONSUMED entry reservation.
        assert published == []

        open_row = _row(
            odno=_ODNO,
            date=date,
            ord_qty=open_quantity,
            filled=open_quantity,
            remaining=Decimal(0),
        )
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, open_quantity),),
        )
        open_result = runtime.run_once((open_event,))[0]
        assert open_result.flow is not None and open_result.flow.handed_off is True
        assert len(server.requests_for(riskfx._ORDER_PATH)) == 1
        open_attempt = next(
            row["attempt_id"]
            for row in _rows(runtime, "EGRESS_RESULT_CONSUMED")
            if row["egress_result_kind"] == "ACK"
        )

        # First async APPLY sees the full OPEN fill, then another pair binds the positive
        # holdings to the post-fill RCL tip.
        after_open = len(published)
        open_fill_pair = riskfx._wait_for_publish(observer, published, after_open)
        assert isinstance(open_fill_pair.first, riskfx.WitnessSnapshot)
        assert open_fill_pair.first.positions == ((fx.INSTRUMENT, open_quantity),)
        assert any(
            row["attempt_id"] == open_attempt
            and row["egress_result_kind"] == "FULL_FILL"
            for row in _rows(runtime, "EGRESS_RESULT_CONSUMED")
        )
        assert (
            _reservation_state(
                runtime,
                next(
                    reservation_id
                    for reservation_id, state in _positions(runtime)
                    if state is CapacityState.POSITION_CONSUMED
                ),
            )
            is CapacityState.POSITION_CONSUMED
        )
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, open_quantity),),
        )
        after_open_fill = len(published)
        riskfx._wait_for_publish(observer, published, after_open_fill)

        (entry_reservation_id,) = tuple(
            reservation_id
            for reservation_id, state in _positions(runtime)
            if state is CapacityState.POSITION_CONSUMED
        )

        close_event = fx.crossing_event(seq=2, close=fx.UPPER_BAND + 1_000)
        riskfx._discover_and_approve(runtime, custody_root, close_event)
        # Step 4 consumes the proposal approval and advances the durable RCL. The proof pair is
        # therefore refreshed after discovery, before the approved CLOSE replay reaches Step 6.
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, open_quantity),),
        )
        after_close_discovery = len(published)
        riskfx._wait_for_publish(observer, published, after_close_discovery)

        riskfx._script_order_ack(server, riskfx._CLOSE_ODNO)
        posts_before_close = len(server.requests_for(riskfx._ORDER_PATH))
        close_result = runtime.run_once((close_event,))[0]
        assert close_result.flow is not None and close_result.flow.handed_off is True
        assert len(server.requests_for(riskfx._ORDER_PATH)) == posts_before_close + 1
        close_observation = [
            row for row in riskfx._risk_observations(runtime) if "close_effect" in row
        ][-1]
        assert close_observation["close_effect"]["proof_status"] == "PROOF_ACCEPTED"
        assert (
            Decimal(close_observation["close_effect"]["held_quantity"]) == open_quantity
        )
        close_attempt_id = next(
            row["attempt_id"]
            for row in reversed(_rows(runtime, "EGRESS_RESULT_CONSUMED"))
            if row["egress_result_kind"] == "ACK"
        )

        close_row = _row(
            odno=riskfx._CLOSE_ODNO,
            date=date,
            ord_qty=open_quantity,
            filled=open_quantity,
            remaining=Decimal(0),
        )
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close_row],
            holdings=(),
        )
        close_reservation_id = next(
            reservation_id
            for reservation_id, _state in _positions(runtime)
            if reservation_id != entry_reservation_id
        )
        after_close_fill = len(published)

        def crash_before_entry_discharge(
            self, payload, entry, *, proof, report
        ) -> None:
            del self, payload, entry, proof, report
            raise _SimulatedProcessCrash

        with monkeypatch.context() as patch:
            patch.setattr(
                FinalityReleaseConsumer,
                "_discharge_entry",
                crash_before_entry_discharge,
            )
            with pytest.raises(_SimulatedProcessCrash):
                riskfx._wait_for_publish(observer, published, after_close_fill)

        assert (
            _reservation_state(runtime, close_reservation_id) is CapacityState.RELEASED
        )
        assert (
            _reservation_state(runtime, entry_reservation_id)
            is CapacityState.POSITION_CONSUMED
        )
        assert (
            _release_transition_count(runtime, release_command_id(close_attempt_id))
            == 1
        )
        assert (
            _release_transition_count(
                runtime, entry_release_command_id(close_attempt_id)
            )
            == 0
        )

        _close(runtime)
        runtime2 = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            riskfx._ENVIRONMENT_LABEL,
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            transport_kind=riskfx.TransportKind.KIS_MOCK,
            monotonic_source=clock,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert type(runtime2.risk_state) is RiskStateService
        assert runtime2.recovery is not None and runtime2.recovery.ready is True
        observer2 = runtime2.fill_observer
        assert observer2 is not None
        published2, _bridge2 = riskfx._capture_published(observer2)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close_row],
            holdings=(),
        )
        assert observer2.pending_recovery_attempt_ids is not None
        assert close_attempt_id in observer2.pending_recovery_attempt_ids()
        release_snapshots_before_recovery = len(
            _rows(runtime2, riskfx.FILL_OBSERVER_RELEASE_SNAPSHOT_KIND)
        )
        recovery_snapshot = riskfx._wait_for_release_snapshot(
            observer2, runtime2, release_snapshots_before_recovery
        )
        assert recovery_snapshot["verdict"] == "served"
        assert recovery_snapshot["read_ok"] is True
        assert close_attempt_id not in observer2.pending_recovery_attempt_ids()
        # Recovery consumed the independent flat release snapshot; no position-proof poll is
        # eligible once entry discharge has committed.
        assert published2 == []

        assert (
            _reservation_state(runtime2, entry_reservation_id) is CapacityState.RELEASED
        )
        assert (
            _reservation_state(runtime2, close_reservation_id) is CapacityState.RELEASED
        )
        assert (
            _release_transition_count(runtime2, release_command_id(close_attempt_id))
            == 1
        )
        assert (
            _release_transition_count(
                runtime2, entry_release_command_id(close_attempt_id)
            )
            == 1
        )
    finally:
        if runtime2 is not None:
            _close(runtime2)
        elif runtime.rcl_log is not None:
            _close(runtime)
