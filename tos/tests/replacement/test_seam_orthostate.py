"""MANDATED test-only seam cross-check: replacement <-> orthostate (design #18 §3.4(d)).

``tos.replacement`` does **not** import ``tos.orthostate`` at runtime (sibling edge 0).
This file imports **both** as a **test** to lock the injected order / attempt coordinates.

**Honest disclosure (design #18 §3.4(b)).** Unlike protective / afg / brokercap, orthostate
exposes **no dedicated replacement-facing predicate**: the order and transmission-attempt
axes cross the seam as *coordinates*, not as produced bools (the #13 are-orthostate and
#16 afg-orthostate precedent). So this seam locks **token parity and non-collapse**, not a
predicate polarity — anything more would be a phantom.

The two load-bearing facts:

* ADR-002-005 §7 line 103-104: "a later valid fill SHALL be accepted even after a locally
  observed ``CANCELLED``". A ``CANCELLED`` token therefore never terminates the exposure
  by itself, which is exactly why PR-EV-004 stays an ``EV-L3+Broker`` coordinate;
* §5 line 107 forbids collapsing the order / transmission / knowledge / capacity /
  protection axes into one enum. The replacement workflow record keeps **five separate
  fields** and its own lifecycle label as a sixth.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.orthostate import BrokerOrderState, TransmissionAttemptState
from tos.replacement import (
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    ORTHOGONAL_WORKFLOW_AXES,
    ReplacementWorkflowState,
    workflow_record_axes_not_collapsed,
)

from ._replacement_strategies import issue_workflow_record

# ---------------------------------------------------------------------------
# Token drift locks
# ---------------------------------------------------------------------------


def test_broker_order_state_tokens_match_the_real_orthostate_members() -> None:
    """(drift lock) replacement's local coordinate tokens are the live enum values."""
    assert BrokerOrderState.CANCELLED.value == BROKER_ORDER_STATE_CANCELLED
    assert BrokerOrderState.UNKNOWN.value == BROKER_ORDER_STATE_UNKNOWN
    assert len(BrokerOrderState) == 9


def test_attempt_state_token_matches_the_real_orthostate_member() -> None:
    """(drift lock) ``SENT_UNCONFIRMED`` is the potentially-live attempt token (§14)."""
    assert (
        TransmissionAttemptState.SENT_UNCONFIRMED.value
        == ATTEMPT_STATE_SENT_UNCONFIRMED
    )


# ---------------------------------------------------------------------------
# Coordinate non-collapse (§5 line 107 / §2.2-5)
# ---------------------------------------------------------------------------


def test_the_workflow_axis_is_disjoint_from_the_order_and_attempt_axes() -> None:
    """(§2.2-5) A replacement workflow label is never an order or attempt state."""
    workflow = set(ReplacementWorkflowState)
    assert workflow.isdisjoint(set(BrokerOrderState))
    assert workflow.isdisjoint(set(TransmissionAttemptState))
    # The concepts are genuinely distinct: ``COMPLETED`` (workflow) is not ``FILLED``
    # (broker order) and neither is ``ACK_OBSERVED`` (attempt).
    assert ReplacementWorkflowState.COMPLETED is not BrokerOrderState.FILLED
    assert (
        ReplacementWorkflowState.FIRST_LEG_SENT
        is not TransmissionAttemptState.SEND_STARTED
    )


def test_a_workflow_record_carries_the_order_and_attempt_axes_as_separate_fields() -> (
    None
):
    """(§5 line 107) Five orthogonal axes, each its own field, plus the lifecycle label."""
    record = issue_workflow_record(
        workflow_state=ReplacementWorkflowState.INTERMEDIATE_STATE,
        broker_order_state=BrokerOrderState.CANCELLED.value,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED.value,
    )
    assert workflow_record_axes_not_collapsed(record) is True
    # A locally observed CANCELLED order coexisting with an unconfirmed attempt and an
    # INTERMEDIATE_STATE workflow is exactly the state a collapsed enum could not express.
    assert record.broker_order_state == BrokerOrderState.CANCELLED.value
    assert (
        record.transmission_attempt_state
        == TransmissionAttemptState.SENT_UNCONFIRMED.value
    )
    assert record.workflow_state is ReplacementWorkflowState.INTERMEDIATE_STATE
    for axis in ORTHOGONAL_WORKFLOW_AXES:
        assert getattr(record, axis) is not None


def test_a_cancelled_order_state_does_not_move_the_workflow_label() -> None:
    """(§7 line 103-104 / §11 line 273) A cancel ACK ends nothing by itself.

    orthostate records that "a later valid fill SHALL be accepted even after a locally
    observed ``CANCELLED``". replacement therefore never *sets* a workflow state from an
    order state — the two axes move independently, and the package has no setter at all.
    """
    cancelled_but_pending = issue_workflow_record(
        broker_order_state=BrokerOrderState.CANCELLED.value,
        workflow_state=ReplacementWorkflowState.OLD_FINALITY_PENDING,
    )
    assert (
        cancelled_but_pending.workflow_state
        is ReplacementWorkflowState.OLD_FINALITY_PENDING
    ), "a CANCELLED broker order does not advance the workflow to COMPLETED"

    from tos import replacement as replacement_pkg

    for forbidden in (
        "set_broker_order_state",
        "set_attempt_state",
        "attempt_transition_allowed",
        "advance_workflow",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} exists — the order / attempt state machines are orthostate's "
            "(design #18 §0.2), and workflow transition validity is not Phase-1 (Q3)"
        )
