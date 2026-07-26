"""MANDATED test-only seam cross-check: iap single-use consumption shape ↔ rlp (design #25 §3.5/§0.4g).

iap (ADR-002-023) owns the single-use consumption **shape** — ``ApprovalResult`` (truthy-untestable
``StrEnum``, gate ``is ApprovalResult.APPROVE``) and "eligibility to be consumed once"
(``iap/predicates.py``). rlp's ``promotion_progressive_single_use`` **re-expresses this shape
locally** (``PromotionResult`` gate ``is ELIGIBLE_TO_REQUEST_NEW_SCOPE`` + single-use) — a
**REUSE-BY-SHAPE, not an import** (§0.4g; the ``_NonTruthyStrEnum`` is authored locally-fresh, sibling
edge 0). This file imports the real iap enum as a **test** to confirm the shape precedent; the
import-closure test proves ``tos.iap`` is **absent** from the rlp runtime closure.

Regime tag: predicate substrate only; RLP-EV-007 NOT_IMPLEMENTED (``EV-L2/3+Security``); EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.rlp as rlp
from tos.iap import ApprovalResult
from tos.rlp import PromotionResult, promotion_progressive_single_use

from ._rlp_strategies import (
    PROMOTION_PREDECESSOR_FLOOR,
    clean_decision,
    clean_promotion_policy,
)


def test_iap_approval_result_is_the_single_use_shape_precedent() -> None:
    """(§0.4g) iap ApprovalResult is a truthy-untestable single-use consumption enum (the precedent)."""
    with pytest.raises(TypeError):
        bool(ApprovalResult.DENY)
    # the mandated iap consume gate is the positive-identity comparison.
    assert (ApprovalResult.APPROVE is ApprovalResult.APPROVE) is True


def test_rlp_reexpresses_the_shape_locally_not_by_import() -> None:
    """(§0.4g) rlp's PromotionResult is a locally-fresh non-truthy enum — NOT iap's ApprovalResult."""
    # rlp does not import / re-export the iap enum.
    assert not hasattr(rlp, "ApprovalResult")
    # rlp's own promotion enum is distinct and truthy-untestable in the same shape.
    with pytest.raises(TypeError):
        bool(PromotionResult.DENY)
    assert (
        PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE.value
        == "ELIGIBLE_TO_REQUEST_NEW_SCOPE"
    )


def test_rlp_promotion_single_use_mirrors_iap_consume_once() -> None:
    """(§0.4g / §18 line 464) rlp promotion is single-use — a consumed decision cannot be reused."""
    policy = clean_promotion_policy()
    # fresh + eligible ⇒ consumable once.
    assert (
        promotion_progressive_single_use(
            clean_decision(single_use_consumed=False),
            policy,
            PROMOTION_PREDECESSOR_FLOOR,
        )
        is True
    )
    # consumed ⇒ reject reuse (the iap "consumed once" shape).
    assert (
        promotion_progressive_single_use(
            clean_decision(single_use_consumed=True),
            policy,
            PROMOTION_PREDECESSOR_FLOOR,
        )
        is False
    )
    # unknown consumption (None) ⇒ reject reuse (negative-polarity fail-closed).
    assert (
        promotion_progressive_single_use(
            clean_decision(single_use_consumed=None),
            policy,
            PROMOTION_PREDECESSOR_FLOOR,
        )
        is False
    )
