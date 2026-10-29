"""Regression for issue #1004: a stale consumed entry must not authorize an over-close.

The counterexample's broker is already flat, but its local durable evidence still records the
10-contract entry fill and the RCL still has the corresponding POSITION_CONSUMED reservation.
The production risk-state service has no broker-position input, so it sees only those stale
local facts. With the current unconditional ``-q`` CLOSE effect, it can project usage below zero
and GRANT a 10-contract close even though the configured risk limit is 1.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.core import EventResult
from tos.engine.records import StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import (
    AppendReceipt,
    CapacityComponent,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot
from tos_runtime.riskstate.policies import load_aggregate_risk_policy

from . import _fixtures as fx
from .conftest import write_approval_file

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = fx.ACCOUNT
_INSTRUMENT = fx.INSTRUMENT
_ENTRY_QUANTITY = Decimal("10")
_ARE_LIMIT = Decimal("1")


class _IndependentFlatBrokerWitness:
    """Test broker provider whose complete, independent snapshot reports this scope flat."""

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=scope.as_of_generation,
            orders=(),
            positions=(),
            positions_complete=True,
            provenance="test-independent-flat-broker",
            independent_of_evidence_store=True,
        )


def _close_rule() -> dict[str, object]:
    rationale = "close crossed the upper band — flat-account regression"
    return {
        "all_of": [
            {
                "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                "op": "GT",
                "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
            }
        ],
        "decision": {
            "kind": "ACTION",
            "rationale": rationale,
            "target": {
                "kind": "ACTION",
                "account": _ACCOUNT,
                "instrument": _INSTRUMENT,
                "direction": "SHORT",
                "position_effect": "CLOSE",
                "quantity_basis": "RISK",
                "edge_or_confidence": "close-risk-flat-regression",
                "rationale": rationale,
            },
        },
    }


def _write_close_strategy(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = fx.band_reversion_strategy_mapping

    def close_strategy_mapping() -> dict[str, object]:
        mapping = original()
        policy = mapping["policy"]
        assert isinstance(policy, dict)
        rules = policy["rules"]
        assert isinstance(rules, list)
        rules.append(_close_rule())
        return mapping

    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", close_strategy_mapping)
    fx.write_band_strategy_file(config_dir)


def _set_effective_limit(config_dir: Path, limit: Decimal) -> str:
    """Set the opt-in compose fixture's ARE limit and keep its activated digest aligned."""
    are_path = config_dir / "aggregate_risk_policy.yaml"
    raw = yaml.safe_load(are_path.read_text(encoding="utf-8"))
    effective_limits = raw["_runtime"]["effective_limits"]
    assert isinstance(effective_limits, dict) and len(effective_limits) == 1
    dimension_id = next(iter(effective_limits))
    assert isinstance(dimension_id, str)
    effective_limits[dimension_id] = str(limit)
    raw["canonical_digest"] = "TBD"
    are_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    loaded = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    activation_path = config_dir / "safety_activation.yaml"
    activation = yaml.safe_load(activation_path.read_text(encoding="utf-8"))
    members = activation["members"]
    are_members = [m for m in members if m["kind"] == "AGGREGATE_RISK_POLICY"]
    assert len(are_members) == 1
    are_members[0]["digest"] = loaded.policy.canonical_digest
    activation_path.write_text(
        yaml.safe_dump(activation, sort_keys=False), encoding="utf-8"
    )
    return dimension_id


