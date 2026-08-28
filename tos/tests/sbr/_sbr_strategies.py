"""Shared valid-artifact builders + strategies for the sbr property tests (design #17 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #17 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be
*genuinely* admissible, never a permissive shortcut):

* a **clean** inventory cut covers every required dependency kind, has nothing unbounded, a
  non-ambiguous time, and every conservative-evidence witness positively present;
* a **clean** obligation graph is a genuine acyclic DAG whose every obligation reached
  ``SATISFIED`` within its acceptable set and whose independent-review obligations are
  independently satisfied;
* a **clean** ``IsolationFacts`` has all eight conditions positively ``True``;
* a **clean** readiness decision is a positive ``READY`` with the package / cut / obligation-set
  digests present and every fold result ``SATISFIED``;
* the **∅ strategies** deliberately generate empty sets / graphs so the ∅-void guards are
  actually exercised (the #10 lesson — a strategy that never emits an empty set leaves the ∅
  branch untested).

Every bound / age / generation value is an explicit fixture int — nothing here is a *policy*
number; the real recovery bounds are Verification-Profile injected and all null / PROPOSED in
Phase 1 (design #17 §8). The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.sbr import (
    BrokerReadSequence,
    IsolationFacts,
    ObligationResult,
    ReadinessVerdict,
    RecoveryBarrierPolicy,
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryReadinessDecision,
    RecoveryScope,
    RecoverySession,
    RecoveryTrigger,
    SessionState,
)

#: The injected provisional canonicalizer (REUSE, design #17 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: The six obligation result classes (only ``SATISFIED`` passes an obligation, §2.2(5)).
OBLIGATION_RESULTS = st.sampled_from(list(ObligationResult))
#: The three readiness verdicts.
READINESS_VERDICTS = st.sampled_from(list(ReadinessVerdict))
#: A representative required dependency-kind universe (§12 line 318-331 groups).
DEPENDENCY_KINDS: frozenset[str] = frozenset(
    {
        "order",
        "attempt",
        "fill",
        "position",
        "capacity",
        "external",
        "protective",
        "broker",
    }
)


# ---------------------------------------------------------------------------
# Clean builders (genuinely admissible — the #8 lesson)
# ---------------------------------------------------------------------------


def clean_policy(kinds: frozenset[str] = DEPENDENCY_KINDS) -> RecoveryBarrierPolicy:
    """A policy declaring a non-empty required-dependency-kind set (§5.1)."""
    return RecoveryBarrierPolicy(
        policy_id="sbr-policy-1", required_dependency_kinds=kinds
    )


def clean_inventory_cut(
    *, required: frozenset[str] = DEPENDENCY_KINDS
) -> RecoveryInventoryCut:
    """A complete, bounded, non-ambiguous inventory cut (§5.1 positive side)."""
    return RecoveryInventoryCut.issue(
        scheme=SCHEME,
        session_id="sbr-sess-1",
        recovery_generation=3,
        required_dependency_kinds=required,
        observed_dependency_kinds=required,
        unbounded_dependency_kinds=frozenset(),
        time_ambiguous=False,
        unobserved_window_assumptions_present=True,
        max_adverse_bounds_present=True,
        required_repeat_observations_met=True,
    )


def obligation(
    oid: str,
    *,
    prerequisites: tuple[str, ...] = (),
    result: ObligationResult = ObligationResult.SATISFIED,
    acceptable: tuple[ObligationResult, ...] = (ObligationResult.SATISFIED,),
    independent_review_required: bool | None = None,
    independent_review_satisfied: bool | None = None,
) -> RecoveryObligation:
    """One recovery obligation (content-addressed digest-bound record)."""
    return RecoveryObligation.issue(
        scheme=SCHEME,
        obligation_id=oid,
        prerequisite_ids=frozenset(prerequisites),
        result=result,
        acceptable_results=frozenset(acceptable),
        independent_review_required=independent_review_required,
        independent_review_satisfied=independent_review_satisfied,
    )


def clean_obligation_set() -> frozenset[RecoveryObligation]:
    """A genuine acyclic, all-SATISFIED obligation set (§5.2 positive side)."""
    return frozenset(
        {
            obligation("a"),
            obligation("b", prerequisites=("a",)),
            obligation("c", prerequisites=("a", "b")),
        }
    )


def clean_isolation_facts() -> IsolationFacts:
    """All eight isolation conditions positively proven (§5.5 positive side)."""
    return IsolationFacts(
        distinct_capacity_domain=True,
        broker_session_isolated=True,
        margin_collateral_safe=True,
        no_protective_boundary_crossing=True,
        config_authority_time_compatible=True,
        external_non_trade_unmappable=True,
        final_egress_scope_enforceable=True,
        hard_safety_envelope_satisfied=True,
    )


def clean_scope() -> RecoveryScope:
    """An identified restricted candidate scope (§5.5)."""
    return RecoveryScope(
        scope_id="acct-restricted", excluded_scopes=frozenset({"acct-broad"})
    )


def clean_broker_reads() -> BrokerReadSequence:
    """A bounded-convergence, stable, intervening-events-reflected read sequence (§6.4 positive)."""
    return BrokerReadSequence(
        bounded_convergence_proven=True,
        field_specific_proof_stable=True,
        intervening_events_reflected=True,
    )


def issue_session(
    *, state: SessionState = SessionState.READY, session_id: str = "sbr-sess-1"
) -> RecoverySession:
    """A digest-verified recovery session (id ⊥ digest)."""
    return RecoverySession.issue(
        scheme=SCHEME,
        session_id=session_id,
        recovery_generation=3,
        state=state,
        trigger_digest="sbr-trigger-digest",
    )


def issue_trigger(trigger_id: str = "sbr-trigger-1") -> RecoveryTrigger:
    """A content-addressed recovery trigger."""
    return RecoveryTrigger.issue(
        scheme=SCHEME,
        trigger_id=trigger_id,
        trigger_class="COLD_START",
        initial_scope="acct",
        recovery_generation=3,
    )


def issue_decision(
    *,
    verdict: ReadinessVerdict = ReadinessVerdict.READY,
    decision_id: str = "sbr-dec-1",
    recovery_generation: int = 3,
    all_results: tuple[ObligationResult, ...] = (
        ObligationResult.SATISFIED,
        ObligationResult.SATISFIED,
    ),
    package_digest: str | None = "sbr-pkg-digest",
    inventory_cut_digest: str | None = "sbr-cut-digest",
    obligation_set_digest: str | None = "sbr-obl-digest",
) -> RecoveryReadinessDecision:
    """A digest-verified readiness decision (id ⊥ digest)."""
    return RecoveryReadinessDecision.issue(
        scheme=SCHEME,
        decision_id=decision_id,
        issuer="sbr-issuer",
        session_id="sbr-sess-1",
        recovery_generation=recovery_generation,
        verdict=verdict,
        package_digest=package_digest,
        inventory_cut_digest=inventory_cut_digest,
        obligation_set_digest=obligation_set_digest,
        all_results=all_results,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies (∅ deliberately reachable — the #10 lesson)
# ---------------------------------------------------------------------------


@st.composite
def graph_and_trigger(
    draw: st.DrawFn,
) -> tuple[dict[str, frozenset[str]], str]:
    """A random dependency graph + a trigger node drawn from it (∅ graph reachable)."""
    nodes = draw(
        st.lists(st.text(min_size=1, max_size=3), min_size=1, max_size=6, unique=True)
    )
    graph: dict[str, frozenset[str]] = {}
    for node in nodes:
        deps = draw(st.sets(st.sampled_from(nodes), max_size=len(nodes)))
        graph[node] = frozenset(deps)
    trigger = draw(st.sampled_from(nodes))
    return graph, trigger


@st.composite
def acyclic_obligation_set(draw: st.DrawFn) -> frozenset[RecoveryObligation]:
    """A random genuinely-acyclic obligation set, every obligation SATISFIED (∅ excluded here)."""
    size = draw(st.integers(min_value=1, max_value=6))
    ids = [f"ob-{i}" for i in range(size)]
    obligations = []
    for index, oid in enumerate(ids):
        # prerequisites only reference strictly-earlier ids => acyclic by construction.
        prereqs = draw(
            st.sets(
                st.sampled_from(ids[:index]) if index else st.nothing(), max_size=index
            )
        )
        obligations.append(obligation(oid, prerequisites=tuple(prereqs)))
    return frozenset(obligations)
