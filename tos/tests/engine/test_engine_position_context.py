"""``DecisionTickPayload.position_context`` + pipeline threading (plan P4 §2 D1/D5, S1)."""

from __future__ import annotations

import pytest
from tos.dsl import (
    POSITION_NAMESPACE,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    PositionContext,
    PositionSide,
    Rule,
    TargetKind,
    TargetSpec,
    project_position_context,
)
from tos.engine import (
    DecisionTickPayload,
    EngineEvent,
    EventKind,
    RegisteredStrategy,
)
from tos.engine.pipeline import run_decision_pipeline
from tos.engine.records import event_identity
from tos.engine.sink import RecordingEvidenceSink
from tos.engine.vocabulary import HaltReason

from ._engine_fixtures import (
    ACCOUNT,
    INSTRUMENT,
    SCHEME,
    admitting_time_inputs,
    authored_config,
    engine_configuration,
    instrument_key,
    issue_capsule,
    issue_strategy,
    ordering,
)

_ENTRY = 30_000
_ENTRY_AS_OF = 1_700_000_000_000
_STOP_BP = -50


def _position(*, price: int = _ENTRY - 300) -> PositionContext:
    """A held LONG position projected onto a bar whose price moved against it."""
    return project_position_context(
        side=PositionSide.LONG,
        held_qty=1,
        entry_price=_ENTRY,
        entry_price_basis="EXECUTION",
        entry_as_of=_ENTRY_AS_OF,
        price=price,
        as_of=_ENTRY_AS_OF + 300_000,
        bar_interval_ms=60_000,
        source_ref="ev-send-1",
        scheme=SCHEME,
    )


def _tick(*, position: PositionContext | None, sequence: int = 1) -> EngineEvent:
    """A ``DECISION_TICK`` event carrying (or not carrying) a projected position."""
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=instrument_key(),
            capsule=issue_capsule(),
            time=admitting_time_inputs(),
            reference=ordering(sequence),
            position_context=position,
        ),
    )


def _position_gated_policy() -> DecisionPolicy:
    """A declared stop-loss whose guard reads only the position namespace."""
    flat = Decision(
        kind=DecisionKind.FLAT,
        rationale="the declared stop-loss bound was reached — explicit flat",
        target=TargetSpec(
            kind=TargetKind.FLAT,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="SHORT",
            position_effect="CLOSE",
            rationale="the declared stop-loss bound was reached — explicit flat",
        ),
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=Operand(ref=("capsule", POSITION_NAMESPACE, "side")),
                        op=CompareOp.NE,
                        right=Operand(const=PositionSide.FLAT.value),
                    ),
                    Compare(
                        left=Operand(
                            ref=("capsule", POSITION_NAMESPACE, "unrealized_bp")
                        ),
                        op=CompareOp.LE,
                        right=Operand(ref=("config", "stop_loss_bp")),
                    ),
                ),
                decision=flat,
            ),
        ),
        default=Decision(
            kind=DecisionKind.NO_ACTION,
            rationale="no declared bound was reached — hold",
        ),
    )


def _run(position: PositionContext | None):
    """Run the decision pipeline for the position-gated strategy over one tick."""
    key = instrument_key()
    entry = RegisteredStrategy(
        strategy=issue_strategy(_position_gated_policy()),
        config=authored_config(bindings={"stop_loss_bp": _STOP_BP}),
        instrument_key=key,
    )
    payload = DecisionTickPayload(
        instrument_key=key,
        capsule=issue_capsule(),
        time=admitting_time_inputs(),
        position_context=position,
    )
    return run_decision_pipeline(
        entry=entry,
        payload=payload,
        configuration=engine_configuration(),
        scheme=SCHEME,
        sink=RecordingEvidenceSink(),
    )


def test_the_payload_carries_the_position_as_a_dsl_type() -> None:
    """(plan §10 ④) A dsl type, so the engine's import closure allowlist is untouched."""
    annotation = str(DecisionTickPayload.model_fields["position_context"].annotation)
    assert "PositionContext" in annotation
    assert "tos.position" not in annotation
    assert "marketfeed" not in annotation.lower()


def test_an_unset_position_is_left_out_of_every_dump() -> None:
    """(plan P4 완료 3) A tick without a position dumps exactly as it did before the field"""
    event = _tick(position=None)
    assert event.decision_tick is not None
    assert event.decision_tick.position_context is None
    dumped = event.model_dump(mode="json")
    assert "position_context" not in dumped["decision_tick"]
    legacy = EngineEvent.model_validate(dumped)
    assert event_identity(legacy, scheme=SCHEME) == event_identity(event, scheme=SCHEME)


def test_a_set_position_changes_the_event_identity() -> None:
    """(plan P4 §2 D5) What a decision read is in the event, so a position moves its identity."""
    without = _tick(position=None)
    with_position = _tick(position=_position())
    assert event_identity(without, scheme=SCHEME) != event_identity(
        with_position, scheme=SCHEME
    )
    dumped = with_position.model_dump(mode="json")["decision_tick"]["position_context"]
    assert dumped["side"] == "LONG"
    assert dumped["unrealized_bp"] == -100


def test_two_positions_that_differ_only_in_price_differ_in_identity() -> None:
    """(plan P4 §2 D1) The payload is the replay input — two bars must not collide."""
    assert event_identity(
        _tick(position=_position(price=_ENTRY - 300)), scheme=SCHEME
    ) != event_identity(_tick(position=_position(price=_ENTRY - 299)), scheme=SCHEME)


def test_the_pipeline_fires_the_declared_stop_loss_from_the_payload() -> None:
    """(plan P4 완료 1) The pipeline evaluates only what the payload carries — and it fires."""
    result = _run(_position())
    assert result.proposal is not None
    assert result.proposal.target_kind is TargetKind.FLAT
    assert result.signature is not None
    assert _position().canonical_digest in result.signature.captured_external_value_refs


@pytest.mark.parametrize("price", [_ENTRY - 149, _ENTRY + 300])
def test_the_pipeline_holds_while_the_declared_bound_is_not_reached(price: int) -> None:
    """(dsl/vocabulary evaluate_policy) The default decision stands — no proposal is built."""
    result = _run(_position(price=price))
    assert result.proposal is None
    assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME


def test_without_a_position_a_position_gated_guard_cannot_fire() -> None:
    """(plan P4 §2 D3, 완료 3) Absence narrows: no namespace ⇒ UNKNOWN ⇒ comparison False."""
    result = _run(None)
    assert result.proposal is None
    assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME
