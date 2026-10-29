"""KIS-mock end-to-end: two full CLOSE fills discharge one OPEN across public reboots."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import CapacityState, CommandType
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.release_consumer import (
    entry_release_command_id,
    release_command_id,
)
from tos_runtime.riskstate.service import RiskStateService
from tos_runtime.venue import load_order_construction_policy

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from . import test_kis_mock_close_risk_e2e as riskfx
from .test_kis_mock_fill_finality_e2e import _ODNO, _close, _row, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_CLOSE_1_ODNO = "0000004491"
_CLOSE_2_ODNO = "0000004492"
_OCP_CONFIG_NAME = "order_construction_policy.yaml"
_ACTIVATION_NAME = "safety_activation.yaml"


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    instance = FakeKisServer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def _write_risk_budget(
    config_dir: Path, *, budget: int, construction_generation: int
) -> str:
    """Change only test OCP YAML construction, then rebind its expected activation digest."""
    path = config_dir / _OCP_CONFIG_NAME
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    document["construction_generation"] = construction_generation
    document["policy_generation"] = construction_generation
    model_view = document["_model_view"]
    assert isinstance(model_view, dict)
    model_view["policy_generation"] = construction_generation
    runtime = document["_runtime"]
    assert isinstance(runtime, dict)
    construction = runtime["construction"]
    assert isinstance(construction, dict)
    sizing = construction["sizing"]
    assert isinstance(sizing, dict)
    sizing["risk_budget"] = budget
    # The fixture's activation digest is rebound below after the canonical
    # policy loader recomputes the digest for this construction generation.
    document["canonical_digest"] = "TBD"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    loaded = load_order_construction_policy(
        path, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
    )
    assert loaded.policy.policy_generation == construction_generation
    assert loaded.construction_generation == construction_generation
    assert loaded.construction_rules.sizing_bound.risk_budget == Decimal(budget)
    digest = loaded.policy.canonical_digest
    assert isinstance(digest, str)
    document["canonical_digest"] = digest
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    loaded = load_order_construction_policy(
        path, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
    )
    assert loaded.policy.canonical_digest == digest
    activation_path = config_dir / _ACTIVATION_NAME
    activation = yaml.safe_load(activation_path.read_text(encoding="utf-8"))
    assert isinstance(activation, dict)
    members = activation["members"]
    assert isinstance(members, list)
    ocp_member = next(
        member
        for member in members
        if isinstance(member, dict)
        and member.get("kind") == "ORDER_CONSTRUCTION_POLICY"
    )
    ocp_member["generation"] = loaded.policy.policy_generation
    ocp_member["digest"] = loaded.policy.canonical_digest
    activation_path.write_text(
        yaml.safe_dump(activation, sort_keys=False), encoding="utf-8"
    )
    digest = loaded.policy.canonical_digest
    assert isinstance(digest, str)
    return digest


def _boot(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    clock: riskfx._PacedClock,
) -> ComposedRuntime:
    runtime = compose_paper_runtime(
        config_dir,
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
    assert type(runtime.risk_state) is RiskStateService
    return runtime


def _reservation_states(runtime: ComposedRuntime) -> dict[str, CapacityState]:
    states: dict[str, CapacityState] = {}
    for reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows():
        assert isinstance(state, CapacityState)
        states[reservation_id] = state
    return states


def _release_count(runtime: ComposedRuntime, command_id: str) -> int:
    return sum(
        entry.kind == CommandType.RELEASE_RESERVATION.value
        and entry.command_id == command_id
        for entry in runtime.rcl_log.replay()
    )


def test_two_full_close_fills_accumulate_through_restart_and_release_entry_once(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """10 OPEN, FULL_FILL CLOSE 4 leaves 6, then FULL_FILL CLOSE 6 and broker flat."""
    clock = riskfx._PacedClock()
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    riskfx._sealed_mock_deployment(
        config_dir_with_risk_state, custody_root, server, monkeypatch
    )
    riskfx._script_order_ack(server, _ODNO)
    riskfx._write_close_strategy(config_dir_with_risk_state, monkeypatch)
    riskfx._speed_observer_polls(config_dir_with_risk_state)

    runtime0: ComposedRuntime | None = _boot(
        config_dir_with_risk_state, data_dir, custody_root, clock
    )
    runtime1: ComposedRuntime | None = None
    runtime2: ComposedRuntime | None = None
    runtime3: ComposedRuntime | None = None
    try:
        assert runtime0 is not None
        observer0 = runtime0.fill_observer
        assert observer0 is not None and observer0.snapshots is not None
        published0, _bridge0 = riskfx._capture_published(observer0)
        assert runtime0.session_facts is not None
        date = runtime0.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
        assert date is not None
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[],
            holdings=(),
        )

        # Produce and fill a real 10-unit OPEN through KIS mock.
        open_event = fx.crossing_event(seq=1)
        open_discovery = runtime0.run_once((open_event,))[0]
        assert open_discovery.pipeline is not None
        assert open_discovery.pipeline.proposal is not None
        open_construction = runtime0.construction_stage.construction
        assert open_construction is not None and open_construction.intent is not None
        open_quantity = open_construction.derivation.quantity
        assert open_quantity == Decimal(10)
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
        # The worker has no close-proof eligibility while the account is still flat and the
        # OPEN reservation has not reached POSITION_CONSUMED.
        assert published0 == []

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
        open_result = runtime0.run_once((open_event,))[0]
        assert open_result.flow is not None and open_result.flow.handed_off is True
        assert len(server.requests_for(riskfx._ORDER_PATH)) == 1
        open_attempt_id = next(
            row["attempt_id"]
            for row in _rows(runtime0, "EGRESS_RESULT_CONSUMED")
            if row["egress_result_kind"] == "ACK"
        )
        after_open = len(published0)
        open_pair = riskfx._wait_for_publish(observer0, published0, after_open)
        assert isinstance(open_pair.first, riskfx.WitnessSnapshot)
        assert open_pair.first.positions == ((fx.INSTRUMENT, Decimal(10)),)
        assert any(
            row["attempt_id"] == open_attempt_id
            and row["egress_result_kind"] == "FULL_FILL"
            and Decimal(row["filled_quantity"]) == Decimal(10)
            and Decimal(row["remaining_quantity"]) == Decimal(0)
            for row in _rows(runtime0, "EGRESS_RESULT_CONSUMED")
        )
        entry_reservation_id, *_ = tuple(
            reservation_id
            for reservation_id, state in _reservation_states(runtime0).items()
            if state is CapacityState.POSITION_CONSUMED
        )
        assert _reservation_states(runtime0)[entry_reservation_id] is (
            CapacityState.POSITION_CONSUMED
        )

        # Reboot under test OCP sizing 4. This is a new public composition over the same
        # durable inbox/evidence/RCL files; it does not replace a loaded construction object.
        _close(runtime0)
        runtime0 = None
        digest4 = _write_risk_budget(
            config_dir_with_risk_state, budget=40, construction_generation=2
        )
        assert digest4
        runtime1 = _boot(config_dir_with_risk_state, data_dir, custody_root, clock)
        assert runtime1 is not None
        assert runtime1.recovery is not None and runtime1.recovery.ready is True
        observer1 = runtime1.fill_observer
        assert observer1 is not None
        published1, _bridge1 = riskfx._capture_published(observer1)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, Decimal(10)),),
        )
        riskfx._wait_for_publish(observer1, published1, 0)

        close1_event = fx.crossing_event(seq=2, close=fx.UPPER_BAND + 1_000)
        riskfx._discover_and_approve(runtime1, custody_root, close1_event)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, Decimal(10)),),
        )
        after_close1_discovery = len(published1)
        riskfx._wait_for_publish(observer1, published1, after_close1_discovery)
        riskfx._script_order_ack(server, _CLOSE_1_ODNO)
        posts_before_close1 = len(server.requests_for(riskfx._ORDER_PATH))
        close1_result = runtime1.run_once((close1_event,))[0]
        assert close1_result.flow is not None and close1_result.flow.handed_off is True
        close1_construction = runtime1.construction_stage.construction
        assert close1_construction is not None
        close1_quantity = close1_construction.derivation.quantity
        assert close1_quantity == Decimal(4)
        assert len(server.requests_for(riskfx._ORDER_PATH)) == posts_before_close1 + 1
        close1_observation = [
            row for row in riskfx._risk_observations(runtime1) if "close_effect" in row
        ][-1]
        assert close1_observation["close_effect"]["proof_status"] == "PROOF_ACCEPTED"
        assert Decimal(close1_observation["close_effect"]["held_quantity"]) == Decimal(
            10
        )
        close1_attempt_id = next(
            row["attempt_id"]
            for row in reversed(_rows(runtime1, "EGRESS_RESULT_CONSUMED"))
            if row["egress_result_kind"] == "ACK"
        )
        close1_row = _row(
            odno=_CLOSE_1_ODNO,
            date=date,
            ord_qty=close1_quantity,
            filled=close1_quantity,
            remaining=Decimal(0),
        )
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close1_row],
            holdings=((fx.INSTRUMENT, Decimal(6)),),
        )
        after_close1_fill = len(published1)
        close1_pair = riskfx._wait_for_publish(observer1, published1, after_close1_fill)
        assert isinstance(close1_pair.first, riskfx.WitnessSnapshot)
        assert close1_pair.first.positions == ((fx.INSTRUMENT, Decimal(6)),)
        assert any(
            row["attempt_id"] == close1_attempt_id
            and row["egress_result_kind"] == "FULL_FILL"
            and Decimal(row["filled_quantity"]) == Decimal(4)
            and Decimal(row["remaining_quantity"]) == Decimal(0)
            for row in _rows(runtime1, "EGRESS_RESULT_CONSUMED")
        )
        close1_reservation_id = next(
            reservation_id
            for reservation_id, state in _reservation_states(runtime1).items()
            if reservation_id != entry_reservation_id
            and state is CapacityState.RELEASED
        )
        assert _release_count(runtime1, release_command_id(close1_attempt_id)) == 1
        assert (
            _release_count(runtime1, entry_release_command_id(close1_attempt_id)) == 0
        )
        assert _reservation_states(runtime1)[entry_reservation_id] is (
            CapacityState.POSITION_CONSUMED
        )

        # Reboot after the first complete close. Recovery sees broker holdings 6 and must not
        # release the entry merely because close1 itself was FULL_FILL and RELEASED.
        _close(runtime1)
        runtime1 = None
        digest6 = _write_risk_budget(
            config_dir_with_risk_state, budget=60, construction_generation=3
        )
        assert digest6
        runtime2 = _boot(config_dir_with_risk_state, data_dir, custody_root, clock)
        assert runtime2 is not None
        assert runtime2.recovery is not None and runtime2.recovery.ready is True
        observer2 = runtime2.fill_observer
        assert observer2 is not None
        published2, _bridge2 = riskfx._capture_published(observer2)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close1_row],
            holdings=((fx.INSTRUMENT, Decimal(6)),),
        )
        riskfx._wait_for_publish(observer2, published2, 0)
        assert _reservation_states(runtime2)[entry_reservation_id] is (
            CapacityState.POSITION_CONSUMED
        )
        assert _release_count(runtime2, release_command_id(close1_attempt_id)) == 1
        assert (
            _release_count(runtime2, entry_release_command_id(close1_attempt_id)) == 0
        )

        close2_event = fx.crossing_event(seq=3, close=fx.UPPER_BAND + 2_000)
        riskfx._discover_and_approve(runtime2, custody_root, close2_event)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close1_row],
            holdings=((fx.INSTRUMENT, Decimal(6)),),
        )
        after_close2_discovery = len(published2)
        riskfx._wait_for_publish(observer2, published2, after_close2_discovery)
        riskfx._script_order_ack(server, _CLOSE_2_ODNO)
        posts_before_close2 = len(server.requests_for(riskfx._ORDER_PATH))
        close2_result = runtime2.run_once((close2_event,))[0]
        assert close2_result.flow is not None and close2_result.flow.handed_off is True
        close2_construction = runtime2.construction_stage.construction
        assert close2_construction is not None
        close2_quantity = close2_construction.derivation.quantity
        assert close2_quantity == Decimal(6)
        assert len(server.requests_for(riskfx._ORDER_PATH)) == posts_before_close2 + 1
        close2_observation = [
            row for row in riskfx._risk_observations(runtime2) if "close_effect" in row
        ][-1]
        assert close2_observation["close_effect"]["proof_status"] == "PROOF_ACCEPTED"
        assert Decimal(close2_observation["close_effect"]["held_quantity"]) == Decimal(
            6
        )
        close2_attempt_id = next(
            row["attempt_id"]
            for row in reversed(_rows(runtime2, "EGRESS_RESULT_CONSUMED"))
            if row["egress_result_kind"] == "ACK"
        )
        assert close2_attempt_id != close1_attempt_id
        close2_row = _row(
            odno=_CLOSE_2_ODNO,
            date=date,
            ord_qty=close2_quantity,
            filled=close2_quantity,
            remaining=Decimal(0),
        )
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close1_row, close2_row],
            holdings=(),
        )
        release_snapshots_before_close2 = len(
            _rows(runtime2, riskfx.FILL_OBSERVER_RELEASE_SNAPSHOT_KIND)
        )
        close2_release_snapshot = riskfx._wait_for_release_snapshot(
            observer2, runtime2, release_snapshots_before_close2
        )
        assert close2_release_snapshot["verdict"] == "served"
        assert close2_release_snapshot["read_ok"] is True
        assert any(
            row["attempt_id"] == close2_attempt_id
            and row["egress_result_kind"] == "FULL_FILL"
            and Decimal(row["filled_quantity"]) == Decimal(6)
            and Decimal(row["remaining_quantity"]) == Decimal(0)
            for row in _rows(runtime2, "EGRESS_RESULT_CONSUMED")
        )

        close2_reservation_id = next(
            reservation_id
            for reservation_id, state in _reservation_states(runtime2).items()
            if reservation_id not in (entry_reservation_id, close1_reservation_id)
        )
        states_after_close2 = _reservation_states(runtime2)
        assert states_after_close2[entry_reservation_id] is CapacityState.RELEASED
        assert states_after_close2[close1_reservation_id] is CapacityState.RELEASED
        assert states_after_close2[close2_reservation_id] is CapacityState.RELEASED
        assert _release_count(runtime2, release_command_id(close1_attempt_id)) == 1
        assert _release_count(runtime2, release_command_id(close2_attempt_id)) == 1
        assert (
            _release_count(runtime2, entry_release_command_id(close1_attempt_id)) == 0
        )
        assert (
            _release_count(runtime2, entry_release_command_id(close2_attempt_id)) == 1
        )

        # A final public boot replays durable finality once more; no release command may be
        # appended a second time.
        _close(runtime2)
        runtime2 = None
        runtime3 = _boot(config_dir_with_risk_state, data_dir, custody_root, clock)
        assert runtime3 is not None
        assert runtime3.recovery is not None and runtime3.recovery.ready is True
        observer3 = runtime3.fill_observer
        assert observer3 is not None
        published3, _bridge3 = riskfx._capture_published(observer3)
        riskfx._script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row, close1_row, close2_row],
            holdings=(),
        )
        # The entry is already RELEASED, so replay must not schedule another held-position poll.
        assert published3 == []
        assert _reservation_states(runtime3)[entry_reservation_id] is (
            CapacityState.RELEASED
        )
        assert _release_count(runtime3, release_command_id(close1_attempt_id)) == 1
        assert _release_count(runtime3, release_command_id(close2_attempt_id)) == 1
        assert (
            _release_count(runtime3, entry_release_command_id(close1_attempt_id)) == 0
        )
        assert (
            _release_count(runtime3, entry_release_command_id(close2_attempt_id)) == 1
        )
    finally:
        for runtime in (runtime0, runtime1, runtime2, runtime3):
            if runtime is not None:
                _close(runtime)
