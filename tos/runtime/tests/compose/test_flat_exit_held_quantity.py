"""Issue #1025 — a FLAT exit's held quantity is the DURABLE entry remainder, end to end."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.dsl import FLAT_QUANTITY_BASIS
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime

from . import _fixtures as fx
from . import _symmetry_fixtures as sfx
from .conftest import write_approval_file
from .test_compose_root import _reach_trusted
from .test_synthetic_close_bound_inert import _hand_off_a_filled_entry
from .test_synthetic_venue_ledger_e2e import _close_runtime, _reservations, _rows
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_BAND_ONLY_MAPPING = fx.band_reversion_strategy_mapping

_ENVIRONMENT_LABEL = "non-live-test"


def admit_the_flat_basis(config_dir: Path) -> Path:
    """Add the kernel's FLAT token to this tree's ``admitted_quantity_bases``."""
    path = config_dir / "order_construction_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert 'admitted_quantity_bases: ["RISK"]' in text, text
    path.write_text(
        text.replace(
            'admitted_quantity_bases: ["RISK"]',
            f'admitted_quantity_bases: ["RISK", "{FLAT_QUANTITY_BASIS}"]',
        ),
        encoding="utf-8",
    )
    return path


def _flat_exit_rule(*, direction: str) -> dict[str, Any]:
    """``close > upper_band`` -> go FLAT, in the shipped Setup D R2/R3 shape."""
    rationale = f"close pierced the upper band — FLAT exit ({direction})"
    return {
        "all_of": [
            {
                "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                "op": "GT",
                "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
            }
        ],
        "decision": {
            "kind": "FLAT",
            "rationale": rationale,
            "target": {
                "kind": "FLAT",
                "account": fx.ACCOUNT,
                "instrument": fx.INSTRUMENT,
                "direction": direction,
                "position_effect": "CLOSE",
                "rationale": rationale,
            },
        },
    }


def _long_entry_flat_exit_mapping() -> dict[str, object]:
    mapping = _BAND_ONLY_MAPPING()
    mapping["policy"]["rules"].append(_flat_exit_rule(direction="SHORT"))  # type: ignore[index]
    return mapping


def _short_entry_flat_exit_mapping() -> dict[str, object]:
    """The mirrored SHORT entry plus a FLAT exit whose closing action is ``LONG`` (-> BUY)."""
    mapping = sfx.mirrored_strategy_mapping()
    mapping["policy"]["rules"].append(_flat_exit_rule(direction="LONG"))  # type: ignore[index]
    return mapping


def _sides(runtime) -> list[str]:
    """Every sealed outbound side this process sent, in order."""
    return [row["send_seal"]["outbound_side"] for row in _rows(runtime, "SEND_SEALED")]


def _step2(result):
    assert result.flow is not None
    (verdict,) = [
        v
        for v in result.flow.verdicts
        if v.step is CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION
    ]
    return verdict


def _derived_quantity(runtime) -> Decimal | None:
    construction = runtime.construction_stage.construction
    assert construction is not None
    quantity: Decimal | None = construction.derivation.quantity
    return quantity


def _boot_synthetic(
    config_dir: Path, data_dir: Path, custody_root: Path, *, construction=None
):
    """A real synthetic boot with the PRODUCTION step-6/7 risk-state service."""
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        _ENVIRONMENT_LABEL,
        construction=fx.construction_config() if construction is None else construction,
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )


def _approve_and_run(runtime, custody_root: Path, event):
    """Discover, write the operator approval for that exact proposal, then run it for real."""
    (discovery,) = runtime.run_once((event,))
    assert discovery.pipeline is not None and discovery.pipeline.proposal is not None
    construction = runtime.construction_stage.construction
    if construction is None or construction.intent is None:
        return discovery, None
    write_approval_file(
        custody_root,
        proposal_digest=discovery.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    (result,) = runtime.run_once((event,))
    return discovery, result


def _exit_tick(seq: int):
    return fx.crossing_event(seq=seq, close=fx.UPPER_BAND + 1_000)


def test_a_synthetic_long_flat_exit_sends_a_sell_and_releases_both_reservations(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry -> fill -> FLAT exit -> fill, on a LONG tree, with no held-position stand-in."""
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)

        _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(runtime)
        assert entry_quantity is not None and entry_quantity > 0
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(runtime)

        discovery, exit_ = _approve_and_run(runtime, custody_root, _exit_tick(1))
        proposal = discovery.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
        assert _step2(discovery).outcome is StageOutcome.ADMIT, _step2(discovery).reason
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail

        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["BUY", "SELL"], _sides(runtime)

        for _ in range(3):
            runtime.run_once(())
        after = _reservations(runtime)
        assert len(after) == 2, after
        assert {state for _id, state in after} == {CapacityState.RELEASED}, after
    finally:
        _close_runtime(runtime)


