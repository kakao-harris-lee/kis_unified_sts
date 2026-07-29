"""Shared builders for the ``tos.backtest`` authoring-evidence suite (design #33 §8).

Every builder is deterministic and clock-free: no ``time`` / ``datetime`` / ``random`` / ``uuid``
appears anywhere, including here, because the §9 determinism canary scans the *sources* and a test
suite must not model something the shipped package forbids.

The suite is deliberately **self-contained** rather than importing the ``tos.engine`` suite's
fixtures: a harness suite that depended on another package's test internals would couple two
independent authoring-evidence lanes, and the D-E3 scenarios need shapes (an Explicit-Flat policy,
a per-bar Capsule source) the engine suite has no reason to carry.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from tos.backtest import (
    BacktestDriver,
    BacktestIntegrityError,
    BacktestRun,
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    FillParameters,
    ProvisionalContextResolver,
    ScenarioSpec,
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
DECISION_CLASS = "entry"
CONTINUITY_ID = "backtest-stream-0"

#: Every bound the harness consumes is injected here — the package hardcodes none (design #33 §10).
#: These are **provisional** values: the DSL-evaluation budget key does not exist in
#: VERIFICATION-PROFILE-002 and the register's Phase-0 bounds approval (P0-1) is incomplete.
PROVISIONAL_BUDGET_STEPS = 64
PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

PROOF_DIGEST = "proof-digest-bt"
PERMIT_IDENTITY = "permit-bt"

#: pydantic wraps an exception raised inside a ``model_validator`` in a ``ValidationError``, while a
#: plain function raises :class:`~tos.backtest.BacktestIntegrityError` directly. Both are the same
#: fail-closed refusal, so the suite asserts against the pair rather than against whichever wrapper
#: happens to apply — the ``tos.engine`` suite's own precedent
#: (``test_engine_at_most_one.py:124`` widens to ``Exception`` for exactly this reason).
INTEGRITY_ERRORS = (BacktestIntegrityError, ValidationError)


def instrument_key(account: str = ACCOUNT, instrument: str = INSTRUMENT) -> InstrumentKey:
    """The dispatch key used across the suite."""
    return InstrumentKey(account=account, instrument=instrument)


def issue_capsule(**overrides: Any) -> DecisionContextCapsule:
    """Issue a valid Decision Context Capsule scoped to the suite's account/instrument."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-bt",
        "critical_input_policy": PolicyRef(policy_id="pol-bt", canonical_digest="pd-bt"),
        "critical_input_snapshot": SnapshotRef(snapshot_id="cis-bt", canonical_digest="sd-bt"),
        "scope": CapsuleScope(
            environment="non-live-test",
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class=DECISION_CLASS,
        ),
        "safety_critical_facts": SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    }
    base.update(overrides)
    return DecisionContextCapsule.issue(scheme=SCHEME, **base)


def capsule_source(bar: Any) -> DecisionContextCapsule:  # noqa: ARG001 - the slot takes the bar
    """The injected per-bar Capsule source.

    Slice #1 issues the *same* Capsule content for every bar, which is the honest position: the
    value surface that would make bars distinguishable is D-E2's (design #33 §3.5), and the design
    explicitly does **not** claim identity distinctness across bars — only reproducibility
    (design #33 §5.2, D-E1 Gap-1).
    """
    return issue_capsule()


def capsule_gated_policy(
    *, target_kind: TargetKind = TargetKind.ACTION, fires: bool = True
) -> DecisionPolicy:
    """A policy whose single guard reads a **capsule-sourced** operand (design #31 §3.2 (3)).

    ``target_kind=FLAT`` builds the Explicit-Flat scenario's policy (design #33 §5.1 row 7): a
    zero-position action, which is a single order and therefore NIT-3 consistent — not a round trip.
    """
    if target_kind is TargetKind.FLAT:
        decision = Decision(
            kind=DecisionKind.FLAT,
            rationale="capsule-sourced guard fired — explicit flat",
            target=TargetSpec(
                kind=TargetKind.FLAT,
                account=ACCOUNT,
                instrument=INSTRUMENT,
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
                instrument=INSTRUMENT,
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


def issue_strategy(policy: DecisionPolicy | None = None, **overrides: Any) -> AuthoredStrategy:
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


def admitting_stages(**overrides: Any) -> dict[CommitmentStep, Stage]:
    """A complete NON-AUTHORITATIVE PROVISIONAL stand-in map that admits every injected step."""
    return provisional_stage_map(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        **overrides,
    )


def time_projection(**overrides: Any) -> BarTimeProjection:
    """Injected bar → time-coordinate bounds that positively admit (design #33 §3.3).

    Every value is provisional: the trustworthy-time bounds are register §8-1 new-key candidates
    and P0-1 is incomplete (design #33 §10).
    """
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
) -> CausalBarConverter:
    """Wire the causal converter with the suite's defaults."""
    return CausalBarConverter(
        instrument_key=key or instrument_key(),
        resolver=resolver or ProvisionalContextResolver(),
        capsule_source=capsule_source,
        time_projection=projection or time_projection(),
    )


def build_core(
    *,
    strategy: AuthoredStrategy | None = None,
    stages: Mapping[CommitmentStep, Stage] | None = None,
    transmit: Any = None,
    configuration: EngineConfiguration | None = None,
) -> tuple[EngineCore, RecordingEvidenceSink]:
    """Wire a core with the suite's defaults and return it with its recording sink."""
    sink = RecordingEvidenceSink()
    core = EngineCore(
        registry=registry_with(strategy),
        stages=dict(stages) if stages is not None else admitting_stages(),
        configuration=configuration or engine_configuration(),
        transmit=transmit,
        sink=sink,
    )
    return core, sink


def build_fill_model(
    parameters: FillParameters, *, scenario_id: Any = None
) -> DeterministicFillModel:
    """Wire the deterministic synthetic fill band."""
    return DeterministicFillModel(
        instrument_key=instrument_key(), parameters=parameters, scenario_id=scenario_id
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


def stages_for(spec: ScenarioSpec) -> dict[CommitmentStep, Stage]:
    """Build the scenario's stand-in stage map (denials / no-decisions as the spec declares)."""
    overrides: dict[str, Any] = {}
    if spec.denied_steps:
        overrides["denied_steps"] = dict.fromkeys(spec.denied_steps, spec.denial_reason or "")
    if spec.unknown_steps:
        overrides["unknown_steps"] = frozenset(spec.unknown_steps)
    return admitting_stages(**overrides)


def run_scenario(
    spec: ScenarioSpec,
) -> tuple[BacktestRun, EngineCore, DeterministicFillModel, RecordingEvidenceSink]:
    """Replay one mandated scenario end-to-end through a single core (design #33 §5.1).

    Returns:
        ``(run, core, fill_model, sink)`` — the run's artifacts plus the live objects, so a test can
        assert against the **engine's** own state rather than a harness restatement of it.
    """
    fill_model = build_fill_model(spec.fill_parameters, scenario_id=spec.scenario_id)
    driver = build_driver(fill_model, scenario_id=spec.scenario_id)
    core, sink = build_core(
        strategy=issue_strategy(capsule_gated_policy(target_kind=spec.target_kind)),
        stages=stages_for(spec),
        transmit=fill_model,
    )
    run = driver.run(core, reference_bars(spec.bar_count))
    return run, core, fill_model, sink
