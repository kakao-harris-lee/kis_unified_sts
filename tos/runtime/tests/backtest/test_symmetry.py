"""Long/short structural symmetry through the ``tos.backtest`` driver (TOS Phase 5 W5 plan"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tos.backtest import (
    BacktestDriver,
    BacktestRun,
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    ExecutionPriceBasis,
    FillMode,
    FillParameters,
    FillSide,
    NonBrokerTransportNature,
    ProvisionalContextResolver,
    SettlementPolicy,
    SyntheticNonLivePreconditions,
    TraceEntry,
    reference_bars,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import (
    AuthoredStrategy,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.engine import (
    EngineConfiguration,
    EngineCore,
    InstrumentKey,
    RecordingEvidenceSink,
    StrategyRegistry,
    provisional_stage_map,
)
from tos.time import HealthState, SessionContext

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-symmetry"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
CONTINUITY_ID_PREFIX = "symmetry-stream"

PROOF_DIGEST = "proof-digest-symmetry"
PERMIT_IDENTITY = "permit-symmetry"

PROVISIONAL_BUDGET_STEPS = 64
PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

_LONG = ("LONG", FillSide.BUY)
_SHORT = ("SHORT", FillSide.SELL)


def _instrument_key() -> InstrumentKey:
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def _issue_capsule(direction: str) -> DecisionContextCapsule:
    """Issue the mirrored-direction Decision Context Capsule for this scope."""
    return DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-symmetry",
        critical_input_policy=PolicyRef(
            policy_id="pol-symmetry", canonical_digest="pd-symmetry"
        ),
        critical_input_snapshot=SnapshotRef(
            snapshot_id="cis-symmetry", canonical_digest="sd-symmetry"
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class=DECISION_CLASS,
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction=direction,
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def _capsule_source(direction: str) -> Any:
    """The injected per-bar Capsule source for one side (same content on every bar — design #33"""

    def _source(
        bar: Any,
    ) -> DecisionContextCapsule:  # noqa: ARG001 - the slot takes the bar
        return _issue_capsule(direction)

    return _source


def _mirrored_policy(direction: str) -> DecisionPolicy:
    """A single-rule policy whose fired decision opens the mirrored ``direction`` — the SHORT/SELL"""
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale=f"{direction} entry — W5 symmetry harness",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction=direction,
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale=f"{direction} entry — W5 symmetry harness",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="guard did not fire — hold")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "scope", "decision_class")),
                op=CompareOp.EQ,
                right=Operand(const=DECISION_CLASS),
            ),
        ),
        decision=entry,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def _issue_strategy(direction: str) -> AuthoredStrategy:
    return AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-symmetry",
        config_binding_version="cfg-bind-symmetry",
        policy=_mirrored_policy(direction),
    )


def _registry_with(direction: str) -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(
        _issue_strategy(direction),
        EvaluationConfig(config_version="cfg-symmetry", bindings={"band_k": 2}),
    )
    return registry


def _engine_configuration() -> EngineConfiguration:
    return EngineConfiguration(
        dsl_evaluation_budget_steps=PROVISIONAL_BUDGET_STEPS,
        max_unresolved_send_per_scope=PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        enforcement_mechanism_version="enf-symmetry",
    )


def _time_projection() -> BarTimeProjection:
    return BarTimeProjection(
        source_age=10,
        delay_bounds=(5,),
        max_age_bound=1000,
        future_tolerance=50,
        snapshot_age_bound=20,
        maximum_consumer_age_ms=1000,
        interval_width=2,
        boundary_lag=10,
        session_template=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=0,
        ),
        health_state=HealthState.TRUSTED,
    )


def _fill_parameters(side: FillSide) -> FillParameters:
    """A settled fill, mirrored only in ``side`` — every magnitude/price/cost value is the exact"""
    return FillParameters(
        mode=FillMode.SETTLE,
        side=side,
        settlement=SettlementPolicy.SAME_BAR,
        price_basis=ExecutionPriceBasis.CLOSE,
        scenario_quantity=Decimal(10),
        participation_cap_fraction=Decimal("0.5"),
        slippage_bps=Decimal(5),
        cost_per_unit=Decimal("0.02"),
        limit_reference_price=Decimal(100),
        price_band_fraction=Decimal("0.05"),
    )


