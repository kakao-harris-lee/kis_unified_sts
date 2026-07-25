"""Envelope dominance / non-silent expansion (design #12 §4.1/§5.1; SPG-EV-001 substrate).

Both-ways canaries (the guard fires AND does not over-block) + the ∅-void hunt (an empty
envelope dimension set grants zero authority; a None fails closed).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.spg import (
    ValidationReason,
    envelope_bounded,
    envelope_expansion_enlarges_nothing,
    envelope_incompatible,
    envelope_not_expanded,
    profile_within_envelope,
)

from ._spg_strategies import (
    envelope_dimension,
    issue_envelope,
    issue_profile,
    over_envelope_profile,
    profile_dimension,
)

# ---------------------------------------------------------------------------
# profile_within_envelope — both-ways
# ---------------------------------------------------------------------------


def test_within_envelope_positive_side() -> None:
    """(canary +) A within-envelope profile validates with an empty reason set."""
    result = profile_within_envelope(issue_envelope(), issue_profile())
    assert result.valid is True
    assert result.reason_set == frozenset()


def test_over_envelope_is_rejected() -> None:
    """(canary -) A value over the envelope max => invalid + EXCEEDS_ENVELOPE + the dim."""
    result = profile_within_envelope(issue_envelope(), over_envelope_profile())
    assert result.valid is False
    assert ValidationReason.EXCEEDS_ENVELOPE in result.reason_set
    assert "qty" in result.rejected_dimensions


def test_none_envelope_or_profile_fails_closed() -> None:
    """(fail-closed) A None envelope or profile is invalid (never vacuously within)."""
    assert profile_within_envelope(None, issue_profile()).valid is False
    assert profile_within_envelope(issue_envelope(), None).valid is False


def test_generation_mismatch_fails_closed() -> None:
    """(§10 line 281) A profile pinning a different envelope generation is rejected."""
    env = issue_envelope(envelope_generation=2)
    prof = issue_profile(target_envelope_generation=1)  # pins gen 1, not gen 2
    assert profile_within_envelope(env, prof).valid is False


# ---------------------------------------------------------------------------
# ∅-void hunt — empty envelope dimension set grants zero authority
# ---------------------------------------------------------------------------


def test_empty_envelope_dimension_set_grants_zero_authority() -> None:
    """(∅-seal §5.1) An empty envelope + a profile referencing a dimension => rejected."""
    empty_env = issue_envelope(governed_dimensions=())
    prof = issue_profile(
        governed_dimensions=(profile_dimension(profile_value=Decimal("1")),)
    )
    result = profile_within_envelope(empty_env, prof)
    assert result.valid is False  # NOT vacuously dominant
    assert "qty" in result.rejected_dimensions


def test_undeclared_dimension_is_rejected() -> None:
    """(§9 line 264) A profile dimension the envelope does not declare is over-envelope."""
    env = issue_envelope(governed_dimensions=(envelope_dimension(dimension="qty"),))
    prof = issue_profile(governed_dimensions=(profile_dimension(dimension="notional"),))
    result = profile_within_envelope(env, prof)
    assert result.valid is False
    assert "notional" in result.rejected_dimensions


def test_missing_envelope_max_fails_closed() -> None:
    """(fail-closed §5.1) A declared dimension with a None max cannot admit a value."""
    env = issue_envelope(
        governed_dimensions=(envelope_dimension(dimension="qty", envelope_max=None),)
    )
    result = profile_within_envelope(env, issue_profile())
    assert result.valid is False


def test_scope_not_subset_is_rejected() -> None:
    """(§9) A profile scope outside the envelope permitted scope is rejected."""
    env = issue_envelope(permitted_scope=("acct-1",))
    prof = issue_profile(scope=("acct-1", "acct-2"))
    result = profile_within_envelope(env, prof)
    assert result.valid is False
    assert "<scope>" in result.rejected_dimensions


def test_envelope_bounded_bool_matches_dominance() -> None:
    """The envelope_bounded seam bool mirrors profile_within_envelope validity."""
    assert envelope_bounded(issue_envelope(), issue_profile()) is True
    assert envelope_bounded(issue_envelope(), over_envelope_profile()) is False
    assert envelope_bounded(None, issue_profile()) is False


# ---------------------------------------------------------------------------
# SPG-INV-001 "omit" limb — envelope -> profile coverage (the MAJOR fix)
# ---------------------------------------------------------------------------


def _two_dimension_envelope() -> object:
    """A mandatory-2-dimension envelope (qty + notional)."""
    return issue_envelope(
        governed_dimensions=(
            envelope_dimension(dimension="qty", envelope_max=Decimal("10")),
            envelope_dimension(dimension="notional", envelope_max=Decimal("100")),
        )
    )


def test_empty_profile_omits_mandatory_dimension_rejected() -> None:
    """(canary - "omit") An empty profile against a declaring envelope is invalid (not vacuous)."""
    empty_profile = issue_profile(governed_dimensions=())
    result = profile_within_envelope(issue_envelope(), empty_profile)
    assert result.valid is False  # a zero-iteration profile must NOT pass vacuously
    assert "qty" in result.rejected_dimensions  # the omitted mandatory dimension


def test_partial_profile_missing_one_mandatory_rejected() -> None:
    """(canary - "omit") A profile omitting one mandatory dimension is invalid + names it."""
    partial = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
        )
    )  # notional omitted
    result = profile_within_envelope(_two_dimension_envelope(), partial)
    assert result.valid is False
    assert "notional" in result.rejected_dimensions  # the omitted mandatory dimension


def test_full_coverage_within_bounds_is_valid() -> None:
    """(canary + positive) A profile covering ALL mandatory dimensions within max is valid."""
    full = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
            profile_dimension(dimension="notional", profile_value=Decimal("50")),
        )
    )
    result = profile_within_envelope(_two_dimension_envelope(), full)
    assert result.valid is True
    assert result.reason_set == frozenset()


def test_both_empty_envelope_and_profile_grants_zero_authority() -> None:
    """(∅-seal both directions) An empty envelope cannot vacuously dominate an empty profile."""
    result = profile_within_envelope(
        issue_envelope(governed_dimensions=()),
        issue_profile(governed_dimensions=()),
    )
    assert result.valid is False  # zero-authority envelope => nothing is within it
    assert "<no-envelope-dimensions>" in result.rejected_dimensions


def test_empty_profile_propagates_to_envelope_bounded_false() -> None:
    """(propagation) An empty profile fails the envelope_bounded seam bool closed."""
    assert (
        envelope_bounded(issue_envelope(), issue_profile(governed_dimensions=()))
        is False
    )


# ---------------------------------------------------------------------------
# envelope_expansion_enlarges_nothing / envelope_not_expanded — both-ways
# ---------------------------------------------------------------------------


def test_expansion_enlarges_nothing_when_profile_unchanged() -> None:
    """(canary + SPG-INV-007) A wider envelope + an unchanged in-old-bounds profile => True."""
    old_env = issue_envelope(
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("10")),)
    )
    new_env = issue_envelope(
        envelope_generation=2,
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("100")),),
    )
    profile = issue_profile(
        governed_dimensions=(profile_dimension(profile_value=Decimal("5")),)
    )
    assert envelope_expansion_enlarges_nothing(old_env, new_env, profile) is True
    assert envelope_not_expanded(old_env, new_env, profile) is True


def test_expansion_that_enlarges_profile_is_false() -> None:
    """(canary -) A profile value grown to exploit the new wider ceiling => False."""
    old_env = issue_envelope(
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("10")),)
    )
    new_env = issue_envelope(
        envelope_generation=2,
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("100")),),
    )
    grown = issue_profile(
        governed_dimensions=(profile_dimension(profile_value=Decimal("50")),)
    )  # 50 > old max 10
    assert envelope_expansion_enlarges_nothing(old_env, new_env, grown) is False
    assert envelope_not_expanded(old_env, new_env, grown) is False


def test_expansion_none_fails_closed() -> None:
    """(fail-closed) A None on any argument fails closed to False."""
    assert envelope_not_expanded(None, issue_envelope(), issue_profile()) is False
    assert envelope_not_expanded(issue_envelope(), None, issue_profile()) is False
    assert envelope_not_expanded(issue_envelope(), issue_envelope(), None) is False


# ---------------------------------------------------------------------------
# envelope_incompatible — polarity (True => authority invalidated side)
# ---------------------------------------------------------------------------


def test_envelope_incompatible_polarity() -> None:
    """(authority seam) Matching generation => compatible(False); mismatch/None => True."""
    env = issue_envelope(envelope_generation=3)
    assert envelope_incompatible(env, 3) is False  # compatible
    assert envelope_incompatible(env, 2) is True  # stale/mismatch => invalidated side
    assert envelope_incompatible(env, None) is True  # unknown => invalidated side
    assert envelope_incompatible(None, 3) is True  # no active envelope => fail-closed


@given(presented=st.none() | st.integers(min_value=0, max_value=5))
def test_envelope_incompatible_only_false_on_exact_match(presented: int | None) -> None:
    """(property) envelope_incompatible is False ONLY for the exact matching generation."""
    env = issue_envelope(envelope_generation=3)
    result = envelope_incompatible(env, presented)
    assert result is (presented != 3)
