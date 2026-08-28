"""CII-EV-004 transformation-lineage reproducibility -> INVALID (design §2.3).

A derived input that is non-reproducible, or has a missing exact parent, or is a
stochastic transform lacking both a seed and a nondeterminism declaration, is
``INVALID`` for new risk (ADR §10 line 285, 288).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule.field_state import FieldState
from tos.capsule.lineage import ParentRef, Stochastic, TransformationLineage
from tos.capsule.predicates import derive_lineage_state

from ._strategies import lineages


@given(lineage=lineages())
def test_non_reproducible_is_invalid(lineage: TransformationLineage) -> None:
    """A non-reproducible lineage is INVALID regardless of anything else."""
    if not lineage.reproducible:
        assert derive_lineage_state(lineage) == FieldState.INVALID


@given(reproducible=st.booleans())
def test_missing_parent_is_invalid(reproducible: bool) -> None:
    """A missing/empty exact parent forces INVALID even when reproducible."""
    empty = TransformationLineage(reproducible=reproducible, parents=())
    assert derive_lineage_state(empty) == FieldState.INVALID
    incomplete = TransformationLineage(
        reproducible=reproducible, parents=(ParentRef(parent_id="p", digest=None),)
    )
    assert derive_lineage_state(incomplete) == FieldState.INVALID


def test_stochastic_without_seed_is_invalid() -> None:
    """A stochastic transform without seed/nondeterminism declaration is INVALID."""
    lineage = TransformationLineage(
        reproducible=True,
        parents=(ParentRef(parent_id="p", digest="d"),),
        stochastic=Stochastic(is_stochastic=True),
    )
    assert derive_lineage_state(lineage) == FieldState.INVALID


def test_reproducible_with_complete_parents_is_valid() -> None:
    """A reproducible lineage with complete parents and a seed is VALID."""
    lineage = TransformationLineage(
        reproducible=True,
        parents=(ParentRef(parent_id="p", digest="d"),),
        stochastic=Stochastic(is_stochastic=True, random_seed="42"),
    )
    assert derive_lineage_state(lineage) == FieldState.VALID
