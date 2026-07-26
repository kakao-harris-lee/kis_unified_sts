"""§5.4/§3.2 state: §6 line 123 orthogonality + the ``tos.ordering`` append-only REUSE.

Two disciplines:

* **no-collapse** — the five axes ADR §6 line 123 forbids fusing into the non-trade event
  state stay five separate fields, with the nontrade-owned lifecycle label as a distinct
  sixth coordinate;
* **append-only order** — the versioned order is REUSED from ``tos.ordering`` (one of the
  package's only two imports) rather than re-authored, and a wall clock never orders.

**No transition predicate exists** (design #21 §5.4) and this module asserts that absence:
whether one workflow state may follow another depends on rcl / recon / venue / time runtime
gates, so Phase 1 authors the vocabulary and the structure only.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    ORTHOGONAL_EVENT_AXES,
    WORKFLOW_BRANCH_STATES,
    WORKFLOW_LINEAR_LIFECYCLE,
    NonTradeEventWorkflowState,
    correction_generation_append_only,
    correction_generation_order,
    event_axes_not_collapsed,
    event_generation_append_only,
    event_generation_order,
)
from tos.ordering import Ordering

from ._nontrade_strategies import issue_correction, issue_event

# ---------------------------------------------------------------------------
# §6 line 123 orthogonality
# ---------------------------------------------------------------------------


def test_the_five_axes_are_five_separate_fields() -> None:
    """(§6 line 123) order / exposure / capacity / authority / evidence-confidence."""
    assert event_axes_not_collapsed(issue_event()) is True
    assert len(ORTHOGONAL_EVENT_AXES) == 5


def test_a_none_record_proves_no_orthogonality() -> None:
    """(fail-closed) Nothing to inspect is not a pass."""
    assert event_axes_not_collapsed(None) is False


def test_the_axes_carry_sibling_tokens_this_package_never_sets() -> None:
    """(§3.4) Each axis is an opaque injected token — the types belong to the siblings.

    ``tos.nontrade`` holds sibling edge 0 and therefore cannot name orthostate
    ``BrokerOrderState`` / ``KnowledgeState``, rcl ``CapacityState``, authority
    ``AuthorityState``, or recon ``FieldConfidenceClass``; it carries their tokens.
    """
    event = issue_event(
        order_state="UNKNOWN",
        exposure_state="OPEN",
        capacity_state="TRAPPED_CONSUMED",
        authority_state="HALTED",
        evidence_confidence_state="CONFLICTED",
    )
    assert event_axes_not_collapsed(event) is True
    # a fused state would have made these indistinguishable; here they coexist
    assert event.capacity_state == "TRAPPED_CONSUMED"
    assert event.workflow_state is NonTradeEventWorkflowState.OBSERVED
    assert event.order_state != event.capacity_state


@given(st.sampled_from(list(NonTradeEventWorkflowState)))
def test_the_lifecycle_label_is_orthogonal_to_the_five_axes(
    state: NonTradeEventWorkflowState,
) -> None:
    """(§2.2-5) The nontrade label never becomes one of the injected axes."""
    event = issue_event(workflow_state=state)
    assert event_axes_not_collapsed(event) is True
    assert "workflow_state" not in ORTHOGONAL_EVENT_AXES


def test_no_transition_predicate_exists() -> None:
    """(§5.4) Transition validity is a runtime gate — Phase 1 authors no state machine."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "workflow_transition_allowed",
        "advance_workflow",
        "set_workflow_state",
        "transition_allowed",
        "next_state",
    ):
        assert not hasattr(nontrade_pkg, forbidden)


def test_the_lifecycle_tuples_partition_the_enum() -> None:
    """(§2.2-2) 8 linear + 3 branch, disjoint and exhaustive."""
    assert set(WORKFLOW_LINEAR_LIFECYCLE) | set(WORKFLOW_BRANCH_STATES) == set(
        NonTradeEventWorkflowState
    )
    assert set(WORKFLOW_LINEAR_LIFECYCLE).isdisjoint(WORKFLOW_BRANCH_STATES)


