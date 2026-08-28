"""Pure evaluation + recorded-input signature (design §4; RFC-008 §9).

Evaluating an Authored Strategy over a fixed Decision Context Capsule and fixed
configuration is a **pure function** of exactly those three inputs (design §4.1;
RFC-008 §9 L284): :func:`evaluate` reads only ``(strategy, capsule, config)`` — its
signature exposes **no** ambient clock, wall-time, randomness, mutable global,
network, or filesystem, and no fetch callable (ambient-independence is structural;
DCE-INV-003). The Capsule is a frozen, read-only input; evaluation reads it and
never mutates it (structurally impossible — it is frozen).

**Captured, not called (EXV-INV-001; design §4.2).** Any external/LLM-derived value
a strategy consumes has already been captured into the Capsule as Critical Input
*before* evaluation; :func:`evaluate` has no capability to fetch one live. The
recorded-input signature records the captured-value pointer (the snapshot digest)
as reproduction evidence, never authority (EXV-INV-005).

**Recorded provenance (design §4.1).** The function's *data dependency* is the
three inputs; the *recorded signature* is wider (RFC-008 §9 L302-306; ADR-DEV-001 §9
L254-257): Capsule id/digest, the content-addressed Authored Strategy version, the
DSL version, the configuration version, the Enforcement-Mechanism version, and the
captured-external-value pointers.

**Reproducibility granularity is deferred (design §4.3).** Phase 1 asserts only
outcome+rationale equivalence (referential transparency); bit-for-bit is
ADR-DEV-002's to decide and is not pre-empted here.

Firewall: ``pydantic`` + stdlib + ``tos.*`` (incl. ``tos.capsule`` read-only input)
only (design §firewall).
"""

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
    """A versioned configuration for one evaluation (design §4.1; §7 no-hardcoding).

    ``bindings`` carries the injected thresholds/constants a policy reads via a
    ``config``-sourced context ref — thresholds are configuration, never hard-coded
    in the DSL (design §7). ``config_version`` is recorded in the outcome and the
    signature (RFC-008 §9).
    """

    config_version: str
    bindings: dict[str, ScalarValue] = {}


