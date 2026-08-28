"""Seam: ``tos.posttrade`` <-> ``tos.orthostate`` — the obligation axis is the sixth one.

ADR-002-030 §10 line 305 keeps the obligation-lifecycle axis "orthogonal to ADR-002-006
Knowledge/Evidence State", and §10 line 303-310 lists the five orthostate-owned axes it must
not be fused with. So the obligation lifecycle is a **sixth** coordinate beside orthostate's
five, and the five arrive on
:class:`~tos.posttrade.EconomicObligationRecord` as five **separate injected fields** carrying
opaque sibling tokens this package consumes and never sets.

**Token overlap, type separation (design #24 §2.2-6).** ``CLOSED`` exists on orthostate's
intent axis and on our obligation axis; ``RECONCILED`` exists on orthostate's knowledge axis
and (differently again) on nontrade's event axis. The words coincide because the ADR uses them
on several axes; the types never do, because this package imports none of them.

Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import tos.posttrade.predicates as posttrade_predicates
import tos.posttrade.vocabulary as posttrade_vocabulary
from tos.posttrade import (
    ORTHOGONAL_POST_TRADE_AXES,
    EconomicObligationRecord,
    PostTradeObligationLifecycleState,
    obligation_axes_not_collapsed,
)

from ._posttrade_strategies import clean_obligation_record


def test_closed_is_a_different_type_on_the_two_axes() -> None:
    """(§2.2-6) orthostate ``IntentState.CLOSED`` is not our obligation ``CLOSED``."""
    from tos.orthostate import IntentState

    ours = PostTradeObligationLifecycleState.CLOSED
    theirs = IntentState.CLOSED
    assert ours.value == theirs.value
    assert type(ours) is not type(theirs)
    assert ours is not theirs


def test_finality_proven_is_not_knowledge_reconciled() -> None:
    """(§2.2-6 / §10 line 305) Two different claims about two different things.

    ``FINALITY_PROVEN`` says an exact obligation leg's declared finality class is proven.
    ``KnowledgeState.RECONCILED`` says the local knowledge of a broker state has been
    reconciled. Neither implies the other, and no token even coincides.
    """
    from tos.orthostate import KnowledgeState

    assert hasattr(KnowledgeState, "RECONCILED")
    assert not hasattr(PostTradeObligationLifecycleState, "RECONCILED")
    assert not hasattr(KnowledgeState, "FINALITY_PROVEN")


def test_the_five_orthostate_axes_are_five_separate_injected_fields() -> None:
    """(§10 line 303-310) No fusion — each axis keeps its own field."""
    record = clean_obligation_record()
    assert obligation_axes_not_collapsed(record) is True
    for axis in ORTHOGONAL_POST_TRADE_AXES:
        assert axis in EconomicObligationRecord.model_fields
        assert EconomicObligationRecord.model_fields[axis].annotation == (str | None)


def test_the_axis_tokens_are_recognizable_orthostate_members() -> None:
    """(seam) The opaque strings this package carries really are orthostate's vocabulary."""
    from tos.orthostate import BrokerOrderState, KnowledgeState

    record = clean_obligation_record(
        order_state=BrokerOrderState.FILLED.value,
        knowledge_state=KnowledgeState.RECONCILED.value,
    )
    assert record.order_state in {member.value for member in BrokerOrderState}
    assert record.knowledge_state in {member.value for member in KnowledgeState}


def test_this_package_re_authors_none_of_the_five_axes() -> None:
    """(§3.5) orthostate owns the order / knowledge / capacity / authority / evidence axes."""
    for forbidden in (
        "KnowledgeState",
        "IntentState",
        "BrokerOrderState",
        "TransmissionState",
    ):
        assert not hasattr(posttrade_vocabulary, forbidden)
    for forbidden in ("no_coupling_violation", "reconstruct_conservative"):
        assert not hasattr(posttrade_predicates, forbidden)


def test_the_sixth_axis_is_ours_and_only_ours() -> None:
    """(§10 line 305) The obligation lifecycle exists on neither of the five."""
    from tos.orthostate import BrokerOrderState, IntentState, KnowledgeState

    ours = {member.value for member in PostTradeObligationLifecycleState}
    for sibling_enum in (IntentState, KnowledgeState, BrokerOrderState):
        theirs = {member.value for member in sibling_enum}
        # an overlap in wording is expected and harmless; a *containment* would mean the
        # axis had been duplicated rather than kept separate
        assert not ours <= theirs
        assert not theirs <= ours