def _seed_durable_entry_fill(runtime: ComposedRuntime, *, quantity: Decimal) -> None:
    attempt_id = "prior-entry-fill"
    instrument_key = {"account": _ACCOUNT, "instrument": _INSTRUMENT}
    runtime.evidence_store.append(
        {
            "kind": "SEND_SEALED",
            "attempt_id": attempt_id,
            "send_seal": {
                "instrument_key": instrument_key,
                "outbound_side": "BUY",
                "outbound_quantity": str(quantity),
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )
    runtime.evidence_store.append(
        {
            "kind": "EGRESS_RESULT_CONSUMED",
            "attempt_id": attempt_id,
            "instrument_key": instrument_key,
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": str(quantity),
            "remaining_quantity": "0",
            "result_disposition": "APPLIED",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )


def _seed_position_consumed_reservation(
    runtime: ComposedRuntime, *, quantity: Decimal, dimension_id: str
) -> None:
    view = runtime.rcl_log.read_linearizable(writer_epoch=runtime.writer_epoch)
    expected_seq = -1 if view.last_seq is None else view.last_seq
    transition = CapacityReservationTransition(
        reservation_id="prior-entry-reservation",
        writer_epoch=runtime.writer_epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.POSITION_CONSUMED,
        scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        committed_vector=CapacityVector(
            components=(
                CapacityComponent(dimension_id=dimension_id, magnitude=quantity),
            )
        ),
    )
    result = runtime.rcl_log.apply_reservation_transition(
        transition,
        TransitionCause.FINAL_QUANTITY_PROOF,
        command_type=CommandType.RELEASE_RESERVATION,
        command_id="cmd-prior-entry-position-consumed",
        command_digest="digest-prior-entry-position-consumed",
        expected_seq=expected_seq,
        finality_witness=True,
    )
    assert isinstance(result, AppendReceipt)


def _verdict(result: EventResult, step: CommitmentStep) -> StageVerdict:
    assert result.flow is not None
    (verdict,) = [item for item in result.flow.verdicts if item.step is step]
    return verdict


def test_flat_broker_and_stale_position_consumed_entry_do_not_admit_overclose(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker-side position is 0, but local evidence/RCL still show the entry's 10.

    The CLOSE's derived quantity is 10, greater than the 1-unit ARE limit. A negative effect
    of -10 then turns ``10 + (-10)`` into zero and the actual production step 6 GRANTs; since
    there is no broker-position input at pretrade, that GRANT would sell into a flat account.
    """
    _write_close_strategy(config_dir_with_risk_state, monkeypatch)
    dimension_id = _set_effective_limit(config_dir_with_risk_state, _ARE_LIMIT)
    runtime = compose_paper_runtime(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    assert runtime.risk_state is not None

    event = fx.crossing_event(seq=0, close=fx.UPPER_BAND + 1_000)
    (discovery,) = runtime.run_once((event,))
    assert discovery.pipeline is not None
    proposal = discovery.pipeline.proposal
    assert proposal is not None and isinstance(proposal.canonical_digest, str)
    assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    quantity = construction.derivation.quantity
    assert construction.intent is not None
    assert isinstance(construction.intent.canonical_digest, str)
    assert quantity == _ENTRY_QUANTITY
    assert quantity > _ARE_LIMIT
    write_approval_file(
        custody_root,
        proposal_digest=proposal.canonical_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )

    # A separate broker provider answers flat, but RiskStateService/build_risk_state_service
    # have no witness input. No corresponding egress result is added for the out-of-band
    # flatten, so production step 6 only sees its stale local 10.
    broker_snapshot = _IndependentFlatBrokerWitness().observe(
        WitnessScope(
            account=_ACCOUNT,
            instrument_keys=(fx.instrument_key(),),
            as_of_generation=1,
        )
    )
    assert broker_snapshot.positions_complete is True
    assert broker_snapshot.independent_of_evidence_store is True
    assert broker_snapshot.positions == ()
    _seed_durable_entry_fill(runtime, quantity=quantity)
    _seed_position_consumed_reservation(
        runtime, quantity=quantity, dimension_id=dimension_id
    )

    (close_result,) = runtime.run_once((event,))
    step6 = _verdict(close_result, CommitmentStep.AGGREGATE_RISK_DECISION)
    assert step6.outcome is StageOutcome.UNKNOWN, (
        "without a complete, fresh, independent per-attempt broker-held-quantity proof, "
        "CLOSE must stay UNKNOWN even though local fills look risk-reducing: "
        f"{step6.outcome.value} ({step6.reason})"
    )
