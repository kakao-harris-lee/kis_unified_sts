"""effective-principal collapse + quorum independence — the yolk (design #20 §4.1/§5.1/§7).

The central HAG-EV-001 substrate: two required human approvals must come from two distinct
**effective natural persons**, not two accounts / sessions / credentials of one person (§8 line
267). Covers collapse determinism, the conservative-merge (set) both-ways, ∅ / 1-person rejection,
and the three MAJOR-2 property cases: (11) an attesting principal absent from ``graph.nodes`` ⇒
``False``; (12) ``unresolved_control`` ``None`` / ``True`` ⇒ deny; (13) a per-edge ``resolved is
not True`` edge still merges (distinct-count reduction).

Regime tag: predicate / model substrate only; HAG-EV-001 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.hag import (
    ArtifactIntegrityError,
    AttestationDecision,
    ConflictRole,
    EffectiveControlEdge,
    EffectivePrincipalGraph,
    EffectivePrincipalNode,
    HumanDelegationRecord,
    RoleAssignment,
    RoleGrant,
    delegation_bounded_nontransitive,
    effective_principal_collapse,
    quorum_independence_satisfied,
    separation_of_duties_satisfied,
)

from ._hag_strategies import (
    SCHEME,
    clean_attestation,
    clean_graph,
    clean_two_person_attestations,
    graph_and_principals,
    malformed_edge_graph,
    same_person_graph,
)

# ---------------------------------------------------------------------------
# collapse — determinism + conservative merge (set both-ways, §4.7)
# ---------------------------------------------------------------------------


def test_distinct_persons_collapse_to_distinct_classes() -> None:
    """(§4.7 set-distinct) Genuinely distinct principals map to distinct classes (count = |persons|)."""
    graph = clean_graph(principal_ids=("alice", "bob", "carol"))
    collapse = effective_principal_collapse(graph, ["alice", "bob", "carol"])
    assert len({collapse["alice"], collapse["bob"], collapse["carol"]}) == 3


def test_same_person_multi_identity_collapses_to_one_class() -> None:
    """(§3.5 (a) — the yolk) alice-svc-01 / alice-svc-02 under a control edge collapse to ONE person."""
    graph = same_person_graph()
    collapse = effective_principal_collapse(
        graph, ["alice-svc-01", "alice-svc-02", "bob"]
    )
    assert collapse["alice-svc-01"] == collapse["alice-svc-02"]  # one effective person
    assert collapse["bob"] != collapse["alice-svc-01"]  # bob is genuinely distinct
    assert (
        len({collapse["alice-svc-01"], collapse["alice-svc-02"], collapse["bob"]}) == 2
    )


def test_collapse_is_deterministic() -> None:
    """(§7 determinism) The collapse mapping is identical across repeated calls (min representative)."""
    graph = same_person_graph()
    first = effective_principal_collapse(graph, ["alice-svc-01", "alice-svc-02", "bob"])
    second = effective_principal_collapse(
        graph, ["bob", "alice-svc-02", "alice-svc-01"]
    )
    assert first == second


def test_none_graph_yields_singletons() -> None:
    """(fail-closed) A None graph collapses nothing — each principal is its own singleton."""
    collapse = effective_principal_collapse(None, ["alice", "bob"])
    assert collapse["alice"] == "alice"
    assert collapse["bob"] == "bob"


def test_transitive_control_chain_collapses_component() -> None:
    """(union-find) A -> B -> C control chain collapses all three to one effective person."""
    graph = clean_graph(
        principal_ids=("a", "b", "c", "d"),
        edges=(
            EffectiveControlEdge(source="a", target="b", resolved=True),
            EffectiveControlEdge(source="b", target="c", resolved=None),
        ),
    )
    collapse = effective_principal_collapse(graph, ["a", "b", "c", "d"])
    assert collapse["a"] == collapse["b"] == collapse["c"]
    assert collapse["d"] != collapse["a"]


# ---------------------------------------------------------------------------
# property (13) — per-edge `resolved is not True` still merges (design #20 §7 case 13)
# ---------------------------------------------------------------------------


def test_property_13_unresolved_edge_merges_like_resolved() -> None:
    """(§7 case 13 / §4.1) An edge with ``resolved`` None OR False merges its endpoints (fail-closed)."""
    for unresolved in (None, False):
        graph = clean_graph(
            principal_ids=("x", "y"),
            edges=(EffectiveControlEdge(source="x", target="y", resolved=unresolved),),
        )
        collapse = effective_principal_collapse(graph, ["x", "y"])
        assert (
            collapse["x"] == collapse["y"]
        ), f"resolved={unresolved!r} must still merge (a fail-open would let it escape)"


def test_resolved_true_edge_also_merges() -> None:
    """(§4.1) A positively-resolved (confirmed) control edge merges too — the edge IS control."""
    graph = clean_graph(
        principal_ids=("x", "y"),
        edges=(EffectiveControlEdge(source="x", target="y", resolved=True),),
    )
    collapse = effective_principal_collapse(graph, ["x", "y"])
    assert collapse["x"] == collapse["y"]


# ---------------------------------------------------------------------------
# quorum independence — ∅ / 1-person / duplicate / degenerate N
# ---------------------------------------------------------------------------


def test_genuine_two_person_quorum_satisfied() -> None:
    """(positive) Two distinct principals, both APPROVE, in a resolved graph => quorum(2) satisfied."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    atts = clean_two_person_attestations()
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is True


