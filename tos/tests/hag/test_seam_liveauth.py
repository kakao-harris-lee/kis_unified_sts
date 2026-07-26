"""MANDATED test-only seam cross-check: hag collapse -> liveauth dual-control (design #20 §3.4/§3.5/§7).

hag **produces** the distinct effective-principal count (the collapse §5.1); the liveauth
``DualControlAttestation`` (``state.py:168``) carries the opaque principal coordinates
(``armer_principal`` / ``limit_change_approver_principal``) and the pre-computed
``distinct_approver_count`` (``state.py:180``) that ``rearm_dual_control_satisfied``
(``predicates.py:492``) consumes — liveauth does **not** import ``tos.hag``. **The central §3.5 (a)
proof**: the liveauth Path-1 distinctness is a pure string ``!=`` (``predicates.py:525``), which
**cannot** detect that two distinct identifier strings collapse to one natural person; the HAG
collapse can. This file imports the real liveauth symbols as a **test** to lock that boundary — and
the import-closure test separately proves ``tos.liveauth`` is **absent** from the hag runtime
closure (re-authored NOT AT ALL, imported NOT AT ALL).

Regime tag: predicate / model substrate only; HAG-EV-010 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    dual_control_effective_distinct,
    effective_principal_collapse,
    quorum_independence_satisfied,
)
from tos.liveauth import (
    DualControlAttestation,
    ReArmPathKind,
    rearm_dual_control_satisfied,
)

from ._hag_strategies import clean_attestation, clean_graph, same_person_graph


def test_liveauth_dual_control_attestation_carries_opaque_principal_coordinates() -> (
    None
):
    """(§3.5 (a)) liveauth's DualControlAttestation carries opaque principal coordinates + a count."""
    fields = DualControlAttestation.model_fields
    assert "armer_principal" in fields
    assert "limit_change_approver_principal" in fields
    assert (
        "distinct_approver_count" in fields
    )  # the count hag PRODUCES, liveauth CONSUMES


def test_liveauth_string_inequality_cannot_catch_same_person_but_hag_collapse_can() -> (
    None
):
    """(§3.5 (a) — the central proof) alice-svc-01 != alice-svc-02 to a string compare; ONE person to HAG."""
    armer = "alice-svc-01"
    approver = "alice-svc-02"
    # liveauth Path-1 distinctness is a pure string `!=` (predicates.py:525) — it sees two principals.
    assert (armer != approver) is True
    attestation = DualControlAttestation(
        armer_principal=armer,
        limit_change_approver_principal=approver,
        distinct_approver_count=2,  # a NAIVE upstream would inject 2 (string-distinct)
        path=ReArmPathKind.QUORUM,
    )
    # liveauth, fed the naive count, would accept it as dual-control-satisfied…
    assert rearm_dual_control_satisfied(attestation) is True
    # …but the HAG collapse (fed the real graph) sees ONE effective natural person.
    graph = same_person_graph()
    collapse = effective_principal_collapse(graph, [armer, approver])
    assert (
        collapse[armer] == collapse[approver]
    )  # ONE person — the string `!=` missed it
    # So the HAG dual-control predicate (collapse-before-count) correctly REJECTS the pair.
    atts = (
        clean_attestation(attestation_id="a1", principal_id=armer),
        clean_attestation(attestation_id="a2", principal_id=approver),
    )
    assert dual_control_effective_distinct(atts, graph) is False


def test_hag_produces_the_distinct_count_liveauth_consumes() -> None:
    """(§3.5 layering) A genuine 2-person graph yields a HAG-satisfied quorum that seeds count=2."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    atts = (
        clean_attestation(attestation_id="a1", principal_id="alice"),
        clean_attestation(attestation_id="a2", principal_id="bob"),
    )
    # HAG produces the distinct-count verdict (>= 2 effective persons).
    assert quorum_independence_satisfied(atts, graph, 2, frozenset()) is True
    # liveauth would then consume distinct_approver_count=2 (the count hag produced).
    attestation = DualControlAttestation(
        armer_principal="alice",
        limit_change_approver_principal="bob",
        distinct_approver_count=2,
        path=ReArmPathKind.QUORUM,
    )
    assert rearm_dual_control_satisfied(attestation) is True


def test_hag_does_not_reauthor_liveauth_rearm_instance() -> None:
    """(§0.4b/§3.5) hag re-authors none of the liveauth §17 re-arm consumption instance."""
    import tos.hag as hag

    # The liveauth re-arm consumption symbols are liveauth-owned — absent from the hag namespace.
    assert not hasattr(hag, "rearm_dual_control_satisfied")
    assert not hasattr(hag, "ReArmPathKind")
    assert not hasattr(hag, "Safe053VariantAttestation")
    assert not hasattr(hag, "DualControlAttestation")
