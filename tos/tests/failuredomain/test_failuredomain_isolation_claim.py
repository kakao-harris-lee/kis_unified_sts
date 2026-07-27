"""§4.1 ``unproven_isolation_is_common_mode`` — ∅ both ways, blank forgery, polarity (design #27 §6).

ADR-002-009 §1 line 32: "If an asserted isolation property cannot be positively established, the
affected paths SHALL be classified as common-mode." §5 line 130: "Unknown, untested, or
undocumented sharing SHALL be recorded as common-mode. It SHALL NOT be recorded as independent
with an explanatory footnote."

**both-ways canary** on every guard: the guard genuinely fires (each of the five §4.4 fields, when
voided, forces common-mode) **and** it does not block a legitimate establishment (a genuinely
complete claim reaches ``ESTABLISHED``). ``∅`` is exercised in both directions: a bare unmarked
``frozenset()`` never buys an establishment, while the positively-analysed ``∅`` marker does.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.failuredomain import (
    ExplicitlyAnalyzedEmpty,
    IsolationClaim,
    IsolationClaimStatus,
    unproven_isolation_is_common_mode,
)
from tos.failuredomain.predicates import _isolation_claim_status

from ._failuredomain_strategies import (
    BLANK_TEXTS,
    CLAIM_FIELDS,
    NON_BLANK_TOKENS,
    clean_claim,
)

#: The four collection-shaped §4.4 fields (``residual_risk`` is free text).
_COLLECTION_FIELDS: tuple[str, ...] = (
    "assumptions",
    "excluded_common_modes",
    "enforcement_mechanisms",
    "verification_cases",
)


# --- both-ways: the legitimate establishment is NOT blocked ------------------


def test_a_genuinely_complete_claim_is_established() -> None:
    """(both-ways b) All five §4.4 fields positively stated => NOT common-mode."""
    assert unproven_isolation_is_common_mode(clean_claim()) is False
    assert _isolation_claim_status(clean_claim()) is IsolationClaimStatus.ESTABLISHED


def test_the_clean_fixture_is_genuinely_complete_not_a_shortcut() -> None:
    """(#8 fixture discipline) The clean claim really fills all five fields with content."""
    claim = clean_claim()
    for field in CLAIM_FIELDS:
        assert getattr(claim, field) is not None, field
    assert set(IsolationClaim.model_fields) >= set(CLAIM_FIELDS)


# --- both-ways: the guard genuinely fires -----------------------------------


def test_absent_claim_is_common_mode_and_unknown() -> None:
    """(§4.1) ``claim is None`` => common-mode, and the private status axis says UNKNOWN."""
    assert unproven_isolation_is_common_mode(None) is True
    assert _isolation_claim_status(None) is IsolationClaimStatus.UNKNOWN


def test_empty_claim_is_common_mode() -> None:
    """(§4.1) A default (all-unset) claim is common-mode — no vacuous establishment."""
    assert unproven_isolation_is_common_mode(IsolationClaim()) is True
    assert _isolation_claim_status(IsolationClaim()) is IsolationClaimStatus.COMMON_MODE


@pytest.mark.parametrize("field", _COLLECTION_FIELDS)
def test_each_collection_field_voided_to_none_forces_common_mode(field: str) -> None:
    """(§4.1 per-field) Voiding any one of the four collection fields to None fires the guard."""
    assert unproven_isolation_is_common_mode(clean_claim(**{field: None})) is True


@pytest.mark.parametrize("field", _COLLECTION_FIELDS)
def test_each_collection_field_voided_to_bare_empty_forces_common_mode(
    field: str,
) -> None:
    """(∅ vacuity) A bare unmarked ``frozenset()`` is not a positive statement (ADR §5 line 130)."""
    assert (
        unproven_isolation_is_common_mode(clean_claim(**{field: frozenset()})) is True
    )


@pytest.mark.parametrize("field", _COLLECTION_FIELDS)
@pytest.mark.parametrize("blank", BLANK_TEXTS)
def test_blank_entries_never_forge_a_positive_listing(field: str, blank: str) -> None:
    """(blank forgery) A set whose only entry is blank/whitespace is not a statement.

    ``" "`` / ``"\\t"`` / ``"\\n"`` are **truthy** strings — exactly what a ``if value:`` presence
    check would wrongly admit — so the predicate strips before deciding (design #27 §4.1).
    """
    assert (
        unproven_isolation_is_common_mode(clean_claim(**{field: frozenset({blank})}))
        is True
    )


@pytest.mark.parametrize("blank", BLANK_TEXTS)
def test_blank_residual_risk_never_forges_a_statement(blank: str) -> None:
    """(blank forgery) ADR §4.4 requires the claim to *state* residual risk; " " states nothing."""
    assert unproven_isolation_is_common_mode(clean_claim(residual_risk=blank)) is True


def test_none_residual_risk_forces_common_mode() -> None:
    """(§4.1 per-field) The fifth §4.4 field is required just like the other four."""
    assert unproven_isolation_is_common_mode(clean_claim(residual_risk=None)) is True


def test_one_blank_entry_among_valid_ones_still_forges_nothing() -> None:
    """(blank forgery, mixed) A padded blank smuggled into a real list still fails the claim."""
    claim = clean_claim(assumptions=frozenset({"a real assumption", "  "}))
    assert unproven_isolation_is_common_mode(claim) is True


# --- ∅ both ways on ``excluded_common_modes`` --------------------------------


def test_explicitly_analyzed_empty_exclusions_still_establish() -> None:
    """(∅ both ways) A positively-analysed "nothing to exclude" does NOT block establishment."""
    claim = clean_claim(
        excluded_common_modes=ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY
    )
    assert unproven_isolation_is_common_mode(claim) is False


def test_the_marker_does_not_rescue_an_otherwise_incomplete_claim() -> None:
    """(∅ both ways) The marker only satisfies its own field — the other four still apply."""
    claim = clean_claim(
        excluded_common_modes=ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY,
        verification_cases=None,
    )
    assert unproven_isolation_is_common_mode(claim) is True


def test_the_marker_is_only_accepted_on_the_exclusions_field() -> None:
    """(§4.1 scope) Only ``excluded_common_modes`` takes the ∅ marker — the others are sets."""
    for field in ("assumptions", "enforcement_mechanisms", "verification_cases"):
        with pytest.raises(ValueError):
            clean_claim(**{field: ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY})


def test_bare_empty_exclusions_and_marker_are_distinguishable() -> None:
    """(∅ both ways, the core distinction) ``frozenset()`` != the analysed-empty marker."""
    vacuous = clean_claim(excluded_common_modes=frozenset())
    analysed = clean_claim(
        excluded_common_modes=ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY
    )
    assert unproven_isolation_is_common_mode(vacuous) is True
    assert unproven_isolation_is_common_mode(analysed) is False
    assert vacuous.excluded_common_modes != analysed.excluded_common_modes


# --- properties --------------------------------------------------------------


@given(field=st.sampled_from(CLAIM_FIELDS))
def test_property_voiding_any_single_field_forces_common_mode(field: str) -> None:
    """(§4.1 property) An otherwise complete claim missing any ONE field is common-mode."""
    assert unproven_isolation_is_common_mode(clean_claim(**{field: None})) is True


@given(
    assumptions=NON_BLANK_TOKENS,
    exclusions=NON_BLANK_TOKENS,
    mechanisms=NON_BLANK_TOKENS,
    cases=NON_BLANK_TOKENS,
    residual=st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != ""),
)
def test_property_any_fully_stated_claim_is_established(
    assumptions: frozenset[str],
    exclusions: frozenset[str],
    mechanisms: frozenset[str],
    cases: frozenset[str],
    residual: str,
) -> None:
    """(§4.1 property, both-ways) Arbitrary non-blank content in all five fields establishes."""
    claim = IsolationClaim(
        assumptions=assumptions,
        excluded_common_modes=exclusions,
        enforcement_mechanisms=mechanisms,
        verification_cases=cases,
        residual_risk=residual,
    )
    assert unproven_isolation_is_common_mode(claim) is False


@given(field=st.sampled_from(_COLLECTION_FIELDS), blank=st.sampled_from(BLANK_TEXTS))
def test_property_blank_entries_are_never_positive(field: str, blank: str) -> None:
    """(blank forgery property) No blank string in any collection field ever counts as stated."""
    assert (
        unproven_isolation_is_common_mode(clean_claim(**{field: frozenset({blank})}))
        is True
    )


def test_status_axis_returns_only_the_three_registered_members() -> None:
    """(§2.1C polarity) The private classifier never invents a fourth status."""
    observed = {
        _isolation_claim_status(None),
        _isolation_claim_status(IsolationClaim()),
        _isolation_claim_status(clean_claim()),
    }
    assert observed == set(IsolationClaimStatus)


def test_predicate_is_the_exact_negation_of_established() -> None:
    """(polarity) ``unproven...`` is True iff the status is NOT positively ESTABLISHED."""
    for claim in (None, IsolationClaim(), clean_claim()):
        expected = (
            _isolation_claim_status(claim) is not IsolationClaimStatus.ESTABLISHED
        )
        assert unproven_isolation_is_common_mode(claim) is expected
