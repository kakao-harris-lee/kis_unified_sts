"""Shared valid-artifact builders + strategies for the Orthogonal Trading State tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #8 §0.3). The ``issue_*``
/ ``*_required_kwargs`` builders populate every safety-load-bearing covered field each
record's issuance guard demands, so a "valid" fixture is genuinely valid (never the
all-null coverage illusion). The five §14 named fixtures (design #8 §7; ADR-002-005 §14
line 207-211 verbatim) are exported as module constants; ``clean_side`` is the positive
(all-proof) side-condition, ``fail_closed_side`` the all-``None`` default. The reserved
``"TBD"`` placeholder is excluded from required-field text (a past flaky-test lesson).
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    CouplingSideConditions,
    DimensionTransitionRecord,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``
#: placeholder the issuance guard rejects — design #8 §2.2/§3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

# ---------------------------------------------------------------------------
# Per-dimension enum strategies
# ---------------------------------------------------------------------------

INTENT_STATES = st.sampled_from(list(IntentState))
ATTEMPT_STATES = st.sampled_from(list(TransmissionAttemptState))
BROKER_STATES = st.sampled_from(list(BrokerOrderState))
KNOWLEDGE_STATES = st.sampled_from(list(KnowledgeState))
CAPACITY_STATES = st.sampled_from(list(CapacityState))


# ---------------------------------------------------------------------------
# CompositeState builders
# ---------------------------------------------------------------------------


def composite_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Composite issuance kwargs with every required covered field concrete (14_1 shape)."""
    base: dict[str, Any] = {
        "composite_state_id": "cs-1",
        "intent_identity": "intent-1",
        "intent_state": IntentState.APPROVED,
        "transmission_attempt_state": TransmissionAttemptState.CAPABILITY_ISSUED,
        "broker_order_state": BrokerOrderState.NONE_OBSERVED,
        "knowledge_state": KnowledgeState.CONSISTENT,
        "capacity_state": CapacityState.ATTEMPT_BOUND,
    }
    base.update(overrides)
    return base


def issue_composite(**overrides: Any) -> CompositeState:
    """Issue a valid :class:`CompositeState`."""
    return CompositeState.issue(scheme=SCHEME, **composite_required_kwargs(**overrides))


@st.composite
def composites(draw: st.DrawFn) -> CompositeState:
    """A hypothesis strategy over arbitrary constructible composite observations."""
    return issue_composite(
        intent_state=draw(INTENT_STATES),
        transmission_attempt_state=draw(ATTEMPT_STATES),
        broker_order_state=draw(BROKER_STATES),
        knowledge_state=draw(KNOWLEDGE_STATES),
        capacity_state=draw(CAPACITY_STATES),
    )


# ---------------------------------------------------------------------------
# DimensionTransitionRecord builders
# ---------------------------------------------------------------------------


def transition_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Transition-record issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "transition_id": "tr-1",
        "intent_identity": "intent-1",
        "dimension": StateDimension.BROKER_ORDER,
        "from_state": BrokerOrderState.WORKING.value,
        "to_state": BrokerOrderState.PARTIALLY_FILLED.value,
        "owning_authority": TransitionAuthority.BROKER_ADAPTER_EVIDENCE,
    }
    base.update(overrides)
    return base


