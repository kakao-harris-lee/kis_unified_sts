"""Shared valid-artifact builders + strategies for the hag property tests (design #20 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #20 §0.3). The builders enforce
the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely*
independent / bound, never a permissive shortcut):

* a **clean** graph declares distinct, fully-resolved (``unresolved_control=False``) nodes with no
  collapsing control edge, so a genuine quorum is achievable;
* a **clean** attestation set carries distinct principals all in the graph, all ``APPROVE``;
* the **∅ strategies** deliberately generate empty sets / graphs so the ∅-void guards are actually
  exercised (the #10 lesson — a strategy that never emits ∅ leaves the ∅ branch untested).

Every quorum / age value is an explicit fixture int — nothing here is a *policy* number; the real
hag bounds are Verification-Profile injected and all null / TBD in Phase 1 (design #20 §8.1). The
reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.hag import (
    AttestationDecision,
    ConflictRole,
    EffectiveControlEdge,
    EffectivePrincipalGraph,
    EffectivePrincipalNode,
    HumanApprovalAttestation,
    HumanApprovalRequest,
    HumanApprovalSet,
)

#: The injected provisional canonicalizer (REUSE, design #20 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])


# ---------------------------------------------------------------------------
# Clean builders (genuinely independent — the #8 lesson)
# ---------------------------------------------------------------------------


def clean_graph(
    *,
    principal_ids: tuple[str, ...] = ("alice", "bob", "carol"),
    edges: tuple[EffectiveControlEdge, ...] = (),
    unresolved_control: bool | None = False,
) -> EffectivePrincipalGraph:
    """A fully-resolved effective-principal graph with distinct nodes (no collapsing edge)."""
    return EffectivePrincipalGraph.issue(
        scheme=SCHEME,
        graph_id="epg-1",
        graph_generation=1,
        nodes=tuple(EffectivePrincipalNode(principal_id=p) for p in principal_ids),
        edges=edges,
        unresolved_control=unresolved_control,
    )


def malformed_edge_graph(
    *,
    unresolved_control: bool | None = None,
) -> EffectivePrincipalGraph:
    """A graph carrying a ``None``-endpoint control edge (MAJOR-1 regression fixture).

    The collapse cannot merge a ``None`` endpoint, so such an edge is a malformed / incompletely
    -resolved control fact. It is constructible **only** with ``unresolved_control`` ``None`` /
    ``True`` — the :class:`EffectivePrincipalGraph` validator rejects the ``False`` combination
    (MAJOR-1). Two accounts of one person (``alice-acct-1`` / ``alice-acct-2``) with a broken edge
    between them would, without the gate, count as two distinct principals (the ADR §2:40 attack).
    """
    return EffectivePrincipalGraph.issue(
        scheme=SCHEME,
        graph_id="epg-malformed",
        graph_generation=1,
        nodes=(
            EffectivePrincipalNode(principal_id="alice-acct-1"),
            EffectivePrincipalNode(principal_id="alice-acct-2"),
        ),
        edges=(
            EffectiveControlEdge(
                source="alice-acct-1",
                target=None,
                relation="mint-credential",
                resolved=None,
            ),
        ),
        unresolved_control=unresolved_control,
    )


def same_person_graph() -> EffectivePrincipalGraph:
    """A graph where ``alice-svc-01`` controls ``alice-svc-02`` — one effective person, plus ``bob``.

    The §3.5 (a) example: the liveauth string ``!=`` sees two distinct principals, but the HAG
    collapse merges them into one natural person via the (unresolved) control edge.
    """
    return clean_graph(
        principal_ids=("alice-svc-01", "alice-svc-02", "bob"),
        edges=(
            EffectiveControlEdge(
                source="alice-svc-01",
                target="alice-svc-02",
                relation="mint-credential",
                resolved=None,  # UNRESOLVED — still merged (fail-closed, §4.1)
            ),
        ),
    )


def clean_attestation(
    *,
    attestation_id: str,
    principal_id: str,
    request_digest: str = "req-digest",
    role: ConflictRole = ConflictRole.TRADE_APPROVER,
    decision: AttestationDecision = AttestationDecision.APPROVE,
) -> HumanApprovalAttestation:
    """A digest-verified attestation (id ⊥ digest, all-false authority)."""
    return HumanApprovalAttestation.issue(
        scheme=SCHEME,
        attestation_id=attestation_id,
        request_digest=request_digest,
        principal_id=principal_id,
        effective_principal_graph_generation=1,
        role=role,
        decision=decision,
        issue_generation=2,
    )


def clean_two_person_attestations(
    *,
    request_digest: str = "req-digest",
) -> tuple[HumanApprovalAttestation, HumanApprovalAttestation]:
    """Two distinct-principal attestations (alice + bob), both ``APPROVE`` — a genuine quorum of 2."""
    return (
        clean_attestation(
            attestation_id="att-alice",
            principal_id="alice",
            request_digest=request_digest,
            role=ConflictRole.TRADE_APPROVER,
        ),
        clean_attestation(
            attestation_id="att-bob",
            principal_id="bob",
            request_digest=request_digest,
            role=ConflictRole.LIVE_ARMER,
        ),
    )


def clean_request(
    *,
    request_id: str = "req-1",
    request_type=None,
) -> HumanApprovalRequest:
    """A digest-verified human approval request (id ⊥ digest, all-false authority)."""
    from tos.hag import AuthorityClass

    return HumanApprovalRequest.issue(
        scheme=SCHEME,
        request_id=request_id,
        request_type=(
            request_type if request_type is not None else AuthorityClass.APPROVE_REARM
        ),
        nonce="nonce-1",
        creation_generation=1,
        requested_action="arm-live",
        maximum_authority=AuthorityClass.APPROVE_REARM,
        decision_context_capsule_id="dcc-1",
        decision_context_capsule_digest="dcc-digest",
        policy_generation=1,
        graph_generation=1,
    )


def clean_approval_set(
    *,
    set_id: str = "set-1",
    request_digest: str = "req-digest",
) -> HumanApprovalSet:
    """A digest-verified approval set of two distinct-principal attestations (all-false authority)."""
    return HumanApprovalSet.issue(
        scheme=SCHEME,
        set_id=set_id,
        attestations=clean_two_person_attestations(request_digest=request_digest),
        policy_generation=1,
        graph_generation=1,
        bound_request_digest=request_digest,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies (∅ deliberately reachable — the #10 lesson)
# ---------------------------------------------------------------------------


@st.composite
def graph_and_principals(
    draw: st.DrawFn,
) -> tuple[EffectivePrincipalGraph, tuple[str, ...], tuple[tuple[str, str], ...]]:
    """A random graph of distinct nodes + a random set of collapsing control edges.

    Returns ``(graph, node_ids, edge_pairs)`` where ``edge_pairs`` are the (source, target) edges
    added (each unresolved), so a property test can predict the collapse components.
    """
    node_ids = draw(
        st.lists(st.text(min_size=1, max_size=4), min_size=1, max_size=6, unique=True)
    )
    edge_pairs = draw(
        st.lists(
            st.tuples(st.sampled_from(node_ids), st.sampled_from(node_ids)),
            max_size=5,
        )
    )
    edges = tuple(
        EffectiveControlEdge(source=s, target=t, resolved=None) for s, t in edge_pairs
    )
    graph = clean_graph(principal_ids=tuple(node_ids), edges=edges)
    return graph, tuple(node_ids), tuple(edge_pairs)