def _run_side(direction: str, side: FillSide) -> BacktestRun:
    """Replay one bar of the shared synthetic feed through a fresh core, for one mirrored side."""
    fill_model = DeterministicFillModel(
        instrument_key=_instrument_key(),
        parameters=_fill_parameters(side),
    )
    converter = CausalBarConverter(
        instrument_key=_instrument_key(),
        resolver=ProvisionalContextResolver(),
        capsule_source=_capsule_source(direction),
        time_projection=_time_projection(),
    )
    driver = BacktestDriver(
        converter=converter,
        fill_model=fill_model,
        continuity_id=CONTINUITY_ID_PREFIX,
    )
    core = EngineCore(
        registry=_registry_with(direction),
        stages=provisional_stage_map(
            conformance_proof_digest=PROOF_DIGEST,
            action_flow_permit_identity=PERMIT_IDENTITY,
        ),
        configuration=_engine_configuration(),
        preconditions=SyntheticNonLivePreconditions(authority_epoch_current=True),
        transmit=fill_model,
        transport_nature=NonBrokerTransportNature(),
        sink=RecordingEvidenceSink(),
    )
    return driver.run(core, reference_bars(1))


_SIDE_BEARING_TRACE_FIELDS = frozenset({"proposal_digest", "outcome_digest"})


def _structural_view(entry: TraceEntry) -> dict[str, Any]:
    """``entry`` with the side-bearing (digest) fields stripped, for a structure-only comparison."""
    return {
        field: value
        for field, value in vars(entry).items()
        if field not in _SIDE_BEARING_TRACE_FIELDS
    }


def test_mirrored_sides_yield_the_same_event_and_evidence_shape() -> None:
    """(decision 8) Same feed, mirrored side: every trace entry matches field-for-field except"""
    long_run = _run_side(*_LONG)
    short_run = _run_side(*_SHORT)

    assert long_run.bars_consumed == short_run.bars_consumed
    assert long_run.events_yielded == short_run.events_yielded
    assert [e.event_kind for e in long_run.trace.entries] == [
        e.event_kind for e in short_run.trace.entries
    ]
    assert len(long_run.trace.entries) == len(short_run.trace.entries)
    for long_entry, short_entry in zip(long_run.trace.entries, short_run.trace.entries):
        assert _structural_view(long_entry) == _structural_view(
            short_entry
        ), f"non-digest trace fields diverged between sides: {long_entry} vs {short_entry}"

    assert [h.halt_reason for h in long_run.halts] == [
        h.halt_reason for h in short_run.halts
    ]
    assert long_run.handoff_count == short_run.handoff_count


def test_mirrored_sides_digests_actually_differ_side_is_bound_into_them() -> None:
    """(decision 8, mutation M6's mirror) The digests are *supposed* to differ — direction is"""
    long_run = _run_side(*_LONG)
    short_run = _run_side(*_SHORT)

    long_digest_entries = [
        e for e in long_run.trace.entries if e.proposal_digest is not None
    ]
    short_digest_entries = [
        e for e in short_run.trace.entries if e.proposal_digest is not None
    ]
    assert long_digest_entries and short_digest_entries, (
        "the scenario must produce at least one proposal digest on each side for this pin to "
        "mean anything"
    )
    assert [e.proposal_digest for e in long_digest_entries] != [
        e.proposal_digest for e in short_digest_entries
    ]
    assert [e.outcome_digest for e in long_run.trace.entries] != [
        e.outcome_digest for e in short_run.trace.entries
    ]
    assert [e.attempt_id for e in long_run.trace.entries] == [
        e.attempt_id for e in short_run.trace.entries
    ]


def test_fill_records_are_identical_except_the_side_field() -> None:
    """(decision 8) The settled fill's quantity/cost apparatus never reads ``side`` for anything"""
    long_run = _run_side(*_LONG)
    short_run = _run_side(*_SHORT)

    (long_fill,) = long_run.fill_records
    (short_fill,) = short_run.fill_records

    assert long_fill.side is FillSide.BUY
    assert short_fill.side is FillSide.SELL
    assert long_fill.attempt_id == short_fill.attempt_id, (
        "attempt_id is scope-derived (same account/instrument/bar slot), not digest-derived — "
        "it stays identical across the mirrored sides"
    )

    assert long_fill.reference_price == short_fill.reference_price
    assert long_fill.execution_price is not None
    assert long_fill.reference_price is not None
    assert short_fill.execution_price is not None
    assert short_fill.reference_price is not None
    long_deviation = long_fill.execution_price - long_fill.reference_price
    short_deviation = short_fill.execution_price - short_fill.reference_price
    assert long_deviation == -short_deviation
    assert long_deviation != 0

    mirrored = long_fill.model_copy(
        update={"side": short_fill.side, "execution_price": short_fill.execution_price}
    )
    assert mirrored == short_fill, (
        "a LocalFillRecord that differs only in `side` and the (symmetric) `execution_price` "
        "after being mirrored is exactly the 'fill/step structure identical' contract decision "
        f"8 asks for — full mirrored record: {mirrored!r}\nfull short record: {short_fill!r}"
    )
