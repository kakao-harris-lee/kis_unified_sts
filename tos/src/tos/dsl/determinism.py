"""Pure evaluation + recorded-input signature (design §4; RFC-008 §9)."""

from __future__ import annotations

from typing import Any

from tos.capsule.capsule import DecisionContextCapsule
from tos.dsl._base import (
    ArtifactIntegrityError,
    DecisionContextCapsuleRef,
    FrozenModel,
)
from tos.dsl.context_value import VALUE_NAMESPACE, ContextValueView
from tos.dsl.outcome import NoActionOutcome, Outcome, PortfolioVector
from tos.dsl.proposal import Proposal, Proposer, build_flat, build_proposal
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import (
    Decision,
    DecisionKind,
    ScalarValue,
    TargetKind,
    TargetSpec,
    evaluate_policy,
)


class EvaluationConfig(FrozenModel):
    """A versioned configuration for one evaluation (design §4.1; §7 no-hardcoding)."""

    config_version: str
    bindings: dict[str, ScalarValue] = {}


class RecordedInputSignature(FrozenModel):
    """The recorded provenance of one evaluation (design §4.1; RFC-008 §9 L302-306)."""

    capsule_id: str | None = None
    capsule_canonical_digest: str | None = None
    authored_strategy_version: str | None = None
    dsl_version: str | None = None
    config_version: str | None = None
    enforcement_mechanism_version: str | None = None
    captured_external_value_refs: tuple[str, ...] = ()


class EvaluationResult(FrozenModel):
    """The pure result of an evaluation: an Outcome plus its recorded signature."""

    outcome: Outcome
    recorded_input_signature: RecordedInputSignature


def build_environment(
    capsule: DecisionContextCapsule,
    config: EvaluationConfig,
    *,
    resolved_context: ContextValueView | None = None,
) -> dict[str, Any]:
    """Build the Decision Context environment from the Capsule + config (design §4)."""
    capsule_view: dict[str, Any] = capsule.model_dump(mode="json")
    if resolved_context is not None:
        if VALUE_NAMESPACE in capsule_view:
            raise ArtifactIntegrityError(
                f"the resolved-value namespace {VALUE_NAMESPACE!r} collides with a Decision "
                "Context Capsule top-level key — merging would overwrite covered Capsule content "
                "with market-derived values, so the merge is refused (design #32 §3.2 (1))"
            )
        capsule_view[VALUE_NAMESPACE] = resolved_context.as_environment_mapping()
    return {
        "capsule": capsule_view,
        "config": dict(config.bindings),
    }


def _captured_value_refs(capsule: DecisionContextCapsule) -> tuple[str, ...]:
    """Pointers to the captured Critical Inputs the evaluation reads (EXV-INV-005)."""
    digest = capsule.critical_input_snapshot.canonical_digest
    return (digest,) if digest is not None else ()


def _capsule_ref(capsule: DecisionContextCapsule) -> DecisionContextCapsuleRef:
    """The content-addressed bind to the exact consumed Capsule (RFC-008 §8)."""
    return DecisionContextCapsuleRef(
        capsule_id=capsule.capsule_id, canonical_digest=capsule.canonical_digest
    )


def _proposer(strategy: AuthoredStrategy) -> Proposer:
    """The proposer identity — the content-addressed strategy id + digest version."""
    return Proposer(
        strategy_id=strategy.strategy_id, strategy_version=strategy.canonical_digest
    )


def _build_target_proposal(
    target: TargetSpec,
    *,
    scheme: Any,
    strategy: AuthoredStrategy,
    config: EvaluationConfig,
    capsule_ref: DecisionContextCapsuleRef,
    proposer: Proposer,
) -> Proposal:
    """Assemble one Proposal from a chosen target via the effect-free builder."""
    if target.kind is TargetKind.FLAT:
        return build_flat(
            scheme=scheme,
            proposer=proposer,
            account=target.account,  # type: ignore[arg-type]
            instrument=target.instrument,  # type: ignore[arg-type]
            direction=target.direction,  # type: ignore[arg-type]
            position_effect=target.position_effect,  # type: ignore[arg-type]
            rationale=target.rationale or "",
            decision_context_capsule=capsule_ref,
            dsl_version=strategy.dsl_version,  # type: ignore[arg-type]
            config_version=config.config_version,
            edge_or_confidence=target.edge_or_confidence,
            timing_and_execution_constraints=target.timing_and_execution_constraints,
        )
    return build_proposal(
        scheme=scheme,
        proposer=proposer,
        account=target.account,  # type: ignore[arg-type]
        instrument=target.instrument,  # type: ignore[arg-type]
        direction=target.direction,  # type: ignore[arg-type]
        position_effect=target.position_effect,  # type: ignore[arg-type]
        quantity_basis=target.quantity_basis,  # type: ignore[arg-type]
        rationale=target.rationale or "",
        decision_context_capsule=capsule_ref,
        dsl_version=strategy.dsl_version,  # type: ignore[arg-type]
        config_version=config.config_version,
        edge_or_confidence=target.edge_or_confidence,
        timing_and_execution_constraints=target.timing_and_execution_constraints,
    )


