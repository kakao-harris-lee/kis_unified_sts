"""Reference source independence + common-mode collapse (time design §2.5 A).

EV-L1 predicate substrate only; TIME-EV-003 remains NOT_IMPLEMENTED pending
EV-L2/L3 fault injection.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.time import (
    ReferenceSource,
    independent_reference_count,
    source_disagreement_within_bound,
)


def test_shared_common_mode_group_collapses_to_one() -> None:
    """Sources sharing a common_mode_group count as ONE contribution (§7 184)."""
    sources = [
        ReferenceSource(source_id="s1", common_mode_group="g1"),
        ReferenceSource(source_id="s2", common_mode_group="g1"),
        ReferenceSource(source_id="s3", common_mode_group="g1"),
    ]
    assert independent_reference_count(sources) == 1


def test_distinct_groups_count_separately() -> None:
    """Distinct common-mode groups each contribute one (§7 184)."""
    sources = [
        ReferenceSource(source_id="s1", common_mode_group="g1"),
        ReferenceSource(source_id="s2", common_mode_group="g2"),
    ]
    assert independent_reference_count(sources) == 2


def test_ungrouped_sources_each_independent() -> None:
    """A source with no declared group counts as its own contribution."""
    sources = [
        ReferenceSource(source_id="s1", common_mode_group=None),
        ReferenceSource(source_id="s2", common_mode_group=None),
    ]
    assert independent_reference_count(sources) == 2


@given(
    n_grouped=st.integers(1, 6),
    n_ungrouped=st.integers(0, 4),
)
def test_common_mode_never_over_counts(n_grouped: int, n_ungrouped: int) -> None:
    """Property: a shared group never inflates the independent count (§7 184)."""
    grouped = [
        ReferenceSource(source_id=f"g{i}", common_mode_group="shared")
        for i in range(n_grouped)
    ]
    ungrouped = [
        ReferenceSource(source_id=f"u{i}", common_mode_group=None)
        for i in range(n_ungrouped)
    ]
    # n_grouped shared-group members collapse to exactly 1.
    assert independent_reference_count(grouped + ungrouped) == 1 + n_ungrouped


@given(dis=st.integers(0, 10**6), tol=st.integers(0, 10**6))
def test_disagreement_within_bound(dis: int, tol: int) -> None:
    """Disagreement is within bound iff it does not exceed the injected tolerance (§7 184)."""
    assert source_disagreement_within_bound(dis, tol) is (dis <= tol)


def test_disagreement_unknown_fails_closed() -> None:
    """Unknown disagreement or unestablished tolerance is not within bound."""
    assert source_disagreement_within_bound(None, 100) is False
    assert source_disagreement_within_bound(100, None) is False
