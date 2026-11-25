"""MANDATED test-only seam cross-check: venue per-decision egress-currentness leaf -> cur (design #23 §0.4b/§3.5)."""

from __future__ import annotations

import tos.cur as cur
from tos.cur import (
    DimensionKey,
    dimension_positively_established,
)
from tos.venue.predicates import egress_currentness_active

from ._cur_strategies import (
    clean_dimension,
    clean_revision,
)


def test_venue_owns_the_per_decision_currentness_leaf() -> None:
    """(§3.5 venue predicates.py:493) venue owns egress_currentness_active — a single-generation leaf."""
    assert egress_currentness_active(True, 5, 5) is True
    assert egress_currentness_active(True, 4, 5) is False
    assert egress_currentness_active(None, 5, 5) is False


def test_cur_reauthors_no_venue_leaf() -> None:
    """(§0.4b) cur re-authors NO venue egress_currentness_active leaf."""
    assert not hasattr(cur, "egress_currentness_active")


def test_cur_consumes_the_venue_leaf_verdict_as_one_dimension() -> None:
    """(§0.4b) The venue leaf verdict is injected as ONE CurrentnessDimension (CONSTRAINT) coordinate."""
    venue_verdict = egress_currentness_active(True, 5, 5)
    rev = clean_revision()
    constraint_dim = clean_dimension(
        dimension_key=DimensionKey.CONSTRAINT,
        revision=rev,
        positively_established=venue_verdict,
    )
    assert dimension_positively_established(constraint_dim) is True
