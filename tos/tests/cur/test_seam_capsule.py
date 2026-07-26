"""MANDATED test-only seam cross-check: capsule Context generation leaf -> cur (design #23 §0.4b/§3.5).

capsule (ADR-002-018) owns the Decision Context generation ordering leaf ``generation_can_authorize``
(``capsule/context_generation.py:16``) and the per-decision egress-currentness leaf
``egress_currentness_ok`` (``capsule/predicates.py:656``, CII-EV-009). The Context generation is the
**injection coordinate** for cur's CONTEXT dimension (v1.1 MAJOR-2 — CONTEXT is a SEPARATE dimension
from CRITICAL_INPUT). cur **consumes** the capsule verdict as **one** :class:`~tos.cur.state.
CurrentnessDimension` (CONTEXT) and re-authors it **not at all** (§0.4b). This file imports the real
capsule predicate as a **test**; the import-closure test proves ``tos.capsule`` is **absent** from the
cur runtime closure.

Regime tag: completeness predicate substrate only; CUR-EV-001 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.cur as cur
from tos.capsule.context_generation import generation_can_authorize
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    DimensionKey,
    dimension_positively_established,
    vector_complete,
)

from ._cur_strategies import (
    clean_dimension,
    clean_policy,
    clean_revision,
    clean_vector,
)


def test_capsule_owns_the_context_generation_leaf() -> None:
    """(§3.5 capsule context_generation.py:16) capsule owns generation_can_authorize — the CONTEXT leaf.

    The capsule leaf authorizes new risk only when the subject context generation is known and not
    older than the latest restrictive generation (monotonic non-revival). cur consumes this verdict
    as the CONTEXT dimension coordinate; it does not re-author the leaf.
    """
    assert (
        generation_can_authorize(5, 5) is True
    )  # not older than the restrictive floor
    assert generation_can_authorize(4, 5) is False  # stale context generation
    assert generation_can_authorize(None, 5) is False  # unknown ⇒ fail-closed


def test_cur_reauthors_no_capsule_leaf() -> None:
    """(§0.4b) cur re-authors NO capsule egress_currentness_ok / generation_can_authorize leaf."""
    assert not hasattr(cur, "egress_currentness_ok")
    assert not hasattr(cur, "generation_can_authorize")


def test_context_is_a_distinct_mandated_dimension() -> None:
    """(v1.1 MAJOR-2) CONTEXT (capsule-owned) is a SEPARATE mandated dimension from CRITICAL_INPUT."""
    assert DimensionKey.CONTEXT in MANDATED_DIMENSION_FLOOR
    assert DimensionKey.CRITICAL_INPUT in MANDATED_DIMENSION_FLOOR
    assert DimensionKey.CONTEXT is not DimensionKey.CRITICAL_INPUT


def test_cur_consumes_the_capsule_context_verdict_as_one_dimension() -> None:
    """(§0.4b) The capsule Context leaf verdict is injected as the CONTEXT CurrentnessDimension coordinate."""
    capsule_verdict = generation_can_authorize(
        5, 5
    )  # the injected per-decision leaf result
    rev = clean_revision()
    context_dim = clean_dimension(
        dimension_key=DimensionKey.CONTEXT,
        revision=rev,
        positively_established=capsule_verdict,
    )
    assert dimension_positively_established(context_dim) is True


def test_absent_context_dimension_makes_vector_incomplete() -> None:
    """(§0.4b / v1.1 MAJOR-2) A vector missing the CONTEXT dimension is incomplete — leaf-undetectable.

    This is the exact fail-open the CONTEXT enum member seals: without CONTEXT in the mandated floor,
    a CONTEXT-absent vector would vacuously pass. It must be denied.
    """
    rev = clean_revision()
    without_context = tuple(
        clean_dimension(dimension_key=key, revision=rev)
        for key in sorted(MANDATED_DIMENSION_FLOOR)
        if key is not DimensionKey.CONTEXT
    )
    vec = clean_vector(revision=rev, dimensions=without_context)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
