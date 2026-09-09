"""Shared builders for ``tos_runtime.engine`` tests (TOS Phase 3 Wave 1 Lane A-R).

**Not a copy of ``tos/tests/engine/_engine_fixtures.py`` and does not import it** — runtime tests
may not import kernel test modules (the same discipline
``tos/runtime/tests/compose/_fixtures.py``'s own docstring states and this module extends). This
file authors its own, much smaller, single-instrument fixture set directly against kernel
PRODUCTION packages (``tos.dsl``/``tos.capsule``/``tos.engine``), mirroring the kernel test
module's own shape (``provisional_stage_map``, a capsule-gated always-fire policy) so the
DECISION_TICK -> flow -> hand-off path is exercised the same way the kernel's own authoring
evidence exercises it, without depending on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    PolicyRef,
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
    EngineConfiguration,
    EngineCore,
    EngineEvent,
    EventKind,
    InstrumentKey,
    NullEvidenceSink,
    SendHandoff,
    Stage,
    StrategyRegistry,
    TimeAdmissionInputs,
    provisional_stage_map,
)
from tos.engine.records import DecisionTickPayload, EgressResultPayload
from tos.engine.vocabulary import EgressResultKind
from tos.ordering import OrderingEvent
from tos.time import HealthState, SessionContext, UncertaintyInterval
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import OrthostateProjector
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-ar"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
PROOF_DIGEST = "proof-digest-ar-0"
PERMIT_IDENTITY = "permit-ar-0"


def instrument_key() -> InstrumentKey:
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def issue_capsule(*, seq: int = 1) -> DecisionContextCapsule:
    return DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-ar",
        critical_input_policy=PolicyRef(policy_id="pol-ar", canonical_digest="pd-ar"),
        critical_input_snapshot=SnapshotRef(
            snapshot_id=f"cis-ar-{seq}", canonical_digest=f"sd-ar-{seq}"
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
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def always_fires_policy() -> DecisionPolicy:
    """A capsule-gated policy that always fires (design #31 §3.2 (3) capsule-sourced guard)."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="A-R fixture always fires",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="A-R fixture always fires",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="unreachable default")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "scope", "decision_class")),
                op=CompareOp.EQ,
                right=Operand(const=DECISION_CLASS),
            ),
        ),
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def never_fires_policy() -> DecisionPolicy:
    """A capsule-gated policy whose guard never matches — a defined no-action for every tick.

    Carries one rule (with a real ``TargetSpec``, so the strategy's dispatch scope is still
    structurally derivable at registration — design #31 §3.3) whose guard compares against a
    decision_class literal no fixture capsule ever carries, so it never actually fires.
    """
    unreachable_action = Decision(
        kind=DecisionKind.ACTION,
        rationale="unreachable — guard never matches",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="unreachable — guard never matches",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="A-R fixture never fires")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("capsule", "scope", "decision_class")),
                op=CompareOp.EQ,
                right=Operand(const="no-such-decision-class"),
            ),
        ),
        decision=unreachable_action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def issue_strategy(policy: DecisionPolicy | None = None) -> AuthoredStrategy:
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-ar",
        config_binding_version="cfg-bind-ar",
        policy=policy if policy is not None else always_fires_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def authored_config() -> EvaluationConfig:
    return EvaluationConfig(config_version="cfg-ar", bindings={})


def registry_with(policy: DecisionPolicy | None = None) -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(issue_strategy(policy), authored_config())
    return registry


def admitting_time_inputs() -> TimeAdmissionInputs:
    return TimeAdmissionInputs(
        source_age=10,
        delay_bounds=(5,),
        max_age_bound=1000,
        future_tolerance=50,
        snapshot_age_bound=20,
        maximum_consumer_age_ms=1000,
        session_context=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-ar",
            trading_calendar_version="cal-ar",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=100000,
        ),
        uncertainty_interval=UncertaintyInterval(lo=1, hi=2),
        health_state=HealthState.TRUSTED,
    )


def engine_configuration() -> EngineConfiguration:
    return EngineConfiguration(
        dsl_evaluation_budget_steps=64,
        max_unresolved_send_per_scope=1,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        enforcement_mechanism_version="engine-ar-tests-v1",
    )


def admitting_stages(**overrides: Any) -> dict[CommitmentStep, Stage]:
    """A complete NON-AUTHORITATIVE PROVISIONAL stand-in map admitting every injected step."""
    return provisional_stage_map(
        conformance_proof_digest=PROOF_DIGEST,
        action_flow_permit_identity=PERMIT_IDENTITY,
        **overrides,
    )


def decision_tick_event(*, seq: int = 1) -> EngineEvent:
    """An UNSTAMPED ``DECISION_TICK`` event — the driver replaces ``reference`` on admission."""
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=instrument_key(),
            capsule=issue_capsule(seq=seq),
            time=admitting_time_inputs(),
            reference=OrderingEvent(
                source_continuity_id="fixture", source_native_sequence=seq
            ),
        ),
    )


def egress_result_event(
    *, attempt_id: str, kind: EgressResultKind = EgressResultKind.ACK
) -> EngineEvent:
    """An UNSTAMPED ``EGRESS_RESULT`` event."""
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=instrument_key(),
            attempt_id=attempt_id,
            kind=kind,
        ),
    )


