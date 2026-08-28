"""Conservative projection — within_limits + apply_benefit (RCL design §5.1).

The three fail-closed rules: missing-dimension = restrictive (empty-set fail-open
canary), benefit = 0 unless positively proven, and no dimension is treated as ``0``.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.rcl import (
    BenefitClaim,
    BenefitProof,
    aggregate_usage,
    apply_benefit,
    within_limits,
)

from ._rcl_strategies import MAGNITUDE, vec

DIMS = ["gross_notional"]


# ---- within_limits: missing-dimension = restrictive (§5.1 rule 3) ----------


def test_empty_dimension_set_is_false_never_vacuous_true() -> None:
    """(canary) An empty applicable-dimension set => False, never a vacuous True."""
    assert within_limits(vec(gross_notional=1), vec(gross_notional=10), []) is False


def test_none_dimension_not_treated_as_zero() -> None:
    """(canary) A None (UNKNOWN) magnitude on either side => False, not 0."""
    # Effect UNKNOWN on the applicable dimension.
    assert (
        within_limits(vec(gross_notional=None), vec(gross_notional=10), DIMS) is False
    )
    # Limit UNKNOWN on the applicable dimension.
    assert within_limits(vec(gross_notional=1), vec(gross_notional=None), DIMS) is False


def test_absent_dimension_is_restrictive() -> None:
    """A dimension applicable but absent from either vector => False (fail-closed)."""
    assert within_limits(vec(other=1), vec(gross_notional=10), DIMS) is False
    assert within_limits(vec(gross_notional=1), vec(other=10), DIMS) is False


@given(effect=MAGNITUDE, limit=MAGNITUDE)
def test_within_limits_iff_effect_le_limit(effect: Decimal, limit: Decimal) -> None:
    """Property: within_limits <=> effect <= limit on the (present) applicable dim."""
    result = within_limits(vec(gross_notional=effect), vec(gross_notional=limit), DIMS)
    assert result is (effect <= limit)


def test_all_applicable_dimensions_must_hold() -> None:
    """Every applicable dimension must be present and within limit."""
    effect = vec(a=1, b=5)
    limits = vec(a=10, b=3)  # b exceeds
    assert within_limits(effect, limits, ["a", "b"]) is False
    assert within_limits(effect, vec(a=10, b=10), ["a", "b"]) is True


# ---- apply_benefit: 0 unless positively proven (§5.1 rule 2) ---------------


def test_benefit_none_returns_base_unchanged() -> None:
    """(canary) apply_benefit(v, claim, proof=None) == v — no reduction without proof."""
    base = vec(gross_notional=10)
    claim = BenefitClaim(kind="netting", reduction=vec(gross_notional=4))
    assert apply_benefit(base, claim, None) == base


def test_benefit_requires_positive_proof_token() -> None:
    """A non-positive proof (missing profile or scope) reduces nothing."""
    base = vec(gross_notional=10)
    claim = BenefitClaim(reduction=vec(gross_notional=4))
    assert apply_benefit(base, claim, BenefitProof()) == base
    assert apply_benefit(base, claim, BenefitProof(broker_profile_proven=True)) == base
    assert apply_benefit(base, claim, BenefitProof(scope_proven=True)) == base


def test_positive_proof_reduces() -> None:
    """A positive proof token (profile + scope proven) reduces the adverse increment."""
    base = vec(gross_notional=10)
    claim = BenefitClaim(reduction=vec(gross_notional=4))
    proof = BenefitProof(broker_profile_proven=True, scope_proven=True)
    reduced = apply_benefit(base, claim, proof)
    assert reduced.magnitude("gross_notional") == Decimal(6)


def test_benefit_never_negative() -> None:
    """A proven reduction is clamped at 0 — never made negative (§6.3 line 277)."""
    base = vec(gross_notional=3)
    claim = BenefitClaim(reduction=vec(gross_notional=10))
    proof = BenefitProof(broker_profile_proven=True, scope_proven=True)
    assert apply_benefit(base, claim, proof).magnitude("gross_notional") == Decimal(0)


def test_benefit_leaves_unknown_dimension_unknown() -> None:
    """A proven benefit cannot manufacture a bound for an UNKNOWN dimension."""
    base = vec(gross_notional=None)
    claim = BenefitClaim(reduction=vec(gross_notional=4))
    proof = BenefitProof(broker_profile_proven=True, scope_proven=True)
    assert apply_benefit(base, claim, proof).magnitude("gross_notional") is None


@given(uncertainty=st.integers(min_value=0, max_value=100))
def test_aggregate_usage_monotone_in_uncertainty(uncertainty: int) -> None:
    """Adding a non-negative uncertainty term never lowers aggregate usage (§5.1 r1).

    Drives the production projection surface (:func:`aggregate_usage`): a larger
    injected uncertainty component aggregates to a >= usage vector (monotone
    non-decreasing; no negative-clamp shortcut).
    """
    base = aggregate_usage([vec(gross_notional=5)])
    higher = aggregate_usage([vec(gross_notional=5), vec(gross_notional=uncertainty)])
    base_mag = base.magnitude("gross_notional")
    higher_mag = higher.magnitude("gross_notional")
    assert base_mag is not None and higher_mag is not None
    assert higher_mag >= base_mag
    assert higher_mag == base_mag + uncertainty