def issue_transition_record(**overrides: Any) -> DimensionTransitionRecord:
    """Issue a valid :class:`DimensionTransitionRecord`."""
    return DimensionTransitionRecord.issue(
        scheme=SCHEME, **transition_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Injected coupling side-conditions
# ---------------------------------------------------------------------------


def clean_side(**overrides: Any) -> CouplingSideConditions:
    """A positive side: every proof / epoch present, no trapped exposure (guard True side)."""
    base: dict[str, Any] = {
        "final_quantity_proof": True,
        "consistent_release_proof_rule": True,
        "authority_epoch_current": True,
        "non_reducible_exposure": False,
    }
    base.update(overrides)
    return CouplingSideConditions(**base)


def fail_closed_side() -> CouplingSideConditions:
    """The all-``None`` side (every side-condition unproven — fail-closed default)."""
    return CouplingSideConditions()


# ---------------------------------------------------------------------------
# The five §14 named composite fixtures (ADR-002-005 §14 line 207-211 verbatim)
# ---------------------------------------------------------------------------

#: §14 row 1 — coupling-clean positive (design #8 §7).
COMPOSITE_14_1_CAPABILITY_ISSUED: CompositeState = issue_composite(
    composite_state_id="cs-14-1",
    intent_state=IntentState.APPROVED,
    transmission_attempt_state=TransmissionAttemptState.CAPABILITY_ISSUED,
    broker_order_state=BrokerOrderState.NONE_OBSERVED,
    knowledge_state=KnowledgeState.CONSISTENT,
    capacity_state=CapacityState.ATTEMPT_BOUND,
)

#: §14 row 2 — representable BUT coupling-negative (Broker=UNKNOWN fires CPL-5).
COMPOSITE_14_2_SENT_UNKNOWN: CompositeState = issue_composite(
    composite_state_id="cs-14-2",
    intent_state=IntentState.ACTIVE,
    transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
    broker_order_state=BrokerOrderState.UNKNOWN,
    knowledge_state=KnowledgeState.CONFLICTED,
    capacity_state=CapacityState.POTENTIALLY_LIVE,
)

#: §14 row 3 — coupling-clean positive (design #8 §7).
COMPOSITE_14_3_PARTIAL_FILL: CompositeState = issue_composite(
    composite_state_id="cs-14-3",
    intent_state=IntentState.ACTIVE,
    transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
    broker_order_state=BrokerOrderState.PARTIALLY_FILLED,
    knowledge_state=KnowledgeState.CONSISTENT,
    capacity_state=CapacityState.PARTIALLY_CONSUMED,
)

#: §14 row 4 — representable BUT coupling-negative (Knowledge=CONFLICTED fires CPL-5).
COMPOSITE_14_4_SUPERSEDED_CANCEL: CompositeState = issue_composite(
    composite_state_id="cs-14-4",
    intent_state=IntentState.ACTIVE,
    transmission_attempt_state=TransmissionAttemptState.SUPERSEDED,
    broker_order_state=BrokerOrderState.CANCEL_PENDING,
    knowledge_state=KnowledgeState.CONFLICTED,
    capacity_state=CapacityState.RELEASE_PENDING_PROOF,
)

#: §14 row 5 — coupling-clean positive (design #8 §7).
COMPOSITE_14_5_FILLED_RECONCILED: CompositeState = issue_composite(
    composite_state_id="cs-14-5",
    intent_state=IntentState.ACTIVE,
    transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
    broker_order_state=BrokerOrderState.FILLED,
    knowledge_state=KnowledgeState.RECONCILED,
    capacity_state=CapacityState.POSITION_CONSUMED,
)

#: The three coupling-clean positive §14 fixtures (design #8 §7 — clean under clean_side).
CLEAN_POSITIVE_FIXTURES: tuple[CompositeState, ...] = (
    COMPOSITE_14_1_CAPABILITY_ISSUED,
    COMPOSITE_14_3_PARTIAL_FILL,
    COMPOSITE_14_5_FILLED_RECONCILED,
)

#: The two coupling-negative §14 fixtures (design #8 §7 — coupling_violations ⊇ {CPL-5}).
COUPLING_NEGATIVE_FIXTURES: tuple[CompositeState, ...] = (
    COMPOSITE_14_2_SENT_UNKNOWN,
    COMPOSITE_14_4_SUPERSEDED_CANCEL,
)

#: All five §14 fixtures (all constructible — STATE-EV-001 representability slice).
ALL_14_FIXTURES: tuple[CompositeState, ...] = (
    COMPOSITE_14_1_CAPABILITY_ISSUED,
    COMPOSITE_14_2_SENT_UNKNOWN,
    COMPOSITE_14_3_PARTIAL_FILL,
    COMPOSITE_14_4_SUPERSEDED_CANCEL,
    COMPOSITE_14_5_FILLED_RECONCILED,
)
