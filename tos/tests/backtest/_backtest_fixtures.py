"""Shared builders for the ``tos.backtest`` authoring-evidence suite (design #33 §8)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError
from tos.backtest import (
    BacktestDriver,
    BacktestIntegrityError,
    BacktestRun,
    BarStream,
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    FillParameters,
    MultiSymbolBacktestDriver,
    NonBrokerTransportNature,
    ProvisionalContextResolver,
    ScenarioSpec,
    SyntheticNonLivePreconditions,
    reference_bars,
    validate_bar_stream,
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
    CommitmentStep,
    EngineConfiguration,
    EngineCore,
    InstrumentKey,
    RecordingEvidenceSink,
    Stage,
    StrategyRegistry,
    provisional_stage_map,
)
from tos.time import HealthState, SessionContext

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-bt"
INSTRUMENT = "ES"
INSTRUMENT_B = "NQ"
DECISION_CLASS = "entry"
CONTINUITY_ID = "backtest-stream-0"

PROVISIONAL_BUDGET_STEPS = 64
PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

PROOF_DIGEST = "proof-digest-bt"
PERMIT_IDENTITY = "permit-bt"

INTEGRITY_ERRORS = (BacktestIntegrityError, ValidationError)


def instrument_key(
    account: str = ACCOUNT, instrument: str = INSTRUMENT
) -> InstrumentKey:
    """The dispatch key used across the suite."""
    return InstrumentKey(account=account, instrument=instrument)


def issue_capsule(
    *, instrument: str = INSTRUMENT, **overrides: Any
) -> DecisionContextCapsule:
    """Issue a valid Decision Context Capsule scoped to the suite's account and ``instrument``."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-bt",
        "critical_input_policy": PolicyRef(
            policy_id="pol-bt", canonical_digest="pd-bt"
        ),
        "critical_input_snapshot": SnapshotRef(
            snapshot_id="cis-bt", canonical_digest="sd-bt"
        ),
        "scope": CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument=instrument,
            decision_class=DECISION_CLASS,
        ),
        "safety_critical_facts": SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=instrument,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    }
    base.update(overrides)
    return DecisionContextCapsule.issue(scheme=SCHEME, **base)


def capsule_source(
    bar: Any,
) -> DecisionContextCapsule:  # noqa: ARG001 - the slot takes the bar
    """The injected per-bar Capsule source."""
    return issue_capsule()


def capsule_source_for(instrument: str) -> Any:
    """One lane's injected per-bar Capsule source (design #37 §3.2)."""

    def _source(
        bar: Any,
    ) -> DecisionContextCapsule:  # noqa: ARG001 - the slot takes the bar
        return issue_capsule(instrument=instrument)

    return _source


def capsule_gated_policy(
    *,
    target_kind: TargetKind = TargetKind.ACTION,
    fires: bool = True,
    instrument: str = INSTRUMENT,
) -> DecisionPolicy:
    """A policy whose single guard reads a **capsule-sourced** operand (design #31 §3.2 (3))."""
    if target_kind is TargetKind.FLAT:
        decision = Decision(
            kind=DecisionKind.FLAT,
            rationale="capsule-sourced guard fired — explicit flat",
            target=TargetSpec(
                kind=TargetKind.FLAT,
                account=ACCOUNT,
                instrument=instrument,
                direction="SHORT",
                position_effect="CLOSE",
                rationale="capsule-sourced guard fired — explicit flat",
            ),
        )
    else:
        decision = Decision(
            kind=DecisionKind.ACTION,
            rationale="capsule-sourced guard fired",
            target=TargetSpec(
                kind=TargetKind.ACTION,
                account=ACCOUNT,
                instrument=instrument,
                direction="LONG",
                position_effect="OPEN",
                quantity_basis="RISK",
                edge_or_confidence="0.7",
                rationale="capsule-sourced guard fired",
            ),
        )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="guard did not fire — hold")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "scope", "decision_class")),
                op=CompareOp.EQ,
                right=Operand(const=DECISION_CLASS if fires else "no-such-class"),
            ),
        ),
        decision=decision,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def issue_strategy(
    policy: DecisionPolicy | None = None, **overrides: Any
) -> AuthoredStrategy:
    """Issue a valid Authored Strategy carrying ``policy`` (a capsule-gated one by default)."""
    base: dict[str, Any] = {
        "dsl_version": "dsl-bt",
        "config_binding_version": "cfg-bind-bt",
        "policy": policy if policy is not None else capsule_gated_policy(),
    }
    base.update(overrides)
    return AuthoredStrategy.issue(scheme=SCHEME, **base)


