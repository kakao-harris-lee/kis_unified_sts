"""Group reconcile regression — all-entry conservatism, order independence, MAX generation (§4.4).

The #22 MAJOR-1 lesson: when several entries map into one group, the verdict must reconcile **every**
entry conservatively, never the first. SIR's reconcile points are the Active Safety Incident Set
(SIR-INV-004 no favorable subset, §10 line 305-312) and the Incident Generation fence (§5.4 monotonic,
§16 line 427 "absence of a newer declaration ... ordered before the claim/send boundary").

The #26 MAJOR-1 lesson runs the other way: an ∅ guard must not **over-seal** a legitimately empty case.
The §4.4 explicit-empty Active Safety Incident Set (applicable = ∅, members = (), positively complete
and current) is the canonical representation of a no-incident bundle (§5.5 line 126 "applicable to";
§16 line 423-424 requires the exact set digest at every final egress even with no incident), so it is
**valid** — while a malformed ∅ denies. Both ways.

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.sir as s
from hypothesis import given
from hypothesis import strategies as st

from ._sir_strategies import (
    CLEAN_APPLICABLE_INCIDENTS,
    CLEAN_APPLICABLE_SHARED_CAUSES,
    clean_active_set,
    clean_dependency_closure,
    clean_member,
    empty_active_set,
)


def _yolk(
    active_set,
    incidents=CLEAN_APPLICABLE_INCIDENTS,
    causes=CLEAN_APPLICABLE_SHARED_CAUSES,
):
    """Run the exact-scope yolk over the clean closure."""
    return s.scope_exact_combined_no_favorable_subset(
        active_set, clean_dependency_closure(), incidents, causes, frozenset()
    )


# --- order independence -----------------------------------------------------


@given(permutation=st.permutations(range(4)))
def test_four_member_verdict_is_order_independent(permutation: list[int]) -> None:
    """(§4.4) Four members in any order produce the same verdict — no first-entry judgement."""
    members = tuple(
        clean_member(
            incident_id=f"inc-{index}",
            lifecycle_state=s.IncidentLifecycleState.CLOSED,
        )
        for index in range(4)
    )
    applicable = frozenset(f"inc-{index}" for index in range(4))
    baseline = _yolk(clean_active_set(members=members), applicable, frozenset())
    reordered = clean_active_set(members=tuple(members[index] for index in permutation))
    assert _yolk(reordered, applicable, frozenset()) is baseline is True


@given(permutation=st.permutations(range(3)))
def test_one_open_member_dominates_regardless_of_position(
    permutation: list[int],
) -> None:
    """(§4.4 all-entry conservatism) A single still-open member dominates from any position."""
    members = (
        clean_member(
            incident_id="inc-0", lifecycle_state=s.IncidentLifecycleState.CLOSED
        ),
        clean_member(
            incident_id="inc-1", lifecycle_state=s.IncidentLifecycleState.CONTAINING
        ),
        clean_member(
            incident_id="inc-2", lifecycle_state=s.IncidentLifecycleState.CLOSED
        ),
    )
    reordered = clean_active_set(
        members=tuple(members[index] for index in permutation),
        shared_dependencies=(),
    )
    assert s.dominating_open_incident_present(reordered) is True


@given(permutation=st.permutations(range(3)))
def test_one_unresolved_shared_cause_dominates_regardless_of_position(
    permutation: list[int],
) -> None:
    """(SIR-INV-004) A single unresolved shared cause denies from any position in the tuple."""
    members = (
        clean_member(
            incident_id="inc-0",
            lifecycle_state=s.IncidentLifecycleState.CLOSED,
            shared_cause_ids=frozenset({"dep-shared"}),
            resolved=True,
        ),
        clean_member(
            incident_id="inc-1",
            lifecycle_state=s.IncidentLifecycleState.CLOSED,
            shared_cause_ids=frozenset({"dep-shared"}),
            resolved=None,  # unknown ⇒ unresolved
        ),
        clean_member(
            incident_id="inc-2",
            lifecycle_state=s.IncidentLifecycleState.CLOSED,
            shared_cause_ids=frozenset(),
            resolved=True,
        ),
    )
    reordered = clean_active_set(
        members=tuple(members[index] for index in permutation),
        shared_dependencies=("dep-shared",),
    )
    assert s.no_favorable_subset(reordered, frozenset({"dep-shared"})) is False


# --- MAX generation, never the first ---------------------------------------


def test_group_generation_reconciles_to_the_newest() -> None:
    """(§4.4 / §5.4 / §16 line 427) A group's reconciled fence is the newest generation, not the first."""
    assert s.max_incident_generation((3, 9, 5)) == 9
    assert s.max_incident_generation((9, 3, 5)) == 9  # order-independent
    assert s.max_incident_generation((5,)) == 5


def test_group_generation_is_unprovable_when_any_entry_is_unknown() -> None:
    """(§16 line 429) A single unknown generation makes the group's newest fence unprovable ⇒ ``None``."""
    assert s.max_incident_generation((3, None, 9)) is None
    assert s.max_incident_generation(()) is None


@given(values=st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=6))
def test_max_generation_is_order_independent(values: list[int]) -> None:
    """(§4.4) The reconciled newest generation does not depend on entry order."""
    assert s.max_incident_generation(tuple(values)) == s.max_incident_generation(
        tuple(reversed(values))
    )
    assert s.max_incident_generation(tuple(values)) == max(values)


def test_generation_advance_is_strict_and_fail_closed() -> None:
    """(§5.4 monotonic) Only a provable strict advance holds; equal / regressing / unknown fails."""
    assert s.incident_generation_advances(1, 2) is True
    assert s.incident_generation_advances(2, 2) is False
    assert s.incident_generation_advances(2, 1) is False
    assert s.incident_generation_advances(None, 2) is False
    assert s.incident_generation_advances(1, None) is False


def test_restriction_dominates_send_uses_the_ordering_reuse() -> None:
    """(§16 line 427) A provably earlier restriction dominates the send boundary."""
    assert s.restriction_dominates_send(1, 2) is True
    assert s.restriction_dominates_send(2, 1) is False
    assert s.restriction_dominates_send(None, 2) is False


# --- ∅ both ways ------------------------------------------------------------


def test_explicit_empty_set_is_valid_and_clears() -> None:
    """(§4.4 / #26 MAJOR-1) The canonical no-incident ∅ is valid and carries no dominating incident."""
    empty = empty_active_set()
    assert _yolk(empty, frozenset(), frozenset()) is True
    assert s.dominating_open_incident_present(empty) is False
    assert s.no_favorable_subset(empty, frozenset()) is True


def test_empty_with_applicable_denies_both_directions() -> None:
    """(§4.4 both-ways) ∅ members with applicable incidents, and members with an ∅ applicable set."""
    assert _yolk(empty_active_set()) is False
    assert _yolk(clean_active_set(), frozenset(), frozenset()) is False


def test_absent_set_is_conservative_not_vacuous() -> None:
    """(§4.4) An absent set denies the scope yolk and asserts a dominating incident — never a clear."""
    assert _yolk(None) is False
    assert s.dominating_open_incident_present(None) is True
    assert s.no_favorable_subset(None, frozenset()) is False
    assert s.active_set_is_canonical_union(None, frozenset()) is False
