"""Shared builders for the ``tos.engine`` authoring-evidence suite (design #31 §7).

Every builder is deterministic and clock-free: no ``time`` / ``datetime`` / ``random`` / ``uuid``
appears anywhere, including here, because the §7.1 determinism canary scans the *sources* and the
tests must not model something the shipped package forbids.
"""

from __future__ import annotations

from typing import Any

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
    AttemptRequest,
    CommitmentStep,
    DecisionTickPayload,
    EngineConfiguration,
    EngineCore,
    EngineEvent,
    EventKind,
    InstrumentKey,
    RecordingEvidenceSink,
    SendHandoff,
    Stage,
    StrategyRegistry,
    TimeAdmissionInputs,
    provisional_stage_map,
)
from tos.ordering import OrderingEvent
from tos.time import HealthState, SessionContext, UncertaintyInterval

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-1"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"

#: Every bound the engine consumes is injected here — the package hardcodes none (design #31 §8).
#: These are **provisional** values: the DSL-evaluation budget key does not exist in
#: VERIFICATION-PROFILE-002 and the register's Phase-0 bounds approval is incomplete.
PROVISIONAL_BUDGET_STEPS = 64
PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

PROOF_DIGEST = "proof-digest-0"
PERMIT_IDENTITY = "permit-0"


def instrument_key(account: str = ACCOUNT, instrument: str = INSTRUMENT) -> InstrumentKey:
    """The dispatch key used across the suite."""
    return InstrumentKey(account=account, instrument=instrument)


def issue_capsule(**overrides: Any) -> DecisionContextCapsule:
    """Issue a valid Decision Context Capsule scoped to the suite's account/instrument."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "critical_input_snapshot": SnapshotRef(snapshot_id="cis-ref", canonical_digest="sd-1"),
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


def capsule_gated_policy(
    *,
    fires: bool = True,
    account: str | None = ACCOUNT,
    instrument: str | None = INSTRUMENT,
) -> DecisionPolicy:
    """A policy whose single guard reads a **capsule-sourced** operand (design #31 §3.2 (3)).

    The guard compares ``capsule.scope.decision_class`` against a literal, so it has the ≥1
    capsule-sourced operand admission requires. ``fires=False`` compares against a different
    literal so the default no-action is selected instead.
    """
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="capsule-sourced guard fired",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=account,
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
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def config_gated_policy() -> DecisionPolicy:
    """A policy whose only guard reads ``config`` — the D1 relabelling escape admission refuses."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="config-gated",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            rationale="config-gated",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="hold")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("config", "last_price")),
                op=CompareOp.GT,
                right=Operand(const=0),
            ),
        ),
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def vector_policy() -> DecisionPolicy:
    """A policy whose firing rule selects a multi-instrument ``VECTOR`` outcome."""
    vector = Decision(
        kind=DecisionKind.VECTOR,
        rationale="portfolio vector",
        vector=(
            TargetSpec(
                kind=TargetKind.ACTION,
                account=ACCOUNT,
                instrument=INSTRUMENT,
                direction="LONG",
                position_effect="OPEN",
                quantity_basis="RISK",
                rationale="leg 1",
            ),
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="hold")
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


def issue_strategy(policy: DecisionPolicy | None = None, **overrides: Any) -> AuthoredStrategy:
    """Issue a valid Authored Strategy carrying ``policy`` (a capsule-gated one by default)."""
    base: dict[str, Any] = {
        "dsl_version": "dsl-0",
        "config_binding_version": "cfg-bind-0",
        "policy": policy if policy is not None else capsule_gated_policy(),
    }
    base.update(overrides)
    return AuthoredStrategy.issue(scheme=SCHEME, **base)


def authored_config(**overrides: Any) -> EvaluationConfig:
    """The authored constants a strategy reads — never a market-derived value (design #31 §3.2)."""
    base: dict[str, Any] = {"config_version": "cfg-0", "bindings": {"band_k": 2}}
    base.update(overrides)
    return EvaluationConfig(**base)


def admitting_time_inputs(**overrides: Any) -> TimeAdmissionInputs:
    """Injected time coordinates that positively admit (design #31 §2.3)."""
    base: dict[str, Any] = {
        "source_age": 10,
        "delay_bounds": (5,),
        "max_age_bound": 1000,
        "future_tolerance": 50,
        "snapshot_age_bound": 20,
        "maximum_consumer_age_ms": 1000,
        "session_context": SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=100000,
        ),
        "uncertainty_interval": UncertaintyInterval(lo=1, hi=2),
        "health_state": HealthState.TRUSTED,
    }
    base.update(overrides)
    return TimeAdmissionInputs(**base)


def engine_configuration(**overrides: Any) -> EngineConfiguration:
    """The injected engine configuration (every value provisional — design #31 §8)."""
    base: dict[str, Any] = {
        "dsl_evaluation_budget_steps": PROVISIONAL_BUDGET_STEPS,
        "max_unresolved_send_per_scope": PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "enforcement_mechanism_version": "enf-0",
    }
    base.update(overrides)
    return EngineConfiguration(**base)


def ordering(sequence: int) -> OrderingEvent:
    """A totally-ordered event coordinate (a bar index — an opaque injected coordinate)."""
    return OrderingEvent(event_id=f"ev-{sequence}", quorum_commit_index=sequence)


def decision_tick(
    *,
    sequence: int = 1,
    capsule: DecisionContextCapsule | None = None,
    key: InstrumentKey | None = None,
    time_inputs: TimeAdmissionInputs | None = None,
) -> EngineEvent:
    """Build a ``DECISION_TICK`` event."""
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=key or instrument_key(),
            capsule=capsule or issue_capsule(),
            time=time_inputs or admitting_time_inputs(),
            reference=ordering(sequence),
        ),
    )


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


class RecordingTransmit:
    """A send-boundary stand-in that records hand-offs and performs no I/O whatsoever."""

    def __init__(self, *, accept: bool = True, raises: bool = False) -> None:
        """Configure the stand-in."""
        self.attempts: list[AttemptRequest] = []
        self._accept = accept
        self._raises = raises

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Record the hand-off (or raise, to exercise the conservative retention path)."""
        self.attempts.append(attempt)
        if self._raises:
            raise RuntimeError("send boundary unavailable")
        return SendHandoff(
            accepted_for_transmission=self._accept, handoff_reference=attempt.attempt_id
        )


def build_core(
    *,
    registry: StrategyRegistry | None = None,
    stages: dict[CommitmentStep, Stage] | None = None,
    transmit: Any = None,
    sink: RecordingEvidenceSink | None = None,
    configuration: EngineConfiguration | None = None,
) -> tuple[EngineCore, RecordingEvidenceSink]:
    """Wire a core with the suite's defaults and return it with its recording sink."""
    recording_sink = sink or RecordingEvidenceSink()
    core = EngineCore(
        registry=registry or registry_with(),
        stages=stages if stages is not None else admitting_stages(),
        configuration=configuration or engine_configuration(),
        transmit=transmit if transmit is not None else RecordingTransmit(),
        sink=recording_sink,
    )
    return core, recording_sink