def authored_config(**overrides: Any) -> EvaluationConfig:
    """The authored constants a strategy reads — never a market-derived value (design #31 §3.2)."""
    base: dict[str, Any] = {"config_version": "cfg-bt", "bindings": {"band_k": 2}}
    base.update(overrides)
    return EvaluationConfig(**base)


def engine_configuration(**overrides: Any) -> EngineConfiguration:
    """The injected engine configuration (every value provisional — design #33 §10)."""
    base: dict[str, Any] = {
        "dsl_evaluation_budget_steps": PROVISIONAL_BUDGET_STEPS,
        "max_unresolved_send_per_scope": PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "enforcement_mechanism_version": "enf-bt",
    }
    base.update(overrides)
    return EngineConfiguration(**base)


def registry_with(strategy: AuthoredStrategy | None = None) -> StrategyRegistry:
    """A registry holding exactly one admitted strategy."""
    registry = StrategyRegistry()
    registry.register(strategy or issue_strategy(), authored_config())
    return registry


def registry_with_all(*strategies: AuthoredStrategy) -> StrategyRegistry:
    """A registry holding N admitted strategies — the multi-symbol universe (design #31 §3.3)."""
    registry = StrategyRegistry()
    for strategy in strategies:
        registry.register(strategy, authored_config())
    return registry


def admitting_stages(**overrides: Any) -> dict[CommitmentStep, Stage]:
    """A complete NON-AUTHORITATIVE PROVISIONAL stand-in map that admits every injected step."""
    return provisional_stage_map(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        **overrides,
    )


def time_projection(**overrides: Any) -> BarTimeProjection:
    """Injected bar → time-coordinate bounds that positively admit (design #33 §3.3)."""
    base: dict[str, Any] = {
        "source_age": 10,
        "delay_bounds": (5,),
        "max_age_bound": 1000,
        "future_tolerance": 50,
        "snapshot_age_bound": 20,
        "maximum_consumer_age_ms": 1000,
        "interval_width": 2,
        "boundary_lag": 10,
        "session_template": SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=0,
        ),
        "health_state": HealthState.TRUSTED,
    }
    base.update(overrides)
    return BarTimeProjection(**base)


def build_converter(
    *,
    resolver: Any = None,
    key: InstrumentKey | None = None,
    projection: BarTimeProjection | None = None,
    source: Any = None,
) -> CausalBarConverter:
    """Wire the causal converter with the suite's defaults."""
    return CausalBarConverter(
        instrument_key=key or instrument_key(),
        resolver=resolver or ProvisionalContextResolver(),
        capsule_source=source or capsule_source,
        time_projection=projection or time_projection(),
    )


def build_core(
    *,
    strategy: AuthoredStrategy | None = None,
    stages: Mapping[CommitmentStep, Stage] | None = None,
    transmit: Any = None,
    configuration: EngineConfiguration | None = None,
    registry: StrategyRegistry | None = None,
    preconditions: Any = None,
) -> tuple[EngineCore, RecordingEvidenceSink]:
    """Wire a core with the suite's defaults and return it with its recording sink."""
    sink = RecordingEvidenceSink()
    core = EngineCore(
        registry=registry if registry is not None else registry_with(strategy),
        stages=dict(stages) if stages is not None else admitting_stages(),
        configuration=configuration or engine_configuration(),
        preconditions=(
            preconditions
            if preconditions is not None
            else SyntheticNonLivePreconditions(authority_epoch_current=True)
        ),
        transmit=transmit,
        transport_nature=NonBrokerTransportNature(),
        sink=sink,
    )
    return core, sink


def build_fill_model(
    parameters: FillParameters,
    *,
    scenario_id: Any = None,
    key: InstrumentKey | None = None,
) -> DeterministicFillModel:
    """Wire the deterministic synthetic fill band."""
    return DeterministicFillModel(
        instrument_key=key or instrument_key(),
        parameters=parameters,
        scenario_id=scenario_id,
    )


