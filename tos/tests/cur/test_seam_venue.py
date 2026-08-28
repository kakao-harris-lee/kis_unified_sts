"""MANDATED test-only seam cross-check: venue per-decision egress-currentness leaf -> cur (design #23 §0.4b/§3.5).

venue (ADR-002-019) owns a **per-decision** egress-currentness leaf ``egress_currentness_active``
(``venue/predicates.py:493``, VTG-EV-007) over a **single Constraint Generation** — venue
``__init__.py:17`` verbatim: "active currentness is ADR-002-024-owned". cur **consumes** that leaf
verdict as **one** :class:`~tos.cur.state.CurrentnessDimension` coordinate (the CONSTRAINT dimension)
and re-authors it **not at all**: the aggregate axis (every dimension present + single revision +
policy complete) is cur's own, and a per-decision leaf structurally **cannot** detect an unrepresented
dimension, a mixed revision, or a policy under-declaration (§0.4b). This file imports the real venue
predicate as a **test**; the import-closure test proves ``tos.venue`` is **absent** from the cur
runtime closure.

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
from tos.venue.predicates import egress_currentness_active

from ._cur_strategies import (
    clean_dimension,
    clean_policy,
    clean_revision,
    clean_vector,
)


def test_venue_owns_the_per_decision_currentness_leaf() -> None:
    """(§3.5 venue predicates.py:493) venue owns egress_currentness_active — a single-generation leaf.

    The venue leaf admits only when currentness is actively established AND the request references
    EXACTLY the current Constraint Generation (a stale / future / None generation fails closed).
    cur consumes this verdict; it does not re-author the leaf.
    """
    assert (
        egress_currentness_active(True, 5, 5) is True
    )  # actively established, exact generation
    assert egress_currentness_active(True, 4, 5) is False  # stale generation
    assert (
        egress_currentness_active(None, 5, 5) is False
    )  # not actively established (absence)


def test_cur_reauthors_no_venue_leaf() -> None:
    """(§0.4b) cur re-authors NO venue egress_currentness_active leaf."""
    assert not hasattr(cur, "egress_currentness_active")


def test_cur_consumes_the_venue_leaf_verdict_as_one_dimension() -> None:
    """(§0.4b) The venue leaf verdict is injected as ONE CurrentnessDimension (CONSTRAINT) coordinate.

    The per-decision leaf's ``positively_established`` verdict becomes one dimension coordinate; cur
    judges only that the coordinate is present + established, not the venue business logic.
    """
    venue_verdict = egress_currentness_active(
        True, 5, 5
    )  # the injected per-decision leaf result
    rev = clean_revision()
    constraint_dim = clean_dimension(
        dimension_key=DimensionKey.CONSTRAINT,
        revision=rev,
        positively_established=venue_verdict,
    )
    assert dimension_positively_established(constraint_dim) is True


def test_completeness_is_the_aggregate_axis_no_leaf_can_detect() -> None:
    """(§0.4b — the airtight rebuttal) A vector missing the CONSTRAINT dimension is incomplete.

    No per-decision leaf (venue / iap / capsule) can detect an unrepresented dimension — only the
    aggregator can. A vector whose CONSTRAINT dimension is simply absent is incomplete even though
    every present leaf might individually be "current".
    """
    rev = clean_revision()
    without_constraint = tuple(
        clean_dimension(dimension_key=key, revision=rev)
        for key in sorted(MANDATED_DIMENSION_FLOOR)
        if key is not DimensionKey.CONSTRAINT
    )
    vec = clean_vector(revision=rev, dimensions=without_constraint)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
    # …but a full vector (CONSTRAINT present) is complete (both-ways).
    assert (
        vector_complete(
            clean_vector(revision=rev), clean_policy(), MANDATED_DIMENSION_FLOOR
        )
        is True
    )
