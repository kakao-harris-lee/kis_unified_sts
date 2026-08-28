"""CII-EV-005 / -006 snapshot validity + freshness + common mode + §6.2 re-wrap.

* CII-EV-005: conservative aggregation (design §5.1) — "individually fresh !=
  valid snapshot"; injected freshness bounds; UNKNOWN is never upgraded.
* CII-EV-006 (core): common-mode collapse (design §5.2).
* MAJOR-3: the four §5.1 conjuncts, empty-blocking fail-closed, injected
  required-corroboration gate; MINOR-4: cut-incoherence floor is CONFLICTED.
* §6.2: Validity-Window as-of anchor -> re-wrap invariance.
* CII-EV-009: predicate-only egress currentness (design §7).
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule.capsule import CapsuleValidity
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.field_evaluation import FieldEvaluation
from tos.capsule.field_state import FieldState
from tos.capsule.observation import Observation, ObservationTime
from tos.capsule.predicates import (
    aggregate_snapshot_validity,
    capsule_observation_stale,
    cut_compatible,
    effective_independent_path_count,
    egress_currentness_ok,
    freshness_state,
    has_unresolved_common_mode,
    observation_validity_stale,
)

from ._strategies import (
    COMPATIBLE_CUT,
    corroboration_path,
    issue_capsule,
    issue_snapshot,
)

# ---- freshness (injected bound) --------------------------------------------


@given(
    age=st.integers(min_value=0, max_value=10**9),
    bound=st.integers(min_value=0, max_value=10**9),
)
def test_freshness_state_against_injected_bound(age: int, bound: int) -> None:
    """VALID within the injected bound, STALE beyond it (design §5.1, §8)."""
    state = freshness_state(age, bound)
    assert state == (FieldState.VALID if age <= bound else FieldState.STALE)


@given(
    present=st.integers(0, 10**6),
    absent=st.none() | st.integers(0, 10**6),
)
def test_missing_window_is_unknown(present: int, absent: int | None) -> None:
    """A missing age OR bound fails closed to UNKNOWN; both present is decided (MINOR-2)."""
    # Missing-age branch (age None, bound present) -> UNKNOWN.
    assert freshness_state(None, present) == FieldState.UNKNOWN
    # Missing-bound branch (age present, bound None) -> UNKNOWN.
    assert freshness_state(present, None) == FieldState.UNKNOWN
    # Both-present branch -> never UNKNOWN (VALID or STALE, decided by the bound).
    if absent is not None:
        assert freshness_state(present, absent) in (FieldState.VALID, FieldState.STALE)


# ---- CII-EV-005 / MINOR-4: individually fresh != valid snapshot ------------


@given(n=st.integers(min_value=0, max_value=4))
def test_individually_fresh_not_valid_when_cut_incompatible(n: int) -> None:
    """All blocking fields VALID but an incompatible cut => CONFLICTED, not VALID."""
    evaluations = tuple(
        FieldEvaluation(field_ref=f"f{i}", state=FieldState.VALID, blocking=True)
        for i in range(n)
    )
    incompatible_cut = ConsistencyCut(
        cut_id="cut-x", atomicity_proven=False, uncertainty=FieldState.VALID
    )
    snap = issue_snapshot(
        field_evaluations=evaluations, consistency_cut=incompatible_cut
    )
    assert not cut_compatible(snap)
    result = aggregate_snapshot_validity(snap, required_independent_paths=0)
    assert result != FieldState.VALID
    # MINOR-4: an incoherent (non-atomic) cut floors at CONFLICTED, not UNKNOWN.
    assert result == FieldState.CONFLICTED


@given(
    worst=st.sampled_from([FieldState.STALE, FieldState.CONFLICTED, FieldState.INVALID])
)
def test_blocking_non_valid_propagates(worst: FieldState) -> None:
    """A blocking non-VALID field keeps the snapshot from being VALID (§5.1)."""
    evaluations = (
        FieldEvaluation(field_ref="ok", state=FieldState.VALID, blocking=True),
        FieldEvaluation(field_ref="bad", state=worst, blocking=True),
    )
    snap = issue_snapshot(field_evaluations=evaluations, consistency_cut=COMPATIBLE_CUT)
    assert (
        aggregate_snapshot_validity(snap, required_independent_paths=0)
        != FieldState.VALID
    )


def test_all_gates_pass_is_valid() -> None:
    """All four §5.1 conjuncts hold => VALID (design §5.1)."""
    evaluations = (
        FieldEvaluation(field_ref="a", state=FieldState.VALID, blocking=True),
        FieldEvaluation(field_ref="b", state=FieldState.VALID, blocking=True),
    )
    paths = (
        corroboration_path("p1", ("origin-a",)),
        corroboration_path("p2", ("origin-b",)),
    )
    snap = issue_snapshot(
        field_evaluations=evaluations,
        consistency_cut=COMPATIBLE_CUT,
        corroboration_paths=paths,
    )
    assert cut_compatible(snap)
    assert not has_unresolved_common_mode(snap)
    assert (
        aggregate_snapshot_validity(snap, required_independent_paths=2)
        == FieldState.VALID
    )


# ---- MAJOR-3: empty-blocking + injected required-corroboration gate ---------


def test_empty_blocking_is_not_valid() -> None:
    """An empty blocking set is not evidence of validity: UNKNOWN, not VALID (MAJOR-3b)."""
    snap = issue_snapshot(
        field_evaluations=(),
        consistency_cut=COMPATIBLE_CUT,
        corroboration_paths=(corroboration_path("p1", ("origin-a",)),),
    )
    assert cut_compatible(snap)
    assert (
        aggregate_snapshot_validity(snap, required_independent_paths=1)
        == FieldState.UNKNOWN
    )


@given(required=st.integers(min_value=1, max_value=3))
def test_zero_corroboration_blocks_valid(required: int) -> None:
    """With required>0 and zero corroboration paths, the result is not VALID (MAJOR-3a)."""
    evaluations = (
        FieldEvaluation(field_ref="a", state=FieldState.VALID, blocking=True),
    )
    snap = issue_snapshot(
        field_evaluations=evaluations,
        consistency_cut=COMPATIBLE_CUT,
        corroboration_paths=(),
    )
    # required=0 (intrinsic) is VALID; injecting a positive requirement blocks it.
    assert (
        aggregate_snapshot_validity(snap, required_independent_paths=0)
        == FieldState.VALID
    )
    assert (
        aggregate_snapshot_validity(snap, required_independent_paths=required)
        != FieldState.VALID
    )


# ---- CII-EV-006 (core): common-mode collapse -------------------------------


def test_shared_tag_collapses_independence() -> None:
    """Two paths sharing a tag count as one independent path (design §5.2)."""
    shared = (corroboration_path("p1", ("libX",)), corroboration_path("p2", ("libX",)))
    assert effective_independent_path_count(shared) == 1
    distinct = (
        corroboration_path("p1", ("libX",)),
        corroboration_path("p2", ("libY",)),
    )
    assert effective_independent_path_count(distinct) == 2


def test_undetermined_scope_treated_as_shared() -> None:
    """An empty-tag (undetermined) path collapses with all others (conservative)."""
    paths = (
        corroboration_path("p1", ()),
        corroboration_path("p2", ("libY",)),
        corroboration_path("p3", ("libZ",)),
    )
    assert effective_independent_path_count(paths) == 1


@given(tag=st.text(min_size=1, max_size=4))
def test_unresolved_common_mode_gate(tag: str) -> None:
    """Two same-tag paths trip the unresolved-common-mode gate (design §5.2)."""
    paths = (corroboration_path("p1", (tag,)), corroboration_path("p2", (tag,)))
    snap = issue_snapshot(corroboration_paths=paths)
    assert has_unresolved_common_mode(snap)


# ---- §6.2: Validity Window as-of anchor / re-wrap invariance ---------------


@given(
    as_of=st.integers(0, 10**6),
    now=st.integers(0, 2 * 10**6),
    window=st.integers(0, 10**6),
    wrap1=st.integers(0, 10**6),
    wrap2=st.integers(0, 10**6),
)
def test_rewrap_does_not_reset_currentness(
    as_of: int, now: int, window: int, wrap1: int, wrap2: int
) -> None:
    """Re-wrapping the same observation in a later capsule keeps staleness (§6.2)."""
    obs = Observation(time=ObservationTime(source_event_time=as_of))
    c1 = issue_capsule(validity=CapsuleValidity(issued_at=wrap1))
    c2 = issue_capsule(validity=CapsuleValidity(issued_at=wrap2))
    stale1 = capsule_observation_stale(c1, obs, now, window)
    stale2 = capsule_observation_stale(c2, obs, now, window)
    assert stale1 == stale2
    # and both equal the as-of-anchored staleness, independent of wrap time
    assert stale1 == observation_validity_stale(as_of, now, window)


def test_missing_window_is_stale_fail_closed() -> None:
    """A missing window/anchor is stale (fail-closed, §6.2 line 197)."""
    assert observation_validity_stale(None, 100, 10) is True
    assert observation_validity_stale(100, 100, None) is True


# ---- CII-EV-009 predicate-only ---------------------------------------------


def test_egress_currentness_fail_closed() -> None:
    """Egress currentness is fail-closed on a missing window (design §7)."""
    assert egress_currentness_ok(None, 100, 10) is False
    assert egress_currentness_ok(90, 100, 20) is True
    assert egress_currentness_ok(50, 100, 20) is False
