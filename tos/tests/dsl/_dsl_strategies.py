"""Shared valid-artifact builders + hypothesis strategies for the DSL property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design §firewall). The
``issue_*`` / ``*_required_kwargs`` builders populate every safety-load-bearing
covered field each artifact's issuance guard demands, so a "valid" fixture is
genuinely valid (never the all-null coverage illusion). The adversarial strategies
actively *generate* escape / ambient / unknown / wildcard candidates so the checker
is exercised against violations, not only positives (★ property strategy generates
violation cases).
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import DecisionContextCapsule, PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.dsl import (
    AdmissibilityResult,
    AuthoredStrategy,
    BoundOutcome,
    BoundState,
    CandidateNode,
    CandidateProgram,
    CapabilityManifest,
    Compare,
    CompareOp,
    Decision,
    DecisionContextCapsuleRef,
    DecisionKind,
    DecisionPolicy,
    NoActionOutcome,
    Operand,
    PortfolioVector,
    Proposal,
    Proposer,
    Rule,
    TargetKind,
    TargetSpec,
    VectorInterdependence,
    analyze,
)
from tos.dsl.candidate import AMBIENT_SYMBOLS, ESCAPE_KINDS, WILDCARD_TOKENS
from tos.dsl.vocabulary import ADMISSIBLE_KINDS, KIND_CONTEXT_REF

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
ENFORCEMENT_VERSION = "esc-checker-ev-l1-0"

#: Text bound to a required-covered field must be concrete (never the reserved
#: ``"TBD"`` placeholder the issuance guard rejects — design §3.2).
REQUIRED_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

_AMBIENT_SOURCES = ("clock", "network", "filesystem", "env", "global", "builtin")


# ---------------------------------------------------------------------------
# Capsule (read-only evaluation input)
# ---------------------------------------------------------------------------


def issue_capsule(**overrides: Any) -> DecisionContextCapsule:
    """Issue a valid Decision Context Capsule (every required covered field concrete)."""
    base: dict[str, Any] = {
        "issuer_principal_id": "principal-1",
        "critical_input_policy": PolicyRef(
            policy_id="cip-1", canonical_digest="cip-digest-1"
        ),
        "critical_input_snapshot": SnapshotRef(
            snapshot_id="snap-1", canonical_digest="snap-digest-1"
        ),
        "scope": CapsuleScope(
            environment="paper",
            account="acct-1",
            instrument="ES",
            decision_class="entry",
        ),
        "safety_critical_facts": SafetyCriticalFacts(
            account="acct-1",
            instrument="ES",
            direction="LONG",
            quantity_basis="RISK",
            unit="CONTRACT",
        ),
    }
    base.update(overrides)
    return DecisionContextCapsule.issue(scheme=SCHEME, **base)


def capref(capsule: DecisionContextCapsule | None = None) -> DecisionContextCapsuleRef:
    """A content-addressed bind to an issued capsule (defaults to a fresh one)."""
    cap = capsule or issue_capsule()
    return DecisionContextCapsuleRef(
        capsule_id=cap.capsule_id, canonical_digest=cap.canonical_digest
    )


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


def proposal_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Proposal issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "proposer": Proposer(strategy_id="astrat-1", strategy_version="digest-1"),
        "target_kind": TargetKind.ACTION,
        "account": "acct-1",
        "instrument": "ES",
        "direction": "LONG",
        "position_effect": "OPEN",
        "quantity_basis": "RISK",
        "rationale": "edge present",
        "decision_context_capsule": capref(),
        "dsl_version": "dsl-0",
        "config_version": "cfg-v1",
    }
    base.update(overrides)
    return base


def issue_proposal(**overrides: Any) -> Proposal:
    """Issue a valid :class:`Proposal`."""
    return Proposal.issue(scheme=SCHEME, **proposal_required_kwargs(**overrides))


# ---------------------------------------------------------------------------
# No-Action Outcome
# ---------------------------------------------------------------------------


def no_action_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """No-Action issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "outcome_id": "noact-1",
        "rationale": "no edge — hold",
        "decision_context_capsule": capref(),
        "strategy_version": "digest-1",
        "dsl_version": "dsl-0",
        "config_version": "cfg-v1",
    }
    base.update(overrides)
    return base