def test_one_person_two_accounts_fails_quorum_two() -> None:
    """(§3.5 (a)) Two accounts of ONE person (collapsed) do NOT satisfy quorum(2)."""
    graph = same_person_graph()
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice-svc-01"),
        clean_attestation(attestation_id="a2", principal_id="alice-svc-02"),
    )
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is False


def test_empty_attestations_reject_but_genuine_quorum_passes() -> None:
    """(∅ both-ways) ∅ attestations => 0 < N => reject; a genuine 2-person set => pass."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    assert quorum_independence_satisfied([], graph, 2, frozenset()) is False
    assert (
        quorum_independence_satisfied(
            clean_two_person_attestations(), graph, 2, frozenset()
        )
        is True
    )


def test_single_attestation_fails_quorum_two() -> None:
    """(1-person) A single attestation is 1 < 2 distinct => reject for re-arm quorum(2)."""
    graph = clean_graph(principal_ids=("alice",))
    att = (clean_attestation(attestation_id="a1", principal_id="alice"),)
    assert quorum_independence_satisfied(att, graph, 2, frozenset()) is False


def test_degenerate_quorum_zero_or_none_rejected() -> None:
    """(§4.1 degenerate N) quorum_n of 0 / None is denial (no authority increase without a human)."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    atts = clean_two_person_attestations()
    assert quorum_independence_satisfied(atts, graph, 0, frozenset()) is False
    assert quorum_independence_satisfied(atts, graph, None, frozenset()) is False


def test_non_approve_decision_never_counts() -> None:
    """(§4.7 truthy-sealed gate) A DENY / ABSTAIN attestation never counts toward the quorum."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice"),
        clean_attestation(
            attestation_id="a2", principal_id="bob", decision=AttestationDecision.DENY
        ),
    )
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is False


def test_required_roles_must_be_covered() -> None:
    """(§5.1 (iv)) A required role not present among the attestations fails the quorum."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    atts = clean_two_person_attestations()  # roles: TRADE_APPROVER, LIVE_ARMER
    assert (
        quorum_independence_satisfied(
            atts, graph, 2, frozenset({ConflictRole.TRADE_APPROVER})
        )
        is True
    )
    assert (
        quorum_independence_satisfied(
            atts, graph, 2, frozenset({ConflictRole.POLICY_ADMIN})
        )
        is False
    )


# ---------------------------------------------------------------------------
# property (11) — unrepresented principal ⇒ False (MAJOR-2 collapse-bypass fail-open seal)
# ---------------------------------------------------------------------------


def test_property_11_unrepresented_principal_rejected() -> None:
    """(§7 case 11 / MAJOR-2) An attesting principal NOT in graph.nodes => False (not a singleton pass)."""
    graph = clean_graph(principal_ids=("alice",))  # bob is NOT in the graph
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice"),
        clean_attestation(attestation_id="a2", principal_id="bob"),  # unrepresented!
    )
    # A naive connected-component impl would count bob as an isolated singleton and pass quorum(2).
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is False


# ---------------------------------------------------------------------------
# property (12) — unresolved_control None/True ⇒ deny (MAJOR-2 graph-level whole-graph denial)
# ---------------------------------------------------------------------------


def test_property_12_unresolved_control_denies() -> None:
    """(§7 case 12 / MAJOR-2) unresolved_control None OR True => whole-graph denial (§8 line 271)."""
    atts = clean_two_person_attestations()
    for flag in (None, True):
        graph = EffectivePrincipalGraph.issue(
            scheme=SCHEME,
            graph_id="epg-un",
            graph_generation=1,
            nodes=(
                EffectivePrincipalNode(principal_id="alice"),
                EffectivePrincipalNode(principal_id="bob"),
            ),
            unresolved_control=flag,
        )
        assert (
            quorum_independence_satisfied(atts, graph, 2, frozenset()) is False
        ), f"unresolved_control={flag!r} must deny the whole graph"
    # …and a positively-resolved (False) graph admits the same genuine quorum.
    resolved = clean_graph(principal_ids=("alice", "bob"))
    assert quorum_independence_satisfied(atts, resolved, 2, frozenset()) is True


