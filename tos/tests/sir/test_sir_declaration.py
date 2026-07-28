"""MANDATED property test — restrictive declaration (SIR-EV-001 / SIR-AC-001; design #28 §5.1/§7.2).

The first yolk. ``restrictive_declaration_non_authorizing`` decides whether an incident declaration is
**restrictive, asymmetric and non-authorizing** (ADR-002-027 §8; SIR-INV-001/002/003). This file is the
design #28 §13 mandated property test for the ``EV-L1`` slice of SIR-EV-001, plus the §8 line 250-257
**8-class anchor drift** lock.

Both ways (design #28 §7.2): every conjunct satisfied ⇒ ``True``, and **each** conjunct violated
individually ⇒ ``False`` — so neither a vacuous pass nor a one-sided seal can hide.

**Closes no SIR-EV.** SIR-EV-001 is ``EV-L1/3+Security``: the ``/3`` integration and adversarial
evidence remains and the whole ``+Security`` axis (§22 line 532 signal suppression / forgery / downgrade
/ reordering) is runtime. Regime tag: restrictive-declaration predicate substrate only; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.sir as s
from hypothesis import given

from ._sir_strategies import (
    TRIBOOL,
    clean_classification,
    clean_record,
    clean_scope,
    clean_signal,
)

#: The ADR §8 line 250-257 classification classes, **independently transcribed** here so a drift
#: between the ADR and :class:`~tos.sir.vocabulary.SignalClassificationClass` fails loudly (design #28
#: §7.2 / appendix C). ``過 0 · 不 0`` — exactly eight.
_ADR_SIGNAL_CLASSES: frozenset[str] = frozenset(
    {
        "HARD_ENVELOPE_VIOLATION",  # line 250 Hard Safety Envelope violation
        "CONTROL_BYPASS",  # line 251 RCL / writer-fence / ... / final-egress bypass
        "BROKER_STATE_ANOMALY",  # line 252 missing / contradictory / stale / externally changed
        "PROTECTION_LOSS",  # line 253 protection loss / replacement gap / trapped exposure
        "CRITICAL_INPUT_COMPROMISE",  # line 254 Critical Input / config / identity / time / ...
        "UNAUTHORIZED_CROSSOVER",  # line 255 unauthorized live / non-live crossover
        "FAILED_GATE",  # line 256 failed bound / security control / independent approval
        "UNESTABLISHED_SCOPE_SEVERITY",  # line 257 scope or severity not yet establishable
    }
)


# --- anchor drift: the §8 8-class catalogue ---------------------------------


def test_signal_classification_matches_the_adr_eight_class_anchor() -> None:
    """(§7.2 drift) ``SignalClassificationClass`` equals the ADR §8 line 250-257 8-class set."""
    assert {
        member.value for member in s.SignalClassificationClass
    } == _ADR_SIGNAL_CLASSES
    assert len(_ADR_SIGNAL_CLASSES) == 8


def test_unestablished_class_is_the_fail_closed_convergence_point() -> None:
    """(§8 line 257) An unestablished scope/severity classifies as UNESTABLISHED_SCOPE_SEVERITY."""
    classification = clean_classification(
        unestablished=True,
        classification=s.SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY,
        policy_class_match=None,
    )
    assert s.classification_admissible(classification) is True
    # ... and an unestablished input labelled as a concrete class is inadmissible (understatement).
    understated = clean_classification(
        unestablished=True,
        classification=s.SignalClassificationClass.HARD_ENVELOPE_VIOLATION,
    )
    assert s.classification_admissible(understated) is False


# --- both ways: the clean declaration holds ---------------------------------


def test_clean_declaration_is_coherent() -> None:
    """(both-ways positive) Every conjunct satisfied ⇒ the declaration is coherent."""
    assert (
        s.restrictive_declaration_non_authorizing(clean_record(), clean_signal())
        is True
    )


def test_absent_record_or_signal_denies() -> None:
    """(∅-seal) An absent record or signal is undecidable ⇒ deny."""
    assert s.restrictive_declaration_non_authorizing(None, clean_signal()) is False
    assert s.restrictive_declaration_non_authorizing(clean_record(), None) is False
    assert s.restrictive_declaration_non_authorizing(None, None) is False


# --- conjunct 2: SIR-INV-001 all-false authority ----------------------------


def test_any_true_authority_flag_makes_the_record_unconstructable() -> None:
    """(SIR-INV-001 line 158) An authority-granting incident record cannot be constructed."""
    with pytest.raises((s.ArtifactIntegrityError, ValueError)):
        s.AllFalseIncidentAuthority(clears_halt=True)


def test_model_construct_authority_bypass_is_caught_by_the_predicate() -> None:
    """(2-layer §2.3) A ``model_construct`` all-false bypass is re-caught in the predicate layer."""
    forged = s.AllFalseIncidentAuthority.model_construct(
        creates_capacity=False,
        creates_protection=False,
        creates_safety_authority=False,
        issues_live_authorization=True,  # forged grant
        creates_transmission_capability=False,
        grants_broker_permission=False,
        clears_halt=False,
        creates_production_scope=False,
        re_arms=False,
        classifies_protective_action=False,
        establishes_recovery_readiness=False,
    )
    assert s.all_false_incident_authority(forged) is False
    # the artifact model re-validates a nested block on the normal path, so the only way to smuggle
    # the forged grant in is the ``model_construct`` escape hatch — which the predicate layer catches.
    reference = clean_record()
    record = s.SafetyIncidentRecord.model_construct(
        **{
            **{
                name: getattr(reference, name)
                for name in s.SafetyIncidentRecord.model_fields
            },
            "authority_effect": forged,
        }
    )
    assert s.declaration_creates_no_authority(record) is False
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is False


# --- conjunct 3: the two recognition axes (M6 disjunction) ------------------


@given(material=TRIBOOL, establishable=TRIBOOL)
def test_declaration_subject_axis_is_material_or_unestablished_scope(
    material: bool | None, establishable: bool | None
) -> None:
    """(§5.1 conjunct 3 / §8 line 257) Subject iff positively material OR scope not establishable."""
    record = clean_record()
    signal = clean_signal(is_material=material, scope_establishable=establishable)
    expected = material is True or establishable is not True
    assert s.restrictive_declaration_non_authorizing(record, signal) is expected


@given(authenticated=TRIBOOL)
def test_authentication_is_a_disjunction_not_a_gate(authenticated: bool | None) -> None:
    """(§5.2 line 110 / M6) An unauthenticated conservative inference is still a declaration subject.

    The v1.0 contract ANDed ``is_authenticated``; v1.1 withdrew that because §5.2 defines a Safety
    Signal as "an authenticated observation **or** conservative inference". Dismissing an
    unauthenticated inference would be the fail-open §8 line 257 exists to prevent.
    """
    signal = clean_signal(is_authenticated=authenticated)
    assert s.restrictive_declaration_non_authorizing(clean_record(), signal) is True


# --- conjunct 4-6: the negative / positive polarity gates -------------------


@given(gated=TRIBOOL)
def test_restriction_workflow_gated_is_negative_polarity(gated: bool | None) -> None:
    """(SIR-INV-002 line 162; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    record = clean_record(restriction_workflow_gated=gated)
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is (
        gated is False
    )


@given(narrows=TRIBOOL)
def test_severity_label_narrows_scope_is_negative_polarity(
    narrows: bool | None,
) -> None:
    """(§8 line 269; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    record = clean_record(severity_label_narrows_scope=narrows)
    assert s.low_severity_no_narrow(record) is (narrows is False)
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is (
        narrows is False
    )


@given(computed=TRIBOOL)
def test_greatest_credible_scope_computed_is_positive_polarity(
    computed: bool | None,
) -> None:
    """(§8 step 2 / SIR-INV-003; §4.3 positive) Only an explicit ``True`` admits."""
    record = clean_record(greatest_credible_scope_computed=computed)
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is (
        computed is True
    )


@given(self_exempted=TRIBOOL, narrowed=TRIBOOL)
def test_scope_self_exemption_and_narrowing_are_negative_polarity(
    self_exempted: bool | None, narrowed: bool | None
) -> None:
    """(§10 line 303 / §8 line 269; §4.3 negative) A self-exempted or narrowed scope denies."""
    scope = clean_scope(self_exempted=self_exempted, wildcard_or_narrowed=narrowed)
    record = clean_record(incident_scope=scope)
    expected = self_exempted is False and narrowed is False
    assert s.scope_not_self_exempt_or_narrowed(scope) is expected
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is expected


def test_absent_scope_structure_denies() -> None:
    """(∅-seal) A record with no exact scope structure is undecidable ⇒ deny."""
    record = clean_record(incident_scope=None)
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is False


# --- conjunct 7: classification admissibility -------------------------------


@given(match=TRIBOOL)
def test_policy_class_match_is_positive_polarity(match: bool | None) -> None:
    """(§8 line 248; §4.3 positive) An established classification needs a positive policy match."""
    record = clean_record(classification=clean_classification(policy_class_match=match))
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is (
        match is True
    )


def test_absent_classification_denies() -> None:
    """(∅-seal) A record with no classification input is undecidable ⇒ deny."""
    assert s.classification_admissible(None) is False
    record = clean_record(classification=None)
    assert s.restrictive_declaration_non_authorizing(record, clean_signal()) is False


def test_classification_with_no_class_denies() -> None:
    """(§8 line 248) An established input with no class at all is inadmissible."""
    classification = clean_classification(classification=None)
    assert s.classification_admissible(classification) is False
