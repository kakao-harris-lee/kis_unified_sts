"""Boot replay re-derives a position-gated decision from the inbox payload (plan P4 §2 D1)."""

from __future__ import annotations

import json

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import (
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    NoActionOutcome,
    Operand,
    PositionContext,
    PositionSide,
    Rule,
    TargetKind,
    TargetSpec,
    project_position_context,
)
from tos.engine import DecisionTickPayload, EngineEvent, EventKind
from tos_runtime.compose._boot_integrity import verify_engine_replay_or_halt
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from .conftest import FakeMonotonicSource

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_NO_TIMEOUT_WITHIN_TEST = 10**12

_STOP_LOSS_BP = -50
_BAR_MS = 60_000
_ENTRY_AS_OF = 1_700_000_060_000
_ENTRY_PRICE = 7_010_000
_BAR_PRICE = 6_939_900


def _position_gated_policy() -> DecisionPolicy:
    """``capsule.position.unrealized_bp <= config bound`` -> act; else a defined no-action."""
    rationale = "position-gated exit — unrealized_bp pierced the declared bound"
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale=rationale,
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=fx.ACCOUNT,
            instrument=fx.INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale=rationale,
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="position bound not pierced")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "position", "unrealized_bp")),
                op=CompareOp.LE,
                right=Operand(const=_STOP_LOSS_BP),
            ),
        ),
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def _held_context(*, price: int = _BAR_PRICE, as_of: int) -> PositionContext:
    return project_position_context(
        side=PositionSide.LONG,
        held_qty=1,
        entry_price=_ENTRY_PRICE,
        entry_price_basis="ORDER",
        entry_as_of=_ENTRY_AS_OF,
        price=price,
        as_of=as_of,
        bar_interval_ms=_BAR_MS,
        source_ref="attempt:boot-integrity-entry@rcl:1:7",
        scheme=SCHEME,
    )


def _tick_with_position(
    *, seq: int, context: PositionContext | None
) -> tuple[EngineEvent, PositionContext | None]:
    """The fixture tick event, rebuilt (never ``model_copy``) with ``context`` aboard."""
    base = fx.decision_tick_event(seq=seq)
    assert base.decision_tick is not None
    payload = base.decision_tick
    return (
        EngineEvent(
            kind=EventKind.DECISION_TICK,
            decision_tick=DecisionTickPayload(
                instrument_key=payload.instrument_key,
                capsule=payload.capsule,
                time=payload.time,
                reference=payload.reference,
                value_view=payload.value_view,
                position_context=context,
            ),
        ),
        context,
    )


def _driver(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> EngineDriver:
    return EngineDriver(
        core=fx.build_core(
            registry=fx.registry_with(_position_gated_policy()),
            stages=fx.admitting_stages(),
            transmit=fx.FakeGateway(),
            sink=EngineEvidenceSinkAdapter(evidence_store),
        ),
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="position-context-boot-integrity",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )


def _replay_build_core(evidence_store: SqliteEvidenceStore):
    """``_engine_wiring``'s own replay-core shape, with the SAME position-gated registry."""

    def factory():
        recorded_stage = RecordedStage(evidence_store)
        core = fx.build_core(
            registry=fx.registry_with(_position_gated_policy()),
            stages=dict.fromkeys(fx.admitting_stages(), recorded_stage),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
        )
        return EventCorrelatingCore(
            core=core, recorded_stage=recorded_stage, scheme=SCHEME
        )

    return factory


def _recorded_outcome_digests(evidence_store: SqliteEvidenceStore) -> list[object]:
    return [
        json.loads(row[0])["payload"].get("outcome_digest")
        for row in evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' ORDER BY seq"
        )
    ]


def test_a_position_gated_decision_replays_from_the_payload_alone(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """D-a: -70_100 over 7_010_000 is -100 bp, so the rule fires; the replay must reproduce it."""
    driver = _driver(inbox, evidence_store, emergency_log)
    event, context = _tick_with_position(
        seq=1, context=_held_context(as_of=_ENTRY_AS_OF + 3 * _BAR_MS)
    )
    assert context is not None and context.unrealized_bp == -100
    result = driver.enqueue_and_run(event)
    assert result.flow is not None and result.flow.handed_off is True
    recorded = _recorded_outcome_digests(evidence_store)
    assert any(recorded), recorded

    # SAFETY: the evidence gains a later sealed send AFTER the tick — a live re-read would now answer differently, and the replay below must still reproduce the recorded decision
    evidence_store.append(
        {
            "kind": "SEND_SEALED",
            "attempt_id": "attempt-after-the-tick",
            "send_seal": {
                "attempt_id": "attempt-after-the-tick",
                "instrument_key": {
                    "account": fx.ACCOUNT,
                    "instrument": fx.INSTRUMENT,
                },
                "outbound_side": "SELL",
                "outbound_quantity": "1",
                "outbound_price": _BAR_PRICE,
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )

    verdict = verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=100,
    )
    assert verdict.ok
    assert verdict.diverged == ()
    assert verdict.total_compared == 1
    assert _recorded_outcome_digests(evidence_store) == recorded


def test_the_same_tick_without_a_position_decides_differently(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Control: the recorded decision genuinely DEPENDS on the payload's position context."""
    driver = _driver(inbox, evidence_store, emergency_log)
    event, _context = _tick_with_position(seq=1, context=None)
    result = driver.enqueue_and_run(event)
    assert result.pipeline is not None
    assert isinstance(result.pipeline.outcome, NoActionOutcome)
    assert result.flow is None

    verdict = verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_build_core(evidence_store),
        scheme=SCHEME,
        window_events=100,
    )
    assert verdict.ok
    assert verdict.diverged == ()
