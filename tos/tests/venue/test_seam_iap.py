"""MANDATED test-only seam cross-check: venue -> iap + shared closure property (design #19 §3.4(d)/§0.4d/§7).

venue **produces** two digests the iap ``ProposalApprovalRequest`` consumes by injection
(``venue_snapshot_digest`` ``iap/records.py:256`` / ``venue_admissibility_decision_digest``
``iap/records.py:257``) — iap does not import ``tos.venue``. **admissibility ≠ approval** (§30
item 12): iap binds the venue digests into an approval request, but admissibility is only one
input to approval, never approval itself.

It also locks the **shared closure property contract** (§0.4d / MINOR-5): the venue
``material_change_closure`` and the iap ``invalidation_closure`` (``iap/predicates.py:347``) are
structurally isomorphic pure graph reachability. venue re-authors the closure **locally** (no
``tos.iap`` import — sibling edge 0); the DRY is preserved by this property contract, not by code
sharing. This file imports the real iap ``invalidation_closure`` as a **test** to prove the
isomorphism — and the import-closure test separately proves ``tos.iap`` is **absent** from the
venue package closure.

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from tos.iap import ProposalApprovalRequest, invalidation_closure
from tos.venue import (
    material_change_closure,
    venue_admissibility_decision_digest_of,
    venue_snapshot_digest_of,
)

from ._venue_strategies import clean_decision, clean_snapshot, graph_and_trigger


def test_iap_request_carries_both_venue_digest_slots() -> None:
    """(seam) The iap ProposalApprovalRequest carries both venue digest slots (str | None)."""
    fields = ProposalApprovalRequest.model_fields
    assert "venue_snapshot_digest" in fields
    assert "venue_admissibility_decision_digest" in fields
    request = ProposalApprovalRequest(
        venue_snapshot_digest=None, venue_admissibility_decision_digest=None
    )
    assert request.venue_snapshot_digest is None
    assert request.venue_admissibility_decision_digest is None


def test_venue_digests_fill_the_iap_slots_admissibility_is_not_approval() -> None:
    """(seam positive, §30 item 12) venue snapshot + decision digests fill the iap approval-request slots."""
    snapshot = clean_snapshot()
    decision = clean_decision()
    snap_digest = venue_snapshot_digest_of(snapshot)
    dec_digest = venue_admissibility_decision_digest_of(decision)
    request = ProposalApprovalRequest(
        venue_snapshot_digest=snap_digest,
        venue_admissibility_decision_digest=dec_digest,
    )
    # iap binds the venue digests — but admissibility is only an INPUT to approval, not approval.
    assert request.venue_snapshot_digest == snapshot.canonical_digest
    assert request.venue_admissibility_decision_digest == decision.canonical_digest


def test_shared_closure_fixed_graph_agrees_with_iap() -> None:
    """(shared-closure contract) venue material_change_closure == iap invalidation_closure on a fixed graph."""
    graph = {
        "t": frozenset({"a", "b"}),
        "a": frozenset({"c"}),
        "b": frozenset({"c", "d"}),
    }
    expected = frozenset({"t", "a", "b", "c", "d"})
    assert invalidation_closure(graph, "t") == expected
    assert material_change_closure(graph, frozenset({"t"})) == expected


def test_shared_closure_empty_graph_agrees() -> None:
    """(∅ axiom) Both yield the minimal closure {trigger} on an empty graph."""
    assert invalidation_closure({}, "t") == frozenset({"t"})
    assert material_change_closure({}, frozenset({"t"})) == frozenset({"t"})


def test_shared_closure_uncertain_edge_agrees() -> None:
    """(uncertain-widen axiom) Both expand an uncertain edge identically."""
    graph = {"t": frozenset({"a"})}
    uncertain = {"a": frozenset({"x"})}
    assert "x" in invalidation_closure(graph, "t", uncertain=uncertain)
    assert "x" in material_change_closure(graph, frozenset({"t"}), unproven=uncertain)


@given(graph_and_trigger())
def test_property_venue_and_iap_closures_agree(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) On any graph, venue single-trigger closure == iap closure."""
    graph, trigger = graph_and_trigger_value
    iap_result = invalidation_closure(graph, trigger)
    venue_result = material_change_closure(graph, frozenset({trigger}))
    assert iap_result == venue_result


@given(graph_and_trigger())
def test_property_venue_and_iap_expand_uncertain_identically(
    graph_and_trigger_value: tuple[dict[str, frozenset[str]], str],
) -> None:
    """(shared-closure property) An uncertain edge widens both closures identically."""
    graph, trigger = graph_and_trigger_value
    uncertain = {trigger: frozenset({"uncertain-node"})}
    iap_result = invalidation_closure(graph, trigger, uncertain=uncertain)
    venue_result = material_change_closure(
        graph, frozenset({trigger}), unproven=uncertain
    )
    assert iap_result == venue_result
    assert "uncertain-node" in venue_result
