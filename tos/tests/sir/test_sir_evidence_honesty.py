"""MANDATED property test — evidence / communication honesty (SIR-EV-009 / SIR-AC-009; design #28 §5.3).

The third yolk. ``evidence_communication_status_honest`` decides whether a communication and its
supporting analysis substitute for neither prevention, finality nor authority (ADR-002-027 §18;
SIR-INV-014). This file is the design #28 §13 mandated property test for that row, plus the §18 line 472
**9-token honesty ladder anchor drift** lock.

Both ways (design #28 §7.2): every conjunct satisfied ⇒ ``True``, each conjunct violated individually ⇒
``False``.

**Closes no SIR-EV.** SIR-EV-009 is ``EV-L1/3`` — the ``/3`` integration and adversarial evidence is
Phase-1-out. Evidence custody, the causal chain and Evidence Gap integrity are evidence-owned
(ADR-002-016) and injected. Regime tag: evidence-honesty predicate substrate only; EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import tos.sir as s
from hypothesis import given
from hypothesis import strategies as st

from ._sir_strategies import TRIBOOL, clean_analysis_claim, clean_communication_ladder

#: The ADR §18 line 472 honesty ladder, **independently transcribed** here so a drift between the ADR
#: and :class:`~tos.sir.vocabulary.CommunicationAssertionKind` fails loudly (design #28 §7.2 / appendix
#: C). ``過 0 · 不 0`` — exactly nine, in ADR order.
_ADR_HONESTY_LADDER: tuple[str, ...] = (
    "OBSERVED_FACT",  # "observed fact"
    "CONSERVATIVE_ASSUMPTION",  # "conservative assumption"
    "UNRESOLVED_UNKNOWN",  # "unresolved UNKNOWN"
    "PLANNED_ACTION",  # "planned action"
    "AUTHORIZED_ACTION",  # "authorized action"
    "TRANSMITTED_ATTEMPT",  # "transmitted attempt"
    "BROKER_EVIDENCE",  # "broker evidence"
    "VERIFIED_RESULT",  # "verified result"
    "ADMINISTRATIVE_DECISION",  # "administrative decision"
)


# --- anchor drift: the §18:472 9-token ladder -------------------------------


def test_communication_assertion_kind_matches_the_adr_nine_token_anchor() -> None:
    """(§7.2 drift) ``CommunicationAssertionKind`` equals the ADR §18 line 472 9-token set."""
    assert tuple(member.value for member in s.CommunicationAssertionKind) == (
        _ADR_HONESTY_LADDER
    )
    assert len(_ADR_HONESTY_LADDER) == 9


def test_no_strength_order_is_authored() -> None:
    """(M7 honesty) The ADR states a **distinction** obligation, not a strength total order.

    design #28 v1.0 invented a "stronger kind" promotion rule and v1.1 withdrew it: §18 line 472 says
    communications SHALL *distinguish* the nine kinds and says nothing about ranking them. Any ranking
    is policy-owned and Phase-0, so no rank / order / strength surface may exist in ``tos.sir``.
    """
    for forbidden in (
        "ASSERTION_STRENGTH_ORDER",
        "assertion_strength",
        "assertion_rank",
        "COMMUNICATION_ASSERTION_ORDER",
        "stronger_assertion",
    ):
        assert not hasattr(s, forbidden), (
            f"{forbidden} would re-introduce the withdrawn §18 strength total order (design #28 "
            "§5.3 conjunct 2, M7) — the ADR states a distinction obligation only"
        )


# --- both ways: the clean communication holds -------------------------------


def test_clean_communication_is_honest() -> None:
    """(both-ways positive) Every conjunct satisfied ⇒ the communication is honest."""
    assert (
        s.evidence_communication_status_honest(
            clean_communication_ladder(), clean_analysis_claim()
        )
        is True
    )


def test_absent_ladder_or_claim_denies() -> None:
    """(∅-seal) An absent ladder or analysis claim is undecidable ⇒ deny."""
    assert s.evidence_communication_status_honest(None, clean_analysis_claim()) is False
    assert (
        s.evidence_communication_status_honest(clean_communication_ladder(), None)
        is False
    )
    assert s.evidence_communication_status_honest(None, None) is False


# --- conjunct 2: the §18:472 distinction obligation -------------------------


def test_missing_assertion_kind_denies() -> None:
    """(§18:472) A communication that distinguishes nothing is not honest."""
    ladder = clean_communication_ladder(assertion_kind=None, claimed_as=None)
    assert s.communication_assertions_distinguished(ladder) is False


def test_unlabelled_communication_is_distinguished() -> None:
    """(§18:472) A communication with a kind and no separate label satisfies the obligation."""
    ladder = clean_communication_ladder(claimed_as=None)
    assert s.communication_assertions_distinguished(ladder) is True


@given(claimed=st.sampled_from(list(s.CommunicationAssertionKind)))
def test_label_must_match_the_assertion_kind(
    claimed: s.CommunicationAssertionKind,
) -> None:
    """(§18:472) Labelling one kind as another is a distinction violation ⇒ deny."""
    ladder = clean_communication_ladder(
        assertion_kind=s.CommunicationAssertionKind.CONSERVATIVE_ASSUMPTION,
        claimed_as=claimed,
    )
    expected = claimed is s.CommunicationAssertionKind.CONSERVATIVE_ASSUMPTION
    assert s.communication_assertions_distinguished(ladder) is expected
    assert (
        s.evidence_communication_status_honest(ladder, clean_analysis_claim())
        is expected
    )


def test_conservative_assumption_labelled_as_observed_fact_denies() -> None:
    """(§18:472, the named case) A conservative assumption presented as observed fact is dishonest."""
    ladder = clean_communication_ladder(
        assertion_kind=s.CommunicationAssertionKind.CONSERVATIVE_ASSUMPTION,
        claimed_as=s.CommunicationAssertionKind.OBSERVED_FACT,
    )
    assert (
        s.evidence_communication_status_honest(ladder, clean_analysis_claim()) is False
    )


# --- conjunct 3: message ack != enforcement ack -----------------------------


@given(is_ack=TRIBOOL, treated=TRIBOOL)
def test_message_ack_never_becomes_an_enforcement_ack(
    is_ack: bool | None, treated: bool | None
) -> None:
    """(§18:472; §4.3) A positive enforcement-ack claim always denies; on a message ack ``None`` too."""
    ladder = clean_communication_ladder(
        is_message_ack=is_ack, treated_as_enforcement_ack=treated
    )
    if treated is True:
        expected = False
    elif is_ack is True:
        expected = treated is False
    else:
        expected = True
    assert s.message_ack_not_enforcement_ack(ladder) is expected
    assert (
        s.evidence_communication_status_honest(ladder, clean_analysis_claim())
        is expected
    )


def test_unknown_enforcement_ack_on_a_message_ack_denies() -> None:
    """(§4.3 negative polarity) ``None`` on a message ack is UNKNOWN ⇒ deny, never a silent clear."""
    ladder = clean_communication_ladder(
        is_message_ack=True, treated_as_enforcement_ack=None
    )
    assert s.message_ack_not_enforcement_ack(ladder) is False


# --- conjunct 4-5: analysis is not prevention -------------------------------


@given(substitutes=TRIBOOL)
def test_substitutes_prevention_is_negative_polarity(substitutes: bool | None) -> None:
    """(SIR-INV-014 line 210; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    claim = clean_analysis_claim(substitutes_prevention=substitutes)
    assert s.analysis_not_prevention(claim) is (substitutes is False)
    assert s.evidence_communication_status_honest(
        clean_communication_ladder(), claim
    ) is (substitutes is False)


@given(authorizes=TRIBOOL)
def test_authorizes_past_effect_is_negative_polarity(authorizes: bool | None) -> None:
    """(§18 line 474; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    claim = clean_analysis_claim(authorizes_past_effect=authorizes)
    assert s.analysis_not_prevention(claim) is (authorizes is False)


def test_absent_analysis_claim_denies() -> None:
    """(∅-seal) An absent analysis claim is undecidable ⇒ deny."""
    assert s.analysis_not_prevention(None) is False


# --- supporting: emergency evidence suppresses nothing (§18 line 470) -------


@given(waits=TRIBOOL, blocks=TRIBOOL, suppressed=TRIBOOL)
def test_emergency_evidence_path_suppresses_nothing(
    waits: bool | None, blocks: bool | None, suppressed: bool | None
) -> None:
    """(§18 line 470) Restriction waits for nothing, evidence loss blocks closure, no HALT suppressed."""
    expected = waits is False and blocks is True and suppressed is False
    assert s.emergency_evidence_no_suppress(waits, blocks, suppressed) is expected