def _decision_to_outcome(
    decision: Decision,
    *,
    scheme: Any,
    strategy: AuthoredStrategy,
    config: EvaluationConfig,
    capsule: DecisionContextCapsule,
) -> Outcome:
    """Map a chosen Decision to its concrete Outcome artifact (ADR-DEV-007)."""
    capsule_ref = _capsule_ref(capsule)
    proposer = _proposer(strategy)
    if decision.kind is DecisionKind.NO_ACTION:
        return NoActionOutcome.issue(
            scheme=scheme,
            outcome_id=f"noact:{strategy.strategy_id}:{capsule.capsule_id}"
            f":{config.config_version}",
            rationale=decision.rationale,
            decision_context_capsule=capsule_ref,
            strategy_version=strategy.canonical_digest,
            dsl_version=strategy.dsl_version,
            config_version=config.config_version,
        )
    if decision.kind in (DecisionKind.ACTION, DecisionKind.FLAT):
        return _build_target_proposal(
            decision.target,  # type: ignore[arg-type]
            scheme=scheme,
            strategy=strategy,
            config=config,
            capsule_ref=capsule_ref,
            proposer=proposer,
        )
    components = tuple(
        _build_target_proposal(
            target,
            scheme=scheme,
            strategy=strategy,
            config=config,
            capsule_ref=capsule_ref,
            proposer=proposer,
        )
        for target in decision.vector
    )
    return PortfolioVector.issue(
        scheme=scheme,
        vector_id=f"vec:{strategy.strategy_id}:{capsule.capsule_id}"
        f":{config.config_version}",
        components=components,
        interdependence=decision.interdependence,
        decision_context_capsule=capsule_ref,
        dsl_version=strategy.dsl_version,
        config_version=config.config_version,
    )


def _evaluate(
    strategy: AuthoredStrategy,
    capsule: DecisionContextCapsule,
    config: EvaluationConfig,
    *,
    scheme: Any,
    enforcement_mechanism_version: str,
    resolved_context: ContextValueView | None,
) -> EvaluationResult:
    """The single evaluation body shared by :func:`evaluate` / :func:`evaluate_resolved`."""
    env = build_environment(capsule, config, resolved_context=resolved_context)
    decision = evaluate_policy(strategy.policy, env)  # type: ignore[arg-type]
    outcome = _decision_to_outcome(
        decision, scheme=scheme, strategy=strategy, config=config, capsule=capsule
    )
    captured_refs = _captured_value_refs(capsule)
    if resolved_context is not None:
        captured_refs = captured_refs + (resolved_context.canonical_digest,)
    signature = RecordedInputSignature(
        capsule_id=capsule.capsule_id,
        capsule_canonical_digest=capsule.canonical_digest,
        authored_strategy_version=strategy.canonical_digest,
        dsl_version=strategy.dsl_version,
        config_version=config.config_version,
        enforcement_mechanism_version=enforcement_mechanism_version,
        captured_external_value_refs=captured_refs,
    )
    return EvaluationResult(outcome=outcome, recorded_input_signature=signature)


def evaluate(
    strategy: AuthoredStrategy,
    capsule: DecisionContextCapsule,
    config: EvaluationConfig,
    *,
    scheme: Any,
    enforcement_mechanism_version: str,
) -> EvaluationResult:
    """Evaluate an Authored Strategy over a Capsule + config (pure; RFC-008 §9)."""
    return _evaluate(
        strategy,
        capsule,
        config,
        scheme=scheme,
        enforcement_mechanism_version=enforcement_mechanism_version,
        resolved_context=None,
    )


def evaluate_resolved(
    strategy: AuthoredStrategy,
    capsule: DecisionContextCapsule,
    config: EvaluationConfig,
    *,
    scheme: Any,
    enforcement_mechanism_version: str,
    resolved_context: ContextValueView | None = None,
) -> EvaluationResult:
    """Evaluate with a resolved Critical Input value view (design #32 §3.2 (3))."""
    return _evaluate(
        strategy,
        capsule,
        config,
        scheme=scheme,
        enforcement_mechanism_version=enforcement_mechanism_version,
        resolved_context=resolved_context,
    )