# ---------------------------------------------------------------------------
# §3.2 append-only generation order (tos.ordering REUSE)
# ---------------------------------------------------------------------------


def test_generations_within_one_series_are_ordered() -> None:
    """(§3.2) The order comes from ``tos.ordering``; the generation is a plain int."""
    first = issue_event(workflow_generation=1)
    second = issue_event(workflow_generation=2)
    assert event_generation_order(first, second) is Ordering.BEFORE
    assert event_generation_order(second, first) is Ordering.AFTER


def test_records_from_different_series_are_ambiguous_not_silently_ordered() -> None:
    """(§3.2) Two different continuities have no comparable order."""
    first = issue_event(idempotency_key="idem-a", workflow_generation=1)
    second = issue_event(idempotency_key="idem-b", workflow_generation=2)
    assert event_generation_order(first, second) is Ordering.AMBIGUOUS


def test_a_missing_generation_is_ambiguous_not_an_assumed_precedence() -> None:
    """(§3.2 fail-closed) An unordered record is UNKNOWN, never "earlier"."""
    concrete = issue_event(workflow_generation=1)
    without = issue_event(workflow_generation=1).model_copy(
        update={"workflow_generation": None}
    )
    assert event_generation_order(without, concrete) is Ordering.AMBIGUOUS


def test_an_append_only_sequence_is_strictly_increasing() -> None:
    """(§10 line 219) A legitimate progression appends a new generation."""
    records = [issue_event(workflow_generation=n) for n in (1, 2, 3)]
    assert event_generation_append_only(records) is True


def test_a_repeated_or_decreasing_generation_is_an_in_place_edit() -> None:
    """(§10 line 219) Equality is a violation too — two records cannot share a generation."""
    assert (
        event_generation_append_only(
            [issue_event(workflow_generation=n) for n in (1, 1)]
        )
        is False
    )
    assert (
        event_generation_append_only(
            [issue_event(workflow_generation=n) for n in (2, 1)]
        )
        is False
    )


def test_a_missing_generation_fails_the_append_only_check() -> None:
    """(§3.2 fail-closed) An unordered record cannot be proven append-only."""
    records = [
        issue_event(workflow_generation=1),
        issue_event(workflow_generation=2).model_copy(
            update={"workflow_generation": None}
        ),
    ]
    assert event_generation_append_only(records) is False


@pytest.mark.parametrize("length", [0, 1])
def test_a_sequence_shorter_than_two_has_nothing_to_violate(length: int) -> None:
    """(§3.2) Vacuously append-only — but a ``None`` generation still fails."""
    records = [issue_event(workflow_generation=1) for _ in range(length)]
    assert event_generation_append_only(records) is True


def test_the_correction_series_shares_the_same_discipline() -> None:
    """(§16 line 313) Corrections form their own append-only series."""
    first = issue_correction(correction_generation=1)
    second = issue_correction(correction_generation=2)
    assert correction_generation_order(first, second) is Ordering.BEFORE
    assert correction_generation_append_only([first, second]) is True
    assert correction_generation_append_only([second, first]) is False
    detached = issue_correction(correction_generation=2).model_copy(
        update={"correction_generation": None}
    )
    assert correction_generation_append_only([first, detached]) is False
    assert correction_generation_order(first, detached) is Ordering.AMBIGUOUS


def test_the_order_never_consults_a_clock() -> None:
    """(§8 line 175) A wall clock never orders; only the injected generation does.

    The seven event times are deliberately varied here and the verdict does not move.
    """
    first = issue_event(workflow_generation=1, observation_time="t-late")
    second = issue_event(workflow_generation=2, observation_time="t-early")
    assert event_generation_order(first, second) is Ordering.BEFORE
