"""Strategy DSL pure models + static admissibility (Phase 1, EV-L1, non-transmitting).

Realizes RFC-008 (Strategy DSL) + ADR-DEV-001 (DSL Realization and Purity/
Escape-Closure Enforcement) Phase 1, per the operator-ratified design contract
``docs/plans/2026-07-21-tos-strategy-dsl-design.md`` (v1.1). Cross-normative:
ADR-DEV-003 (External Value Capture), ADR-DEV-007 (Strategy Output Semantics).

This package is **pure, non-transmitting, and authority-free** (design §0): frozen
pydantic models, a closed typed AST algebra, a pure static-admissibility predicate,
a pure evaluator, and conservative enforcement-evidence records. It reuses the
:mod:`tos.canonical` digest-binding substrate (no redefinition) and reads the
:mod:`tos.capsule` Decision Context Capsule as a read-only input. It imports only
``pydantic`` + stdlib + ``tos.*`` — no ``importlib`` / ``__import__``
/ ``exec`` / ``eval`` / ``compile``, no ``os.environ`` / ``getenv``, no network
stdlib, no ``shared.*`` operational packages, and no ``numpy`` / ``pandas`` — the
escape-checker analyzes candidates by **static node-membership inspection only**,
never by importing or executing them (design §3.2). Actively verified by the §6.4
import-closure test in ``tos/tests/dsl``.

**Honesty (design §0/§1):** this Phase realizes only static admissibility (layer
1), the output-semantics models, the pure evaluator, and the bounded-evaluation
transition. Capability-restricted evaluation (layer 2), the isolation boundary
(layer 3), mechanism verification (DCE-INV-005), layered non-self-trust
(DCE-INV-002), numeric bounds, and any authority are **not** implemented. Property
tests here are *authoring* evidence, not acceptance — every DCE-EV stays
NOT_IMPLEMENTED.

Public surface groups by module:

* :mod:`tos.dsl.vocabulary` — the closed typed AST algebra + pure evaluator.
* :mod:`tos.dsl.candidate` — the adversarial candidate-AST input domain.
* :mod:`tos.dsl.admissibility` — the pure static-admissibility predicate.
* :mod:`tos.dsl.proposal` — the Proposal + effect-free Proposal Builder.
* :mod:`tos.dsl.outcome` — No-Action / Explicit-Flat / Portfolio-Vector semantics.
* :mod:`tos.dsl.strategy` — the Authored Strategy artifact.
* :mod:`tos.dsl.determinism` — the pure ``evaluate`` + recorded-input signature.
* :mod:`tos.dsl.bounds` — the bounded-evaluation (symbolic) state machine.
* :mod:`tos.dsl.evidence` — the enforcement-evidence records.
"""

from __future__ import annotations

from tos.dsl._base import (
    AllFalseAuthority,
    ArtifactIntegrityError,
    DecisionContextCapsuleRef,
    IndependentIdArtifact,
)
from tos.dsl.admissibility import (
    AdmissibilityAnalysis,
    AdmissibilityVerdict,
    admissibility_reasons,
    analyze,
    is_admissible,
)
from tos.dsl.bounds import (
    BoundState,
    degrades_to_no_action,
    resolve_bound,
    select_outcome,
)
from tos.dsl.candidate import (
    AMBIENT_SYMBOLS,
    ESCAPE_KINDS,
    WILDCARD_TOKENS,
    CandidateNode,
    CandidateProgram,
    iter_nodes,
)
from tos.dsl.determinism import (
    EvaluationConfig,
    EvaluationResult,
    RecordedInputSignature,
    build_environment,
    evaluate,
)
from tos.dsl.evidence import (
    PHASE1_CAPABILITY_SCOPE,
    AdmissibilityResult,
    BoundOutcome,
    CapabilityManifest,
    analyze_candidate,
)
from tos.dsl.outcome import (
    NoActionOutcome,
    Outcome,
    PortfolioVector,
    VectorRealization,
    VectorResolution,
    resolve_vector_realization,
)
from tos.dsl.proposal import (
    FLAT_QUANTITY_BASIS,
    Proposal,
    Proposer,
    build_flat,
    build_proposal,
)
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import (
    ADMISSIBLE_CONTEXT_SOURCES,
    ADMISSIBLE_KINDS,
    UNKNOWN,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    ScalarValue,
    TargetKind,
    TargetSpec,
    VectorInterdependence,
    eval_compare,
    evaluate_policy,
    resolve_operand,
    rule_fires,
)

__all__ = [
    # base
    "AllFalseAuthority",
    "ArtifactIntegrityError",
    "DecisionContextCapsuleRef",
    "IndependentIdArtifact",
    # vocabulary
    "ADMISSIBLE_CONTEXT_SOURCES",
    "ADMISSIBLE_KINDS",
    "UNKNOWN",
    "Compare",
    "CompareOp",
    "Decision",
    "DecisionKind",
    "DecisionPolicy",
    "Operand",
    "Rule",
    "ScalarValue",
    "TargetKind",
    "TargetSpec",
    "VectorInterdependence",
    "eval_compare",
    "evaluate_policy",
    "resolve_operand",
    "rule_fires",
    # candidate
    "AMBIENT_SYMBOLS",
    "ESCAPE_KINDS",
    "WILDCARD_TOKENS",
    "CandidateNode",
    "CandidateProgram",
    "iter_nodes",
    # admissibility
    "AdmissibilityAnalysis",
    "AdmissibilityVerdict",
    "admissibility_reasons",
    "analyze",
    "is_admissible",
    # proposal
    "FLAT_QUANTITY_BASIS",
    "Proposal",
    "Proposer",
    "build_flat",
    "build_proposal",
    # outcome
    "NoActionOutcome",
    "Outcome",
    "PortfolioVector",
    "VectorRealization",
    "VectorResolution",
    "resolve_vector_realization",
    # strategy
    "AuthoredStrategy",
    # determinism
    "EvaluationConfig",
    "EvaluationResult",
    "RecordedInputSignature",
    "build_environment",
    "evaluate",
    # bounds
    "BoundState",
    "degrades_to_no_action",
    "resolve_bound",
    "select_outcome",
    # evidence
    "PHASE1_CAPABILITY_SCOPE",
    "AdmissibilityResult",
    "BoundOutcome",
    "CapabilityManifest",
    "analyze_candidate",
]
