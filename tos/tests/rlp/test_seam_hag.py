"""MANDATED test-only seam cross-check: hag effective-principal + quorum ↔ rlp (design #25 §3.5/§0.4e).

hag (ADR-002-015) owns the human-authority general model — ``effective_principal_collapse`` and
``quorum_independence_satisfied`` (``hag/predicates.py``). RLP-INV-014 (independent acceptance) / §18
promotion quorum / §22 role separation are **hag-owned**; rlp **consumes** the hag verdict as an
injected ``effective_principal_verdict`` / ``reviewer_quorum`` coordinate and **re-authors none of
it** (RLP-EV-008 is ``EV-L2/3+Security``). This file imports the real hag predicates as a **test** to
prove the ownership; the import-closure test proves ``tos.hag`` is **absent** from the rlp runtime
closure.

Regime tag: predicate substrate only; RLP-EV-008 NOT_IMPLEMENTED (``EV-L2/3+Security``); EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.rlp as rlp
from tos.hag import effective_principal_collapse, quorum_independence_satisfied
from tos.rlp import ProductionScopePromotionDecision


def test_hag_owns_effective_principal_and_quorum() -> None:
    """(§0.4e) The effective-principal collapse + quorum-independence predicates live in hag, not rlp."""
    assert callable(effective_principal_collapse)
    assert callable(quorum_independence_satisfied)


def test_rlp_reauthors_no_hag_quorum_or_collapse() -> None:
    """(§0.4e / §3.4) rlp re-authors NO effective-principal collapse / quorum-independence predicate."""
    assert not hasattr(rlp, "effective_principal_collapse")
    assert not hasattr(rlp, "quorum_independence_satisfied")


def test_rlp_consumes_hag_verdict_as_injected_coordinate() -> None:
    """(§0.4e) rlp carries the hag verdict as an injected coordinate, never a re-authoring.

    The promotion decision carries ``effective_principal_verdict`` (hag verdict) and
    ``reviewer_quorum`` (hag quorum) as injected fields — rlp consumes them, it does not compute the
    collapse graph or the quorum rule.
    """
    fields = ProductionScopePromotionDecision.model_fields
    assert "effective_principal_verdict" in fields
    assert "reviewer_quorum" in fields
    # the verdict is an injected bool coordinate (positive-polarity), not a re-derived graph.
    decision = ProductionScopePromotionDecision.model_construct(
        decision_id="d", effective_principal_verdict=True, reviewer_quorum=2
    )
    assert decision.effective_principal_verdict is True
    assert decision.reviewer_quorum == 2
