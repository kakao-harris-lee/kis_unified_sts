"""MANDATED test-only seam cross-check: iap per-decision egress-currentness leaf -> cur (design #23 §0.4b/§3.5).

iap (ADR-002-021) owns a **per-decision** egress-currentness leaf ``active_egress_currentness``
(``iap/predicates.py:578``, IAP-EV-008) over a **single approval-consumption** — active bounded proof
AND not inferred-from-absence AND single authoritative consumption. cur **consumes** that leaf verdict
as **one** :class:`~tos.cur.state.CurrentnessDimension` coordinate (the TRADING_APPROVAL dimension)
and re-authors it **not at all** (§0.4b). This file imports the real iap predicate as a **test**; the
import-closure test proves ``tos.iap`` is **absent** from the cur runtime closure.

Regime tag: completeness predicate substrate only; CUR-EV-001 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.cur as cur
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    DimensionKey,
    dimension_positively_established,
    vector_complete,
)
from tos.iap.predicates import active_egress_currentness

from ._cur_strategies import (
    clean_dimension,
    clean_policy,
    clean_revision,
    clean_vector,
)


def test_iap_owns_the_per_decision_currentness_leaf() -> None:
    """(§3.5 iap predicates.py:578) iap owns active_egress_currentness — a single approval-consumption leaf.

    The iap leaf admits only on an active bounded proof, NOT inferred-from-absence, and a single
    authoritative consumption (a None on any fails closed). cur consumes this verdict; it does not
    re-author the leaf.
    """
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=False,
            single_authoritative_consumption=True,
        )
        is True
    )
    # inferred-from-absence ⇒ deny (absence of an invalidation event is not currentness).
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=True,
            single_authoritative_consumption=True,
        )
        is False
    )
    # a None active bounded proof fails closed.
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


def test_absent_approval_dimension_makes_vector_incomplete() -> None:
    """(§0.4b) A vector missing the TRADING_APPROVAL dimension is incomplete (aggregate-only axis)."""
    rev = clean_revision()
    without_approval = tuple(
        clean_dimension(dimension_key=key, revision=rev)
        for key in sorted(MANDATED_DIMENSION_FLOOR)
        if key is not DimensionKey.TRADING_APPROVAL
    )
    vec = clean_vector(revision=rev, dimensions=without_approval)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
