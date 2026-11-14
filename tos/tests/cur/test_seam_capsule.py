"""MANDATED test-only seam cross-check: capsule Context generation leaf -> cur (design #23 §0.4b/§3.5)."""

from __future__ import annotations

import tos.cur as cur
from tos.capsule.context_generation import generation_can_authorize
from tos.cur import (
    DimensionKey,
    dimension_positively_established,
)

from ._cur_strategies import (
    clean_dimension,
    clean_revision,
)


def test_capsule_owns_the_context_generation_leaf() -> None:
    """(§3.5 capsule context_generation.py:16) capsule owns generation_can_authorize — the CONTEXT leaf."""
    assert generation_can_authorize(5, 5) is True
    assert generation_can_authorize(4, 5) is False
    assert generation_can_authorize(None, 5) is False


def test_cur_reauthors_no_capsule_leaf() -> None:
    """(§0.4b) cur re-authors NO capsule egress_currentness_ok / generation_can_authorize leaf."""
    assert not hasattr(cur, "egress_currentness_ok")
    assert not hasattr(cur, "generation_can_authorize")


def test_cur_consumes_the_capsule_context_verdict_as_one_dimension() -> None:
    """(§0.4b) The capsule Context leaf verdict is injected as the CONTEXT CurrentnessDimension coordinate."""
    capsule_verdict = generation_can_authorize(5, 5)
    rev = clean_revision()
    context_dim = clean_dimension(
        dimension_key=DimensionKey.CONTEXT,
        revision=rev,
        positively_established=capsule_verdict,
    )
    assert dimension_positively_established(context_dim) is True