# ---------------------------------------------------------------------------
# property — the distinct-class count never exceeds the principal count (set both-ways)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# MAJOR-1 — malformed (None-endpoint) edge fail-open seal (design #20 code-review MAJOR-1)
# ---------------------------------------------------------------------------


def test_major1_none_endpoint_edge_forbids_resolved_false_claim() -> None:
    """(MAJOR-1 case a) A None-endpoint edge + unresolved_control=False is UNCONSTRUCTABLE."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        EffectivePrincipalGraph.issue(
            scheme=SCHEME,
            graph_id="epg-bad",
            graph_generation=1,
            nodes=(
                EffectivePrincipalNode(principal_id="alice-acct-1"),
                EffectivePrincipalNode(principal_id="alice-acct-2"),
            ),
            edges=(
                EffectiveControlEdge(source="alice-acct-1", target=None, resolved=None),
            ),
            unresolved_control=False,
        )


def test_major1_malformed_edge_graph_denies_all_collapse_gates() -> None:
    """(MAJOR-1 case b) A malformed-edge graph (unresolved_control=None) denies quorum/SoD/delegation."""
    graph = malformed_edge_graph(
        unresolved_control=None
    )  # constructible (denies), NOT False
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice-acct-1"),
        clean_attestation(attestation_id="a2", principal_id="alice-acct-2"),
    )
    # Without the gate, the broken edge drops => alice's 2 accounts count as 2 => quorum(2) passes.
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is False
    assignment = RoleAssignment(
        grants=(
            RoleGrant(principal_id="alice-acct-1", role=ConflictRole.TRADING_PROPOSER),
        )
    )
    assert separation_of_duties_satisfied(assignment, graph) is False
    delegation = HumanDelegationRecord.issue(
        scheme=SCHEME,
        delegation_id="del-1",
        grantor_principal="alice-acct-1",
        delegate_principal="alice-acct-2",
        role=ConflictRole.TRADE_APPROVER,
        transitive=False,
        delegation_generation=1,
    )
    assert (
        delegation_bounded_nontransitive(
            delegation, frozenset({ConflictRole.TRADE_APPROVER}), graph
        )
        is False
    )


def test_major1_complete_edges_with_false_claim_pass_positive_side() -> None:
    """(MAJOR-1 case c) A graph with only complete edges + unresolved_control=False judges normally."""
    graph = clean_graph(
        principal_ids=("alice", "bob"),
        edges=(EffectiveControlEdge(source="alice", target="bob", resolved=True),),
    )
    # alice controls bob => one effective person => quorum(2) correctly fails…
    atts = clean_two_person_attestations()
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is False
    # …and two genuinely distinct, fully-resolved principals pass.
    distinct = clean_graph(principal_ids=("alice", "bob"))
    assert quorum_independence_satisfied(atts, distinct, 2, frozenset()) is True


def test_major1_model_construct_bypass_is_caught_by_consume_gate() -> None:
    """(MAJOR-1 defence-in-depth) A model_construct graph bypassing the validator is still denied."""
    smuggled = EffectivePrincipalGraph.model_construct(
        graph_id="epg-smuggled",
        graph_generation=1,
        nodes=(
            EffectivePrincipalNode(principal_id="alice-acct-1"),
            EffectivePrincipalNode(principal_id="alice-acct-2"),
        ),
        edges=(
            EffectiveControlEdge(source="alice-acct-1", target=None, resolved=None),
        ),
        unresolved_control=False,  # a False claim smuggled past the validator
    )
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice-acct-1"),
        clean_attestation(attestation_id="a2", principal_id="alice-acct-2"),
    )
    assert quorum_independence_satisfied(atts, smuggled, 2, frozenset()) is False


@given(graph_and_principals())
def test_property_collapse_count_bounded_and_edges_reduce(
    value: tuple[EffectivePrincipalGraph, tuple[str, ...], tuple[tuple[str, str], ...]],
) -> None:
    """(§7 set both-ways) distinct classes <= |nodes|; every control edge merges its endpoints."""
    graph, node_ids, edge_pairs = value
    collapse = effective_principal_collapse(graph, list(node_ids))
    classes = {collapse[n] for n in node_ids}
    # (distinct direction) never more classes than nodes.
    assert len(classes) <= len(node_ids)
    # (merge direction) every edge's endpoints share a class (conservative merge, §4.1).
    for source, target in edge_pairs:
        assert collapse[source] == collapse[target]