def test_a_synthetic_short_flat_exit_sends_a_buy_and_releases_both_reservations(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The long/short symmetry half: a SHORT tree's FLAT exit must be a **BUY**."""
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _short_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    ocp = config_dir_with_risk_state / "order_construction_policy.yaml"
    text = ocp.read_text(encoding="utf-8")
    long_axis = '- axis: "DIRECTION"\n        value: "LONG"'
    assert text.count(long_axis) == 1, text
    ocp.write_text(
        text.replace(long_axis, '- axis: "DIRECTION"\n        value: "SHORT"'),
        encoding="utf-8",
    )
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        construction=sfx.mirrored_construction_config(),
    )
    try:
        _reach_trusted(runtime)

        _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(runtime)
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(runtime)

        discovery, exit_ = _approve_and_run(runtime, custody_root, _exit_tick(1))
        proposal = discovery.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert (proposal.position_effect, proposal.direction) == ("CLOSE", "LONG")
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail
        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["SELL", "BUY"], _sides(runtime)

        for _ in range(3):
            runtime.run_once(())
        after = _reservations(runtime)
        assert len(after) == 2, after
        assert {state for _id, state in after} == {CapacityState.RELEASED}, after
    finally:
        _close_runtime(runtime)


@pytest.fixture()
def server():
    from ..transport.kis_mock._fake_kis_server import FakeKisServer

    instance = FakeKisServer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def test_the_stock_transport_sends_the_flat_exit_through_the_standing_boundary(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server,
) -> None:
    """The stock tree's transport: entry ACK -> fill -> FLAT exit ACK, over the fake KIS server."""
    from .test_close_proposal_e2e import (
        _boot,
        _Broker,
        _entry_tick,
        _order_response,
        _standing_cycle_artifact,
    )
    from .test_kis_mock_fill_finality_e2e import _close, _deploy

    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    _deploy(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    admit_the_flat_basis(config_dir)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)
    try:
        _order_response(server, "0000000201")
        (entry,) = runtime.run_once((_entry_tick(),))
        assert entry.flow is not None and entry.flow.handed_off is True
        entry_quantity = _derived_quantity(runtime)
        assert entry_quantity is not None and entry_quantity > 0
        broker.fill(runtime, odno="0000000201")

        _order_response(server, "0000000202")
        (exit_,) = runtime.run_once((_exit_tick(1),))
        proposal = exit_.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert _step2(exit_).outcome is StageOutcome.ADMIT, _step2(exit_).reason
        assert (
            exit_.flow is not None and exit_.flow.handed_off is True
        ), exit_.flow.detail
        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["BUY", "SELL"], _sides(runtime)
    finally:
        _close(runtime)


_NO_HELD_POSITION = "closes a position but no held position was observed"


def test_a_flat_proposal_on_a_flat_scope_is_refused_at_step_2_and_sends_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No position, so nothing to close: the SAME outcome as before #1025, a different reason."""
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        (result,) = runtime.run_once((_exit_tick(0),))
        assert result.pipeline is not None and result.pipeline.proposal is not None
        assert result.pipeline.proposal.quantity_basis == FLAT_QUANTITY_BASIS
        verdict = _step2(result)
        assert verdict.outcome is StageOutcome.DENY, verdict.reason
        assert _NO_HELD_POSITION in (verdict.reason or ""), verdict.reason
        assert result.flow is not None and result.flow.handed_off is not True
        assert _sides(runtime) == []
        assert _reservations(runtime) == []
    finally:
        _close_runtime(runtime)


def test_an_uncorroborated_entry_fill_refuses_the_flat_exit_and_sends_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The venue-ledger-OFF tree — the kis-mock stock tree since the #1053 switch-on, and any tree the key is removed from — still refuses the exit."""
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.COMMITTED_UNBOUND
        ], _reservations(runtime)
        held = _rows(runtime, "CAPACITY_RELEASE_HELD")
        assert [row["reason"] for row in held] == ["WITNESS_NOT_INDEPENDENT"], held

        sealed_before = len(_sides(runtime))
        (result,) = runtime.run_once((_exit_tick(1),))
        verdict = _step2(result)
        assert verdict.outcome is StageOutcome.DENY, verdict.reason
        assert _NO_HELD_POSITION in (verdict.reason or ""), verdict.reason
        assert len(_sides(runtime)) == sealed_before
    finally:
        _close_runtime(runtime)


def test_a_restart_after_the_entry_fill_sizes_the_flat_from_the_durable_entry(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence that step 2 no longer depends on the in-memory ledger at all."""
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)

    first = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(first)
        _, entry = _approve_and_run(first, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(first)
        assert entry_quantity is not None and entry_quantity > 0
        for _ in range(3):
            first.run_once(())
        assert [state for _id, state in _reservations(first)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(first)
    finally:
        _close_runtime(first)

    second = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(second)
        discovery, exit_ = _approve_and_run(second, custody_root, _exit_tick(1))
        assert discovery.pipeline.proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert _step2(discovery).outcome is StageOutcome.ADMIT, _step2(discovery).reason
        assert _derived_quantity(second) == entry_quantity
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail
        assert _sides(second)[-1] == "SELL", _sides(second)
    finally:
        _close_runtime(second)