def issue_no_action(**overrides: Any) -> NoActionOutcome:
    """Issue a valid :class:`NoActionOutcome`."""
    return NoActionOutcome.issue(
        scheme=SCHEME, **no_action_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Portfolio Vector
# ---------------------------------------------------------------------------


def vector_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Portfolio-vector issuance kwargs with distinct, same-Capsule components."""
    ref = capref()
    comp_es = issue_proposal(instrument="ES", decision_context_capsule=ref)
    comp_nq = issue_proposal(instrument="NQ", decision_context_capsule=ref)
    base: dict[str, Any] = {
        "vector_id": "vec-1",
        "components": (comp_es, comp_nq),
        "interdependence": VectorInterdependence.ATOMIC,
        "decision_context_capsule": ref,
        "dsl_version": "dsl-0",
        "config_version": "cfg-v1",
    }
    base.update(overrides)
    return base


def issue_vector(**overrides: Any) -> PortfolioVector:
    """Issue a valid :class:`PortfolioVector`."""
    return PortfolioVector.issue(scheme=SCHEME, **vector_required_kwargs(**overrides))


# ---------------------------------------------------------------------------
# Authored Strategy (+ a simple config-driven policy)
# ---------------------------------------------------------------------------


def simple_policy() -> DecisionPolicy:
    """A policy that proposes an action iff ``config.enabled`` is True, else no-action."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="edge present",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account="acct-1",
            instrument="ES",
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="edge present",
        ),
    )
    hold = Decision(kind=DecisionKind.NO_ACTION, rationale="no edge — hold")
    rule = Rule(
        all_of=(
            Compare(
                left=Operand(ref=("config", "enabled")),
                op=CompareOp.EQ,
                right=Operand(const=True),
            ),
        ),
        decision=action,
    )
    return DecisionPolicy(rules=(rule,), default=hold)


def strategy_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Authored-strategy issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "dsl_version": "dsl-0",
        "config_binding_version": "cfg-bind-0",
        "policy": simple_policy(),
    }
    base.update(overrides)
    return base


