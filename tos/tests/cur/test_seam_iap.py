"""MANDATED test-only seam cross-check: iap per-decision egress-currentness leaf -> cur (design #23 §0.4b/§3.5)."""

from __future__ import annotations

import tos.cur as cur
from tos.cur import (
    DimensionKey,
    dimension_positively_established,
)
from tos.iap.predicates import active_egress_currentness

from ._cur_strategies import (
    clean_dimension,
    clean_revision,
)


def test_iap_owns_the_per_decision_currentness_leaf() -> None:
    """(§3.5 iap predicates.py:578) iap owns active_egress_currentness — a single approval-consumption leaf."""
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=False,
            single_authoritative_consumption=True,
        )
        is True
    )
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=True,
            single_authoritative_consumption=True,
        )
        is False
    )
    assert (
        active_egress_currentness(
            active_bounded_proof=None,
            inferred_from_absence=False,
            single_authoritative_consumption=True,
        )
        is False
    )


def test_cur_reauthors_no_iap_leaf() -> None:
    """(§0.4b) cur re-authors NO iap active_egress_currentness leaf."""
    assert not hasattr(cur, "active_egress_currentness")


def test_cur_consumes_the_iap_leaf_verdict_as_one_dimension() -> None:
    """(§0.4b) The iap leaf verdict is injected as ONE CurrentnessDimension (TRADING_APPROVAL) coordinate."""
    iap_verdict = active_egress_currentness(
        active_bounded_proof=True,
        inferred_from_absence=False,
        single_authoritative_consumption=True,
    )
    rev = clean_revision()
    approval_dim = clean_dimension(
        dimension_key=DimensionKey.TRADING_APPROVAL,
        revision=rev,
        positively_established=iap_verdict,
    )
    assert dimension_positively_established(approval_dim) is True
