"""§7.2-3 — bounded-evaluation degradation folds to a **distinctly recorded** no-action (§3.4).

The design's target: *"bound exhausted → NO_ACTION + 구별 degradation 증거·commitment flow 미진입"*.

Three things must hold together, and the third is the one a careless implementation loses:

1. an exhausted budget produces a No-Action Outcome (DCE-INV-007 — never a stall, never a partial
   unrecorded action);
2. the commitment flow is not entered at all (defence in depth: a no-action starts no flow, and a
   degradation is a no-action);
3. the degradation is recorded **distinctly** from an ordinary no-action — the two have different
   causes, and collapsing them destroys the only evidence that a bound was hit.

The budget gate is also asserted to be a genuine *pre*-evaluation gate: ``resolve_bound`` is
symbolic integer accounting and cannot interrupt ``evaluate`` mid-run (design #31 §3.4, MINOR-2), so
the work count must be derived statically from the policy structure.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from tos.dsl import BoundState, NoActionOutcome
from tos.engine import (
    EvidenceKind,
    HaltReason,
    policy_work_steps,
    run_decision_pipeline,
)

from ._engine_fixtures import (
    RecordingTransmit,
    authored_config,
    build_core,
    capsule_gated_policy,
    decision_tick,
    engine_configuration,
    instrument_key,
    issue_capsule,
    issue_strategy,
    registry_with,
)
from ._engine_fixtures import (
    admitting_time_inputs as _time,
)


def _exhausted_core(sink=None):
    """A core whose injected DSL budget is smaller than any policy's static work count."""
    return build_core(
        configuration=engine_configuration(dsl_evaluation_budget_steps=0),
        transmit=RecordingTransmit(),
        sink=sink,
    )


def test_work_steps_are_derived_statically_from_the_policy_structure() -> None:
    """(§3.4 MINOR-2) The work count is a structural walk, not a runtime measurement."""
    policy = capsule_gated_policy()
    # one rule + one compare + two operands
    assert policy_work_steps(policy) == 1 + 1 + 2
    assert policy_work_steps(capsule_gated_policy(fires=False)) == policy_work_steps(policy), (
        "the count is structural — it does not depend on which branch would fire"
    )


def test_an_exhausted_budget_folds_to_a_no_action_outcome() -> None:
    """(§7.2-3) A bound-exhausted evaluation yields a recorded No-Action (DCE-INV-007)."""
    core, _ = _exhausted_core()
    result = core.handle(decision_tick(sequence=1))

    assert result.pipeline is not None
    assert result.pipeline.bound_state is BoundState.BOUND_EXHAUSTED
    assert isinstance(result.pipeline.outcome, NoActionOutcome)
    assert result.pipeline.outcome.rationale is not None
    assert result.pipeline.outcome.rationale.strip()


def test_a_degraded_outcome_never_enters_the_commitment_flow() -> None:
    """(§7.2-3 / §4.2 rule 4) The flow is not started and nothing reaches the send boundary."""
    transmit = RecordingTransmit()
    core, _ = build_core(
        configuration=engine_configuration(dsl_evaluation_budget_steps=0), transmit=transmit
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.flow is None
    assert result.pipeline is not None and result.pipeline.proposal is None
    assert transmit.attempts == []
    assert core.ledger.outstanding(instrument_key()) is None


def test_the_degradation_is_recorded_distinctly_from_an_ordinary_no_action() -> None:
    """(§7.2-3) DECISION_DEGRADED is its own evidence kind and its own halt reason."""
    core, sink = _exhausted_core()
    core.handle(decision_tick(sequence=1))

    degraded = [r for r in sink.records if r.kind is EvidenceKind.DECISION_DEGRADED]
    assert len(degraded) == 1
    assert degraded[0].halt_reason is HaltReason.DEGRADED_BOUND_EXHAUSTED
    assert degraded[0].detail is not None and "budget_steps" in degraded[0].detail
    assert [r for r in sink.records if r.kind is EvidenceKind.DECISION_OUTCOME_EMITTED] == []

    # ... and an ordinary no-action is recorded under the *other* kind and reason.
    ordinary_core, ordinary_sink = build_core(
        registry=registry_with(issue_strategy(capsule_gated_policy(fires=False))),
        transmit=RecordingTransmit(),
    )
    ordinary_core.handle(decision_tick(sequence=1))
    emitted = [
        r for r in ordinary_sink.records if r.kind is EvidenceKind.DECISION_OUTCOME_EMITTED
    ]
    assert len(emitted) == 1
    assert emitted[0].halt_reason is HaltReason.NO_ACTION_OUTCOME
    assert [
        r for r in ordinary_sink.records if r.kind is EvidenceKind.DECISION_DEGRADED
    ] == []
    assert HaltReason.DEGRADED_BOUND_EXHAUSTED is not HaltReason.NO_ACTION_OUTCOME


def test_the_degraded_outcome_binds_the_exact_capsule_and_versions() -> None:
    """A degradation is still a recorded decision: it binds its Capsule and its versions."""
    capsule = issue_capsule()
    strategy = issue_strategy()
    config = authored_config()
    from tos.engine import DecisionTickPayload
    from tos.engine.sink import RecordingEvidenceSink

    from ._engine_fixtures import SCHEME

    sink = RecordingEvidenceSink()
    registry = registry_with(strategy)
    entry = registry.resolve(instrument_key()).entries[0]
    result = run_decision_pipeline(
        entry=entry,
        payload=DecisionTickPayload(
            instrument_key=instrument_key(), capsule=capsule, time=_time()
        ),
        configuration=engine_configuration(dsl_evaluation_budget_steps=0),
        scheme=SCHEME,
        sink=sink,
    )
    assert result.degraded is True
    outcome = result.outcome
    assert isinstance(outcome, NoActionOutcome)
    assert outcome.decision_context_capsule.capsule_id == capsule.capsule_id
    assert outcome.decision_context_capsule.canonical_digest == capsule.canonical_digest
    assert outcome.strategy_version == strategy.canonical_digest
    assert outcome.config_version == config.config_version


@pytest.mark.parametrize("budget", [4, 5, 100])
def test_a_sufficient_budget_completes_and_reaches_the_flow(budget) -> None:
    """The gate is a real comparison: a budget at or above the work count completes."""
    transmit = RecordingTransmit()
    core, _ = build_core(
        configuration=engine_configuration(dsl_evaluation_budget_steps=budget),
        transmit=transmit,
    )
    result = core.handle(decision_tick(sequence=1))
    assert result.pipeline is not None
    assert result.pipeline.bound_state is BoundState.COMPLETED
    assert result.flow is not None and result.flow.handed_off is True
    assert len(transmit.attempts) == 1


@pytest.mark.parametrize("budget", [0, 1, 2, 3])
def test_a_budget_below_the_work_count_degrades(budget) -> None:
    """Every budget strictly below the static work count degrades (the boundary is exact)."""
    core, _ = build_core(
        configuration=engine_configuration(dsl_evaluation_budget_steps=budget),
        transmit=RecordingTransmit(),
    )
    result = core.handle(decision_tick(sequence=1))
    assert result.pipeline is not None
    assert result.pipeline.bound_state is BoundState.BOUND_EXHAUSTED
    assert result.flow is None