def issue_strategy(**overrides: Any) -> AuthoredStrategy:
    """Issue a valid :class:`AuthoredStrategy`."""
    return AuthoredStrategy.issue(
        scheme=SCHEME, **strategy_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Enforcement-evidence records
# ---------------------------------------------------------------------------


def admissible_program() -> CandidateProgram:
    """A minimal admissible candidate program (a single capsule context read)."""
    return CandidateProgram(
        nodes=(CandidateNode(kind=KIND_CONTEXT_REF, source="capsule"),)
    )


def admissibility_result_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Admissibility-result kwargs whose verdict/reasons match the pure predicate."""
    candidate = overrides.pop("candidate", None) or admissible_program()
    computed = analyze(candidate)
    base: dict[str, Any] = {
        "result_id": "admres-1",
        "candidate": candidate,
        "verdict": computed.verdict,
        "reasons": computed.reasons,
        "enforcement_mechanism_version": ENFORCEMENT_VERSION,
        "dsl_version": "dsl-0",
    }
    base.update(overrides)
    return base


def issue_admissibility_result(**overrides: Any) -> AdmissibilityResult:
    """Issue a valid :class:`AdmissibilityResult`."""
    return AdmissibilityResult.issue(
        scheme=SCHEME, **admissibility_result_required_kwargs(**overrides)
    )


def capability_manifest_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Capability-manifest kwargs (Phase-1 constant scope)."""
    base: dict[str, Any] = {
        "manifest_id": "capman-1",
        "enforcement_mechanism_version": ENFORCEMENT_VERSION,
    }
    base.update(overrides)
    return base


def issue_capability_manifest(**overrides: Any) -> CapabilityManifest:
    """Issue a valid :class:`CapabilityManifest`."""
    return CapabilityManifest.issue(
        scheme=SCHEME, **capability_manifest_required_kwargs(**overrides)
    )


def bound_outcome_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Bound-outcome kwargs whose degrade flag matches its terminal state."""
    base: dict[str, Any] = {
        "bound_outcome_id": "bound-1",
        "terminal_state": BoundState.COMPLETED,
        "degraded_to_no_action": False,
        "enforcement_mechanism_version": ENFORCEMENT_VERSION,
    }
    base.update(overrides)
    return base


def issue_bound_outcome(**overrides: Any) -> BoundOutcome:
    """Issue a valid :class:`BoundOutcome`."""
    return BoundOutcome.issue(
        scheme=SCHEME, **bound_outcome_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies — candidate AST (admissible + adversarial)
# ---------------------------------------------------------------------------

_SAFE_SYMBOLS = st.sampled_from(["price", "vol", "edge", "regime", "atr"])


@st.composite
def admissible_nodes(draw: st.DrawFn, *, max_depth: int = 2) -> CandidateNode:
    """Generate a node that IS inside the Authoring Surface Vocabulary.

    With ``max_depth > 0`` the node may carry admissible children, so an admissible
    program is a genuine *tree*, not a flat list — this exercises the recursive
    ``iter_nodes`` walk (a flat top-level scan would still pass here, but see
    :func:`programs_with_buried_escape` for the negative that requires recursion).
    """
    kind = draw(st.sampled_from(sorted(ADMISSIBLE_KINDS)))
    children: tuple[CandidateNode, ...] = ()
    if max_depth > 0:
        children = tuple(
            draw(st.lists(admissible_nodes(max_depth=max_depth - 1), max_size=2))
        )
    if kind == KIND_CONTEXT_REF:
        source = draw(st.sampled_from(["capsule", "config"]))
        return CandidateNode(kind=kind, source=source, children=children)
    return CandidateNode(kind=kind, children=children)


@st.composite
def escape_nodes(draw: st.DrawFn) -> CandidateNode:
    """Generate a node that is NOT admissible: escape / ambient / wildcard / unknown."""
    which = draw(st.integers(min_value=0, max_value=4))
    if which == 0:  # non-vocabulary escape kind
        return CandidateNode(kind=draw(st.sampled_from(sorted(ESCAPE_KINDS))))
    if which == 1:  # ambient read source on a context_ref
        return CandidateNode(
            kind=KIND_CONTEXT_REF, source=draw(st.sampled_from(_AMBIENT_SOURCES))
        )
    if which == 2:  # ambient symbol name (any node kind)
        return CandidateNode(
            kind=draw(st.sampled_from(sorted(ADMISSIBLE_KINDS))),
            symbol=draw(st.sampled_from(sorted(AMBIENT_SYMBOLS))),
        )
    if which == 3:  # wildcard / "latest" scope
        return CandidateNode(
            kind=draw(st.sampled_from(sorted(ADMISSIBLE_KINDS))),
            scope=draw(st.sampled_from(sorted(WILDCARD_TOKENS))),
        )
    # novel/unknown kind — fail-closed (DCE-INV-006)
    novel = draw(
        st.text(min_size=1, max_size=10).filter(
            lambda s: s not in ADMISSIBLE_KINDS and s not in ESCAPE_KINDS
        )
    )
    return CandidateNode(kind=novel)


@st.composite
def admissible_programs(draw: st.DrawFn) -> CandidateProgram:
    """Generate a fully admissible candidate program (non-empty)."""
    nodes = draw(st.lists(admissible_nodes(), min_size=1, max_size=5))
    return CandidateProgram(nodes=tuple(nodes))


@st.composite
def programs_with_escape(draw: st.DrawFn) -> CandidateProgram:
    """Generate a program containing at least one inadmissible node."""
    good = draw(st.lists(admissible_nodes(), min_size=0, max_size=4))
    bad = draw(st.lists(escape_nodes(), min_size=1, max_size=3))
    combined = good + bad
    # Interleave deterministically by a drawn permutation index list.
    order = draw(st.permutations(list(range(len(combined)))))
    ordered = tuple(combined[i] for i in order)
    return CandidateProgram(nodes=ordered)


@st.composite
def programs_with_buried_escape(draw: st.DrawFn) -> CandidateProgram:
    """Generate an admissible-rooted program with an escape node buried in children.

    The escape sits ≥1 level below the root (wrapped in admissible ``const``
    parents whose own fields are all clean), so *only* a recursive walk
    (``iter_nodes`` descending into ``children``) can find it — a flat top-level
    scan would wrongly admit it. This is the negative that would regress silently
    if the walk ever stopped recursing (M-2 coverage).
    """
    escape = draw(escape_nodes())
    depth = draw(st.integers(min_value=1, max_value=3))
    node = escape
    for _ in range(depth):
        node = CandidateNode(kind="const", children=(node,))
    return CandidateProgram(nodes=(node,))