@dataclass
class FakeGateway:
    """A send-boundary test double exposing the exact surface
    :class:`~tos_runtime.engine.driver.EngineDriver` drains (``.results``, structurally — never
    imported by type, mirroring ``tos.backtest.fills.RetainedEgressResults``'s "declared locally"
    seam). ``__call__`` accepts and, by default, retains an ``ACK`` result SYNCHRONOUSLY before
    returning — mirroring how the real ``BrokerEgressGateway`` retains ``.results`` before its
    own ``__call__`` returns (step 19 happens inside the same call as step 18's ``send_once``).
    A test can still append to :attr:`results` directly (:meth:`record_result`) to simulate a
    result becoming available on a LATER drain instead.
    """

    attempts: list[AttemptRequest] = field(default_factory=list)
    results: tuple[EgressResultPayload, ...] = ()
    auto_ack: bool = True

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        self.attempts.append(attempt)
        if self.auto_ack:
            self.record_result(
                EgressResultPayload(
                    instrument_key=instrument_key(),
                    attempt_id=attempt.attempt_id,
                    kind=EgressResultKind.ACK,
                )
            )
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )

    def record_result(self, payload: EgressResultPayload) -> None:
        """Simulate the gateway retaining one more result after a send."""
        self.results = self.results + (payload,)


class _AlwaysPermissivePreconditions:
    """A ``True``/``True`` ``CoordinatorPreconditions`` double for THIS file's own
    driver/replay fixtures (TOS Phase 3 Wave 2 KW2-B made ``preconditions`` a
    required ``EngineCore`` constructor argument — design #31 §9-10; plan
    §2.1). This module's own tests exercise the durable-inbox/driver/replay
    machinery, not the Coordinator gate itself (that is
    ``tos_runtime.compose._preconditions``'s own test scope,
    ``tos/runtime/tests/compose/test_preconditions.py`` — Lane B-R), so every
    tick here is unconditionally admitted past the gate, matching this
    fixture set's pre-KW2-B behaviour exactly (there was no gate to fail
    before)."""

    def authority_epoch_current(self) -> bool | None:
        return True

    def live_scope_authorized(self, _transport_nature: Any) -> bool | None:
        return True


def build_core(
    *,
    registry: StrategyRegistry | None = None,
    stages: dict[CommitmentStep, Stage] | None = None,
    transmit: Any = None,
    preconditions: Any = None,
    sink: Any = None,
) -> EngineCore:
    """``preconditions`` defaults to :class:`_AlwaysPermissivePreconditions` (module docstring —
    this fixture set exercises the durable-inbox/driver/replay machinery, not the Coordinator
    gate itself). A caller that specifically wants to exercise a gate refusal (independent
    review finding #1, wave 2, 2026-09-09 — ``tos_runtime.engine.replay``'s own Coordinator-gate
    refusal case) passes a different ``CoordinatorPreconditions`` double instead.

    ``sink`` defaults to :class:`~tos.engine.NullEvidenceSink` (this fixture set's own long-
    standing default — kernel-level ``EngineEvidenceRecord``s, e.g. ``SEND_HANDED_OFF``, are
    discarded, never landing in the durable ``evidence_store``). A caller that needs the LIVE
    run's own kernel evidence to be durably queryable afterward (CR5, 2026-09-09 —
    :class:`~tos_runtime.engine.replay_transmit.RecordedTransmit` reads ``SEND_HANDED_OFF``
    evidence back out of the SAME durable store) passes
    ``tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter(evidence_store)`` instead.
    """
    return EngineCore(
        registry=registry if registry is not None else registry_with(),
        stages=stages if stages is not None else admitting_stages(),
        configuration=engine_configuration(),
        preconditions=(
            preconditions
            if preconditions is not None
            else _AlwaysPermissivePreconditions()
        ),
        transmit=transmit,
        sink=sink if sink is not None else NullEvidenceSink(),
        scheme=SCHEME,
    )


def orthostate_projector(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    *,
    authority_epoch_current: Any = lambda: True,
) -> OrthostateProjector:
    """A real, test-scoped :class:`~tos_runtime.engine.orthostate_projection
    .OrthostateProjector` — ``EngineDriver`` now requires one (team-lead CR-4 dispatch, plan
    §2.2), so every test-suite driver construction needs a concrete instance, never a stand-in
    that skips the projection. ``authority_epoch_current`` defaults to an always-current stand-in
    (``lambda: True``): this fixture set's own driver/replay tests exercise the commitment-flow
    machinery, not authority-epoch currency (that is
    ``tos_runtime.compose._preconditions``'s own test scope) — a caller that specifically wants
    to exercise CPL-6 passes a different callable."""
    return OrthostateProjector(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        authority_epoch_current=authority_epoch_current,
    )


#: A fully-valued, test-scoped SYNTHETIC finality policy — mirrors
#: ``tos/runtime/tests/compose/conftest.py``'s own ``finality.yaml`` fixture values, so a driver
#: test and a compose e2e test derive the identical proof shape for the same fill.
_TEST_FINALITY_CONFIG = FinalityConfig(
    currency="KRW",
    value_date="2026-09-09",
    source_revision="engine-test-rev-1",
    proof_recipe_id="engine-test-recipe-1",
)


def finality_producer() -> SyntheticFinalityProducer:
    """A real, test-scoped :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer`
    — ``EngineDriver`` now requires one (team-lead CR-4 dispatch, plan §2.2)."""
    return SyntheticFinalityProducer(config=_TEST_FINALITY_CONFIG, scheme=SCHEME)
