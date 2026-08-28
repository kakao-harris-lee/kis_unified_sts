"""MANDATED test-only seam cross-check: nontrade <-> orthostate / ADR-002-005 (§3.4(d)).

ADR-002-010 §6 line 123 requires the non-trade event state to "remain orthogonal to order,
exposure, capacity, authority, and evidence-confidence state". The order / transmission /
knowledge / capacity axes and their coupling law are **orthostate's** (ADR-002-005), so the
nontrade workflow axis is a *separate* coordinate system that consumes those as injected
tokens and never collapses them (design #21 §2.2-5).

**Honest disclosure (§3.4(b)).** This is a **coordinate-dependent** seam, not a
produced-bool one: orthostate exposes no nontrade-specific bool, so what is locked here is
coordinate non-collapse and polarity, not a dedicated verdict. The design records the same
deferral for #13 are-orthostate and #18 replacement-orthostate.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.nontrade import (
    ORTHOGONAL_EVENT_AXES,
    CorrectionReversalOutcome,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventWorkflowState,
    event_axes_not_collapsed,
)
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    no_coupling_violation,
    reconstruct_conservative,
)
from tos.rcl import CapacityState

from ._nontrade_strategies import issue_event


def _composite(
    *,
    knowledge: KnowledgeState = KnowledgeState.CONSISTENT,
    broker: BrokerOrderState = BrokerOrderState.WORKING,
    capacity: CapacityState = CapacityState.ATTEMPT_BOUND,
) -> CompositeState:
    """One orthostate composite observation across the five dimensions."""
    return CompositeState(
        composite_state_id="cs-1",
        intent_identity="intent-1",
        intent_state=IntentState.AUTHORIZED_FOR_CAPACITY,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=broker,
        knowledge_state=knowledge,
        capacity_state=capacity,
        state_model_version="sm-v1",
    )


# ---------------------------------------------------------------------------
# Coordinate non-collapse (§2.2-5 / §6 line 123)
# ---------------------------------------------------------------------------


def test_the_nontrade_workflow_axis_is_a_distinct_type_from_every_orthostate_axis() -> (
    None
):
    """(§2.2-5) Token overlap never becomes type overlap."""
    assert NonTradeEventWorkflowState.CONFLICTED is not KnowledgeState.CONFLICTED
    assert (
        NonTradeEventWorkflowState.QUARANTINED_UNKNOWN
        is not CapacityState.QUARANTINED_UNKNOWN
    )
    for other in (
        set(KnowledgeState),
        set(BrokerOrderState),
        set(TransmissionAttemptState),
        set(IntentState),
    ):
        assert set(NonTradeDisposition).isdisjoint(other)
        assert set(CorrectionReversalOutcome).isdisjoint(other)
        assert set(CredibleTransitionLegKind).isdisjoint(other)


def test_the_five_axes_stay_five_separate_fields_on_the_event_record() -> None:
    """(§6 line 123) The event record mirrors the no-collapse discipline structurally."""
    event = issue_event(
        order_state=BrokerOrderState.UNKNOWN.value,
        capacity_state=CapacityState.TRAPPED_CONSUMED.value,
    )
    assert event_axes_not_collapsed(event) is True
    assert len(ORTHOGONAL_EVENT_AXES) == 5
    # a composite carrying the same tokens keeps them apart on orthostate's side too
    composite = _composite(
        broker=BrokerOrderState.UNKNOWN, capacity=CapacityState.TRAPPED_CONSUMED
    )
    assert composite.broker_order_state is BrokerOrderState.UNKNOWN
    assert composite.capacity_state is CapacityState.TRAPPED_CONSUMED
    assert composite.broker_order_state.value == event.order_state
    assert composite.capacity_state.value == event.capacity_state


# ---------------------------------------------------------------------------
# Consumed propositions (necessary, not sufficient)
# ---------------------------------------------------------------------------


def test_the_coupling_check_is_a_detection_not_a_certification() -> None:
    """(orthostate ``predicates.py:206``) "No violation **detected**", never "fully legal".

    nontrade consumes that verdict as a coordinate; it is *necessary*, not sufficient, and
    nothing in the nontrade disposition treats it as a permission.
    """
    assert no_coupling_violation(_composite()) in (True, False)
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "no_coupling_violation",
        "coupling_violations",
        "reconstruct_conservative",
        "KnowledgeState",
        "BrokerOrderState",
        "CompositeState",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is orthostate-owned — §6 line 123 keeps the axes separate, "
            "which means separate owners, not a local copy"
        )


def test_a_restart_downgrades_positive_knowledge_and_nontrade_never_re_derives_it() -> (
    None
):
    """(ADR-002-005 §13 line 195-200) ``RECONCILED`` does not survive a restart.

    ADR-002-010 §6 line 143 makes the nontrade ``RECONCILED`` label equally non-probative:
    it "requires evidence sufficient under ADR-002-006". Both packages therefore refuse to
    carry positive knowledge across a discontinuity — orthostate by projection, nontrade by
    the all-false authority effect on **every** state.
    """
    reconstructed = reconstruct_conservative(
        _composite(knowledge=KnowledgeState.RECONCILED)
    )
    assert reconstructed.knowledge_state is KnowledgeState.CONFLICTED
    # nontrade's own RECONCILED label is a coordinate, not a proof: it grants nothing
    event = issue_event(workflow_state=NonTradeEventWorkflowState.RECONCILED)
    assert event.workflow_state is NonTradeEventWorkflowState.RECONCILED
    assert all(
        getattr(event.authority_effect, name) is False
        for name in type(event.authority_effect).model_fields
    )


def test_applied_local_is_not_a_broker_state_claim() -> None:
    """(§6 line 142) ``APPLIED_LOCAL`` says nothing about the broker or venue.

    The broker-side truth lives on orthostate's ``BrokerOrderState`` axis, which the event
    record carries as a **separate** injected token — so a local application and an unknown
    broker order coexist rather than one implying the other.
    """
    event = issue_event(
        workflow_state=NonTradeEventWorkflowState.APPLIED_LOCAL,
        order_state=BrokerOrderState.UNKNOWN.value,
    )
    assert event.workflow_state is NonTradeEventWorkflowState.APPLIED_LOCAL
    assert event.order_state == BrokerOrderState.UNKNOWN.value
    assert event_axes_not_collapsed(event) is True