class RecordedInputSignature(FrozenModel):
    """The recorded provenance of one evaluation (design §4.1; RFC-008 §9 L302-306).

    Wider than the function's data dependency: the extra fields are audit/replay
    provenance (ADR-002-016 conforming inputs), not evaluation inputs. The captured
    external-value pointers evidence EXV-INV-005 (captured, reproducible, not
    authority).
    """

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
    """Build the Decision Context environment from the Capsule + config (design §4).

    The environment is the *only* source a policy reads. It namespaces the read-only
    Capsule content under ``"capsule"`` and the injected config bindings under
    ``"config"``; there is no ``clock``/``random``/``network`` namespace, so an
    ambient read is unreachable (DCE-INV-003). Pure function of its inputs.

    **The resolved-value merge (design #32 §3.2).** When ``resolved_context`` is supplied, its
    admitted values are merged as a flat scalar mapping at
    ``env["capsule"][VALUE_NAMESPACE][field_key]`` — under the ``"capsule"`` source, because a
    market-derived value reaches a policy as Critical Input and **never** relabelled as
    configuration (RFC-008 §10:327-331; RFC-004 §9:251-252). No third context source is invented
    (``ADMISSIBLE_CONTEXT_SOURCES`` is unchanged), and ``evaluate_policy`` is unchanged: the values
    arrive as ordinary scalar leaves the shipped interpreter already walks.

    **Backward compatibility is exact.** With ``resolved_context=None`` (the default, and every
    call site that predates design #32) the returned mapping is what it has always been — the same
    two keys over the same content.

    **Namespace disjointness is checked, not declared** (design #32 §3.2 (1), MINOR-3). The merge
    key is verified absent from the *actual* dumped Capsule mapping; a collision raises rather than
    overwriting a covered Capsule field, so a future Capsule field named ``resolved_values`` fails
    loudly instead of being silently shadowed by market values.

    Args:
        capsule: The read-only Decision Context Capsule.
        config: The versioned evaluation configuration.
        resolved_context: The published, already-verified value view whose admitted values are
            merged under the Capsule source, or ``None`` for the value-free environment.

    Returns:
        A nested, JSON-native environment mapping.

    Raises:
        ArtifactIntegrityError: If the value namespace collides with a Capsule top-level key.
    """
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
    """Pointers to the captured Critical Inputs the evaluation reads (EXV-INV-005).

    The captured external values entered via the Critical Input Snapshot the Capsule
    binds; the snapshot digest is their reproduction pointer. Evaluation reads them
    from the Capsule — it never fetches them live (EXV-INV-001).
    """
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
    # Phase-0 alignment note: these independent ids are a readable (strategy,
    # capsule, config) triple, not a collision-proof key — the same triple over
    # different content yields the same id but a different digest. Collision is
    # harmless here because the IndependentIdArtifact digest binds the content and
    # detects it; a canonical independent-id scheme is a Phase-0 concern.
    if decision.kind is DecisionKind.NO_ACTION:
        return NoActionOutcome.issue(  # type: ignore[return-value]
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
    # DecisionKind.VECTOR
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
    return PortfolioVector.issue(  # type: ignore[return-value]
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
    """The single evaluation body shared by :func:`evaluate` / :func:`evaluate_resolved`.

    One body, two entry points — the difference is *only* whether a resolved value view takes part.
    Duplicating the outcome/signature assembly at a second call site would be the DRY breach design
    #32 §3.5 (B) rejects, so both public entry points funnel through here.
    """
    env = build_environment(capsule, config, resolved_context=resolved_context)
    decision = evaluate_policy(strategy.policy, env)  # type: ignore[arg-type]
    outcome = _decision_to_outcome(
        decision, scheme=scheme, strategy=strategy, config=config, capsule=capsule
    )
    captured_refs = _captured_value_refs(capsule)
    if resolved_context is not None:
        # ★ The fourth decision input joins the recorded provenance (design #32 §3.2 (3b),
        # MAJOR-2a). Without this, two runs over the *same* Capsule but *different* resolved
        # values would record an identical signature while producing different outcomes, and
        # replay could not detect the divergence (RFC-008 §9:302-306).
        captured_refs = captured_refs + (resolved_context.canonical_digest,)
    signature = RecordedInputSignature(
        capsule_id=capsule.capsule_id,
        capsule_canonical_digest=capsule.canonical_digest,
        # Content-addressed strategy version, consistent with the bare
        # ``canonical_digest`` recorded as ``strategy_version`` on the emitted
        # Outcome/Proposer (design §4.1) — not the prefixed ``strategy_id``.
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
    """Evaluate an Authored Strategy over a Capsule + config (pure; RFC-008 §9).

    A pure function of ``(strategy, capsule, config)``: the same three inputs always
    yield the same Outcome and rationale (referential transparency). The signature
    exposes no ambient source and no fetch callable, so evaluation cannot reach a
    clock/RNG/network/filesystem (DCE-INV-003) and cannot live-fetch an external
    value (EXV-INV-001). ``scheme`` and ``enforcement_mechanism_version`` are
    provenance/canonicalization parameters (not decision inputs): they are recorded,
    and do not alter which Decision the policy selects.

    Design #32 adds a *fourth* decision input — a resolved Critical Input value view — through the
    separate :func:`evaluate_resolved` entry point rather than through this signature; see that
    function for why the parameter set here is deliberately left untouched.

    Args:
        strategy: The Authored Strategy (its embedded policy is evaluated).
        capsule: The read-only Decision Context Capsule (frozen input).
        config: The versioned evaluation configuration (injected bindings).
        scheme: The canonicalization scheme bound into the emitted artifacts.
        enforcement_mechanism_version: The recorded escape-checker version (design
            §7; injected, not hard-coded).

    Returns:
        The :class:`EvaluationResult` (Outcome + recorded input signature).
    """
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
    """Evaluate with a resolved Critical Input value view (design #32 §3.2 (3)).

    Identical to :func:`evaluate` in every respect except one: the admitted values of
    ``resolved_context`` are merged into ``env["capsule"][VALUE_NAMESPACE]`` before the policy runs,
    and the view's canonical digest is **appended** to
    :attr:`RecordedInputSignature.captured_external_value_refs`. That append is the point: a
    resolved value set is a decision input, so two runs that differ only in their values must differ
    in their recorded signature or replay cannot detect the divergence (RFC-008 §9:302-306; design
    #32 §3.2 (3b), MAJOR-2a).

    ``resolved_context=None`` reproduces :func:`evaluate` exactly — same environment, same outcome,
    same signature — which is what lets the engine pipeline forward ``payload.value_view``
    unconditionally without changing behaviour for a value-free tick.

    ⚠ **Why this is a separate function rather than a keyword argument on** :func:`evaluate`
    **(deviation from design #32 §3.2 (3)/§15.2 ①(b), recorded honestly).** The design specifies
    ``evaluate(…, resolved_context=None)``. The committed canary
    ``tos/tests/dsl/test_dsl_determinism.py:136-146`` asserts ``evaluate``'s parameter set is
    *exactly* the five existing names, so adding a sixth parameter — ambient or not — breaks a
    shipped test. The design's own sanction premise is "committed 테스트 파괴 0" (§15.2 ③), and
    editing a canary so new code fits is the neutered-canary defect class this series refuses. So
    the *substance* of the design (the merge, the digest append, ``evaluate_policy`` unchanged, the
    Capsule model unchanged, one shared body) is implemented in full and only the entry-point
    spelling differs. Reconciling the two — an errata that names this function, or an explicit
    sanction to amend the canary — is the orchestrator's call, and until then both the design's
    safety property and the committed canary hold simultaneously.

    ⚠ **Trust seam.** The value ⟺ ``payload_digest`` binding was verified by the ``tos.marketfeed``
    producer at publication time; this function does **not** re-verify it (design #32 §2.3/§4.3).
    What it adds is detectability, not enforcement.

    Args:
        strategy: The Authored Strategy (its embedded policy is evaluated).
        capsule: The read-only Decision Context Capsule (frozen input).
        config: The versioned evaluation configuration (injected bindings).
        scheme: The canonicalization scheme bound into the emitted artifacts.
        enforcement_mechanism_version: The recorded escape-checker version (design §7).
        resolved_context: The published value view, or ``None`` for a value-free evaluation.

    Returns:
        The :class:`EvaluationResult` (Outcome + recorded input signature).
    """
    return _evaluate(
        strategy,
        capsule,
        config,
        scheme=scheme,
        enforcement_mechanism_version=enforcement_mechanism_version,
        resolved_context=resolved_context,
    )