def build_driver(
    fill_model: DeterministicFillModel,
    *,
    scenario_id: Any = None,
    continuity_id: str = CONTINUITY_ID,
    converter: CausalBarConverter | None = None,
) -> BacktestDriver:
    """Wire the interleaving re-injection driver."""
    return BacktestDriver(
        converter=converter or build_converter(),
        fill_model=fill_model,
        continuity_id=continuity_id,
        scenario_id=scenario_id,
    )


def offset_bars(count: int, *, coordinate_offset: int = 0) -> BarStream:
    """One lane's stream: the reference profile shifted along the opaque time coordinate."""
    return validate_bar_stream(
        [
            bar.model_copy(
                update={
                    "timestamp_coordinate": bar.timestamp_coordinate + coordinate_offset
                }
            )
            for bar in reference_bars(count)
        ]
    )


def lane_strategy(
    instrument: str,
    *,
    policy: DecisionPolicy | None = None,
    target_kind: TargetKind = TargetKind.ACTION,
) -> AuthoredStrategy:
    """One lane's Authored Strategy, declaring exactly that lane's scope (design #31 §3.3)."""
    return issue_strategy(
        policy
        if policy is not None
        else capsule_gated_policy(target_kind=target_kind, instrument=instrument)
    )


def vector_policy(instrument: str = INSTRUMENT) -> DecisionPolicy:
    """A policy whose firing rule selects a multi-instrument ``VECTOR`` outcome (design #37 §5-T7)."""
    vector = Decision(
        kind=DecisionKind.VECTOR,
        rationale="portfolio vector",
        vector=(
            TargetSpec(
                kind=TargetKind.ACTION,
                account=ACCOUNT,
                instrument=instrument,
                direction="LONG",
                position_effect="OPEN",
                quantity_basis="RISK",
                rationale="leg 1",
            ),
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
        decision=vector,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def build_multi_symbol_driver(
    lanes: Sequence[tuple[str, FillParameters]],
    *,
    continuity_id: str = CONTINUITY_ID,
    scenario_id: Any = None,
) -> tuple[
    MultiSymbolBacktestDriver,
    dict[InstrumentKey, CausalBarConverter],
    dict[InstrumentKey, DeterministicFillModel],
]:
    """Wire an N-lane driver plus its per-lane converters and fill bands (design #37 §3.2)."""
    converters: dict[InstrumentKey, CausalBarConverter] = {}
    fill_models: dict[InstrumentKey, DeterministicFillModel] = {}
    for instrument, parameters in lanes:
        key = instrument_key(instrument=instrument)
        converters[key] = build_converter(
            key=key, source=capsule_source_for(instrument)
        )
        fill_models[key] = build_fill_model(
            parameters, scenario_id=scenario_id, key=key
        )
    driver = MultiSymbolBacktestDriver(
        converters=converters,
        fill_models=fill_models,
        continuity_id=continuity_id,
        scenario_id=scenario_id,
    )
    return driver, converters, fill_models


def stages_for(spec: ScenarioSpec) -> dict[CommitmentStep, Stage]:
    """Build the scenario's stand-in stage map (denials / no-decisions as the spec declares)."""
    overrides: dict[str, Any] = {}
    if spec.denied_steps:
        overrides["denied_steps"] = dict.fromkeys(
            spec.denied_steps, spec.denial_reason or ""
        )
    if spec.unknown_steps:
        overrides["unknown_steps"] = frozenset(spec.unknown_steps)
    return admitting_stages(**overrides)


def run_scenario(
    spec: ScenarioSpec,
) -> tuple[BacktestRun, EngineCore, DeterministicFillModel, RecordingEvidenceSink]:
    """Replay one mandated scenario end-to-end through a single core (design #33 §5.1)."""
    fill_model = build_fill_model(spec.fill_parameters, scenario_id=spec.scenario_id)
    driver = build_driver(fill_model, scenario_id=spec.scenario_id)
    core, sink = build_core(
        strategy=issue_strategy(capsule_gated_policy(target_kind=spec.target_kind)),
        stages=stages_for(spec),
        transmit=fill_model,
    )
    run = driver.run(core, reference_bars(spec.bar_count))
    return run, core, fill_model, sink
