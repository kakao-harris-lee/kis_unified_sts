"""Seam: ``tos.posttrade`` <-> ``tos.nontrade`` — the mutual deferral, the largest boundary.

**The two ADRs defer to each other explicitly (design #24 §3.5 verdict 1).** ADR-002-010 §16
line 309: "This ADR owns the **non-trade event and transformation identity**; **ADR-002-030
owns the obligation-lifecycle serialization**." ADR-002-030 §17 line 414: "**ADR-002-010 owns
lifecycle and non-trade event identity and transformation. This ADR owns the resulting
obligation legs and their finality.**" Cause and consequence: nontrade owns the event,
posttrade owns the obligation it produces.

**Two naming traps, both asserted here:**

* "**lifecycle**" — nontrade's is the *event workflow* lifecycle
  (``OBSERVED -> ... -> RECONCILED``); ours is the *obligation* lifecycle
  (``POTENTIAL -> ... -> CLOSED``). Different enums, different axes, overlapping words;
* "**leg**" — nontrade's ``CredibleTransitionLegKind`` is a credible economic **state during**
  an event; our :class:`~tos.posttrade.ObligationLeg` is an exact economic **effect with
  finality**.

And the substantive rule, §17 line 418 verbatim: "An ADR-002-010 event state such as
``APPLIED_LOCAL`` or ``RECONCILED`` **does not prove its resulting obligations final**."

Locks **2** of the 19 injected tokens: ``APPLIED_LOCAL``, ``RECONCILED``. Test-only sibling
imports are not runtime package edges.
"""

from __future__ import annotations

import pytest
from tos.posttrade import (
    EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY,
    NONTRADE_EVENT_STATE_APPLIED_LOCAL,
    NONTRADE_EVENT_STATE_RECONCILED,
    EventObligationLegKind,
    FinalityDimensionKind,
    PostTradeObligationLifecycleState,
    event_state_not_obligation_finality,
)

from ._posttrade_strategies import proof_map_only


def test_nontrade_event_state_token_drift_locks() -> None:
    """(tokens 13-14 of 19) The two §17 line 418 event-workflow members."""
    from tos.nontrade import NonTradeEventWorkflowState

    assert (
        NonTradeEventWorkflowState.APPLIED_LOCAL.value
        == NONTRADE_EVENT_STATE_APPLIED_LOCAL
    )
    assert (
        NonTradeEventWorkflowState.RECONCILED.value == NONTRADE_EVENT_STATE_RECONCILED
    )
    assert (
        NonTradeEventWorkflowState.APPLIED_LOCAL.value,
        NonTradeEventWorkflowState.RECONCILED.value,
    ) == EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY


@pytest.mark.parametrize(
    "state",
    [
        "APPLIED_LOCAL",
        "RECONCILED",
        "OBSERVED",
        "CORROBORATING",
        "VALIDATED",
        "TRANSITION_PREPARED",
        "EFFECT_PENDING",
        "RECONCILING",
        "CONFLICTED",
        "QUARANTINED_UNKNOWN",
        "CORRECTION_PENDING",
    ],
)
def test_no_nontrade_workflow_state_proves_an_obligation_final(state: str) -> None:
    """(§17 line 418) Every one of nontrade's eleven states, not just the two named.

    The ADR names ``APPLIED_LOCAL`` and ``RECONCILED`` as examples ("such as"); the rule is
    general, and here it is general **structurally** — the token is never read.
    """
    from tos.nontrade import NonTradeEventWorkflowState

    assert state in {member.value for member in NonTradeEventWorkflowState}
    all_unknown: dict[FinalityDimensionKind, bool | None] = dict.fromkeys(
        FinalityDimensionKind
    )
    assert event_state_not_obligation_finality(state, all_unknown) is False
    # ... and with a real dimension proof, the *proof* is what carries it, not the token
    assert (
        event_state_not_obligation_finality(
            state, proof_map_only(FinalityDimensionKind.CORPORATE_ACTION_FINALITY)
        )
        is True
    )


def test_the_two_lifecycles_are_different_enums_on_different_axes() -> None:
    """(§3.5 verdict 1, trap a) "lifecycle" means two things across the boundary."""
    from tos.nontrade import NonTradeEventWorkflowState

    assert len(list(NonTradeEventWorkflowState)) == 11  # 8 linear + 3 branch
    assert len(list(PostTradeObligationLifecycleState)) == 12  # 8 linear + 4 branch
    assert NonTradeEventWorkflowState is not PostTradeObligationLifecycleState
    # ``RECONCILED`` exists on nontrade's axis and has no counterpart on ours
    assert hasattr(NonTradeEventWorkflowState, "RECONCILED")
    assert not hasattr(PostTradeObligationLifecycleState, "RECONCILED")
    # ``FINALITY_PROVEN`` exists on ours and has no counterpart on theirs
    assert hasattr(PostTradeObligationLifecycleState, "FINALITY_PROVEN")
    assert not hasattr(NonTradeEventWorkflowState, "FINALITY_PROVEN")


def test_the_shared_branch_tokens_are_still_different_types() -> None:
    """(§2.2-6) ``CONFLICTED`` / ``CORRECTION_PENDING`` overlap in wording, never in type."""
    from tos.nontrade import NonTradeEventWorkflowState

    ours = PostTradeObligationLifecycleState.CORRECTION_PENDING
    theirs = NonTradeEventWorkflowState.CORRECTION_PENDING
    assert ours.value == theirs.value
    assert type(ours) is not type(theirs)
    assert ours is not theirs


def test_the_two_leg_axes_are_different_enums() -> None:
    """(§3.5 verdict 1, trap b) "leg" means two things across the boundary.

    nontrade's ten credible-transition legs are economic **states during** an event; our nine
    event-obligation leg kinds are the **effects** the event produces.
    """
    from tos.nontrade import CredibleTransitionLegKind

    assert len(list(CredibleTransitionLegKind)) == 10
    assert len(list(EventObligationLegKind)) == 9
    assert CredibleTransitionLegKind is not EventObligationLegKind
    ours = {member.value for member in EventObligationLegKind}
    theirs = {member.value for member in CredibleTransitionLegKind}
    assert ours.isdisjoint(
        theirs
    ), "the two leg vocabularies must not even share a token — they are different axes"


def test_the_two_event_facing_predicates_are_different_functions() -> None:
    """(§0.4e) nontrade classifies the event; this package judges the obligation."""
    from tos.nontrade import (
        correction_reversal_idempotent,
        transition_envelope_complete,
    )
    from tos.posttrade import obligation_commit_idempotent

    assert correction_reversal_idempotent is not obligation_commit_idempotent
    assert callable(transition_envelope_complete)


def test_this_package_never_re_classifies_a_non_trade_event() -> None:
    """(§3.5 verdict 1) No event class, workflow state, or transformation lives here."""
    import tos.posttrade.predicates as posttrade_predicates
    import tos.posttrade.vocabulary as posttrade_vocabulary

    for forbidden in (
        "NonTradeEventClass",
        "NonTradeEventWorkflowState",
        "CredibleTransitionLegKind",
        "SplitTransformationKind",
        "TransformationDirection",
    ):
        assert not hasattr(posttrade_vocabulary, forbidden)
    for forbidden in (
        "split_polarity_coherent",
        "transition_envelope_complete",
        "correction_reversal_idempotent",
        "classify_event",
    ):
        assert not hasattr(posttrade_predicates, forbidden)
