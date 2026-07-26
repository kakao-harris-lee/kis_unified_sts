"""plan_scope_exact_and_complete yolk (RLP-EV-001) + 6-scalar seam anchor (design #25 §5.1/§7.2).

The yolk 1 property suite: ∅ both-ways, drop-one scope incompleteness, wildcard denial, baseline
binding, pre-registered / reviewed polarity, result admissibility — plus the manually-transcribed
regression anchors (ScopeDimension == §9 line 263 catalogue; TrialScope fields == ScopeDimension;
TrialClaimGroup 6-scalar == egress §11.1 / cur §9:258 field set).

Regime tag: structural / completeness predicate substrate only; RLP-EV-001 NOT_IMPLEMENTED
(``EV-L1/3`` — ``/3`` integration / adversarial pending); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.rlp import (
    MANDATED_SCOPE_FLOOR,
    ArtifactIntegrityError,
    ExactTrialPlan,
    PlanResult,
    ScopeDimension,
    TrialClaimGroup,
    TrialScope,
    is_wildcard_value,
    plan_result_admissible,
    plan_scope_exact_and_complete,
)

from ._rlp_strategies import (
    TRIBOOL,
    clean_plan,
    clean_policy,
    clean_scope,
)

# --- manually-transcribed regression anchors (design #25 §0.4h / §7.2) --------

#: The §9 line 263 exact-scope catalogue, transcribed by hand from the ADR (NOT derived). The
#: anchor-drift property asserts the ``ScopeDimension`` enum equals exactly this set.
_SCOPE_ANCHOR: frozenset[str] = frozenset(
    {
        "ENVIRONMENT",
        "SAFETY_CELL",
        "CAPACITY_DOMAIN",
        "PORTFOLIO",
        "ACCOUNT",
        "BROKER",
        "VENUE",
        "INSTRUMENT",
        "STRATEGY",
        "ACTION_CLASS",
        "ORDER_SHAPE",
        "SOFTWARE_RELEASE",
        "CONFIGURATION",
        "IDENTITY",
        "CREDENTIAL",
        "ROUTE",
        "SESSION",
        "TIME_INTERVAL",
        "FAILURE_DOMAIN",
    }
)

#: The egress §11.1 line 308 / cur §9:258 6-scalar trial claim group field set, transcribed by hand.
_TRIAL_CLAIM_SCALAR_ANCHOR: frozenset[str] = frozenset(
    {
        "trial_policy_generation",
        "trial_plan_generation",
        "trial_run_generation",
        "promotion_generation",
        "remaining_envelope",
        "abort_generation",
    }
)


def test_scope_dimension_matches_the_section9_anchor() -> None:
    """(§7.2 anchor drift) ScopeDimension == the §9 line 263 reference set — a drift is caught."""
    assert {d.value for d in ScopeDimension} == _SCOPE_ANCHOR
    assert frozenset(ScopeDimension) == MANDATED_SCOPE_FLOOR


def test_trial_scope_fields_match_scope_dimension() -> None:
    """(§7.2 anchor drift) Every TrialScope field is a lowercased ScopeDimension member, and back."""
    scope_fields = set(TrialScope.model_fields)
    dimension_fields = {d.name.lower() for d in ScopeDimension}
    assert scope_fields == dimension_fields


def test_trial_claim_group_scalars_match_the_seam_anchor() -> None:
    """(§0.4h / §7.2) TrialClaimGroup 6-scalar == egress §11.1 / cur §9:258 field set (anchor)."""
    assert set(TrialClaimGroup.REQUIRED_SCALARS) == _TRIAL_CLAIM_SCALAR_ANCHOR
    # and the model's own fields carry exactly those six scalars.
    assert set(TrialClaimGroup.model_fields) == _TRIAL_CLAIM_SCALAR_ANCHOR


# --- ∅ both-ways ------------------------------------------------------------


def test_empty_seal_both_ways() -> None:
    """(§5.1 point 1) None plan / None policy / ∅ mandate all deny (never vacuously complete)."""
    plan = clean_plan()
    policy = clean_policy()
    assert plan_scope_exact_and_complete(None, policy, MANDATED_SCOPE_FLOOR) is False
    assert plan_scope_exact_and_complete(plan, None, MANDATED_SCOPE_FLOOR) is False
    assert plan_scope_exact_and_complete(plan, policy, frozenset()) is False


def test_clean_plan_is_exact_and_complete() -> None:
    """(§5.1 positive) A genuinely eligible, fully-scoped, reviewed plan passes the yolk."""
    assert (
        plan_scope_exact_and_complete(
            clean_plan(), clean_policy(), MANDATED_SCOPE_FLOOR
        )
        is True
    )


# --- drop-one scope incompleteness (model_construct bypass — defence in depth, §2.3) ---


@given(dropped=st.sampled_from(list(ScopeDimension)))
def test_drop_one_scope_dimension_denies(dropped: ScopeDimension) -> None:
    """(§5.1 point 3 / drop-one) A plan missing any one scope dimension is incomplete ⇒ deny.

    Uses ``model_construct`` to bypass the construction-time coexistence seal (which would itself
    reject an eligible plan with an incomplete scope) — the predicate layer must **independently**
    re-derive incompleteness (defence in depth, §2.3 / #20 lesson).
    """
    scope_kwargs = {d.name.lower(): f"v-{d.name.lower()}" for d in ScopeDimension}
    scope_kwargs[dropped.name.lower()] = None
    malformed = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=TrialScope(**scope_kwargs),
        baseline_digests=("b1",),
        pre_registered=True,
        independently_reviewed=True,
    )
    assert (
        plan_scope_exact_and_complete(malformed, clean_policy(), MANDATED_SCOPE_FLOOR)
        is False
    )


@given(wild=st.sampled_from(list(ScopeDimension)))
def test_wildcard_scope_dimension_denies(wild: ScopeDimension) -> None:
    """(§5.1 point 4 / RLP-INV-002:154) A wildcard on any dimension denies (not exact)."""
    scope_kwargs = {d.name.lower(): f"v-{d.name.lower()}" for d in ScopeDimension}
    scope_kwargs[wild.name.lower()] = "*"
    malformed = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=TrialScope(**scope_kwargs),
        baseline_digests=("b1",),
        pre_registered=True,
        independently_reviewed=True,
    )
    assert (
        plan_scope_exact_and_complete(malformed, clean_policy(), MANDATED_SCOPE_FLOOR)
        is False
    )


# --- MAJOR-1 (#25): normalized + metacharacter-aware wildcard detection --------

#: Wildcard probes that a naive exact-cased / substring-free denylist silently passed as concrete
#: (the #25 MAJOR-1 finding) — case variants of catalogued sentinels, whitespace padding, glob /
#: regex / SQL-LIKE metacharacters, a fullwidth asterisk, a universal-quantifier word, and blanks.
_WILDCARD_PROBES = (
    "All",  # a case variant of the "all" sentinel (its own list, re-cased)
    "aLL",  # another case variant
    " * ",  # whitespace-padded sentinel
    "*.KOSPI",  # glob prefix metacharacter
    "KOSPI*",  # glob suffix metacharacter
    "%",  # SQL-LIKE metacharacter
    "**",  # double glob
    ".*",  # regex
    "＊",  # fullwidth asterisk
    "everything",  # a universal-quantifier sentinel
    "",  # empty
    "   ",  # whitespace-only
)

#: Normal, genuinely exact scope / baseline values that must NOT be flagged as wildcards.
_CONCRETE_PROBES = ("KOSPI200F", "paper_account_01", "v-environment", "baseline-1")


@given(probe=st.sampled_from(_WILDCARD_PROBES))
def test_wildcard_probes_are_non_exact_both_ways(probe: str) -> None:
    """(§5.1 / RLP-INV-002:154 — #25 MAJOR-1) Every wildcard probe is non-exact (drops from concrete)."""
    assert is_wildcard_value(probe) is True
    scope = clean_scope(strategy=probe)
    assert ScopeDimension.STRATEGY in scope.wildcard_dimensions()
    assert ScopeDimension.STRATEGY not in scope.concrete_dimensions()
    assert scope.concrete_dimensions() != MANDATED_SCOPE_FLOOR


@given(probe=st.sampled_from(_CONCRETE_PROBES))
def test_concrete_probes_stay_concrete(probe: str) -> None:
    """(§5.1 — #25 MAJOR-1 regression guard) A normal concrete value is NOT flagged as a wildcard."""
    assert is_wildcard_value(probe) is False
    scope = clean_scope(strategy=probe)
    assert ScopeDimension.STRATEGY in scope.concrete_dimensions()
    assert ScopeDimension.STRATEGY not in scope.wildcard_dimensions()
    # a fully concrete scope whose one probed dimension is also concrete stays complete.
    assert scope.concrete_dimensions() == MANDATED_SCOPE_FLOOR


def test_metacharacter_scope_eligible_plan_is_unconstructable() -> None:
    """(§2.3 / #25 MAJOR-1) An ELIGIBLE plan with a "*.KOSPI" wildcard strategy scope is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_plan(scope=clean_scope(strategy="*.KOSPI"))


def test_metacharacter_baseline_denies() -> None:
    """(§5.1 point 5 / #25 MAJOR-1) A metacharacter baseline digest is non-exact ⇒ deny (predicate layer)."""
    plan = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=clean_scope(),
        baseline_digests=("KOSPI*",),
        pre_registered=True,
        independently_reviewed=True,
    )
    assert (
        plan_scope_exact_and_complete(plan, clean_policy(), MANDATED_SCOPE_FLOOR)
        is False
    )


def test_missing_or_wildcard_baseline_denies() -> None:
    """(§5.1 point 5 / §9 line 263) An empty / wildcard baseline denies."""
    empty_baseline = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=clean_scope(),
        baseline_digests=(),
        pre_registered=True,
        independently_reviewed=True,
    )
    wildcard_baseline = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=clean_scope(),
        baseline_digests=("latest",),
        pre_registered=True,
        independently_reviewed=True,
    )
    policy = clean_policy()
    assert (
        plan_scope_exact_and_complete(empty_baseline, policy, MANDATED_SCOPE_FLOOR)
        is False
    )
    assert (
        plan_scope_exact_and_complete(wildcard_baseline, policy, MANDATED_SCOPE_FLOOR)
        is False
    )


# --- polarity: pre_registered / independently_reviewed ----------------------


@given(pre_registered=TRIBOOL, reviewed=TRIBOOL)
def test_pre_registered_and_reviewed_positive_polarity(
    pre_registered: bool | None, reviewed: bool | None
) -> None:
    """(§5.1 point 6 / §4.3) Only both ``is True`` pass; any None / False denies (positive polarity).

    Constructed via ``model_construct`` so the ``None`` / ``False`` cases are reachable (an eligible
    plan is otherwise built with True fixtures).
    """
    plan = ExactTrialPlan.model_construct(
        plan_id="p",
        result=PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION,
        trial_scope=clean_scope(),
        baseline_digests=("b1",),
        pre_registered=pre_registered,
        independently_reviewed=reviewed,
    )
    expected = pre_registered is True and reviewed is True
    assert (
        plan_scope_exact_and_complete(plan, clean_policy(), MANDATED_SCOPE_FLOOR)
        is expected
    )


def test_non_eligible_result_denies() -> None:
    """(§5.1 point 2 / §4.2) INELIGIBLE / HOLD deny (only ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION)."""
    for result in (PlanResult.INELIGIBLE, PlanResult.HOLD):
        plan = clean_plan(result=result)
        assert plan_result_admissible(plan) is False
        assert (
            plan_scope_exact_and_complete(plan, clean_policy(), MANDATED_SCOPE_FLOOR)
            is False
        )
    # and the sole eligible value is admissible.
    assert plan_result_admissible(clean_plan()) is True


def test_coexistence_seal_blocks_eligible_plan_with_incomplete_scope() -> None:
    """(§2.3 coexistence 1-of-3) An eligible plan with an incomplete scope is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_plan(scope=clean_scope(broker=None))


def test_coexistence_seal_blocks_eligible_plan_with_wildcard_scope() -> None:
    """(§2.3 / RLP-INV-002:154) An eligible plan with a wildcard scope dimension is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_plan(scope=clean_scope(venue="*"))


def test_coexistence_seal_blocks_eligible_plan_with_missing_baseline() -> None:
    """(§2.3) An eligible plan with no baseline digests is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        clean_plan(baseline_digests=())


def test_coexistence_seal_allows_non_eligible_incomplete_plan() -> None:
    """(§2.3) A non-eligible (INELIGIBLE) plan with an incomplete scope IS constructable (seal off)."""
    plan = clean_plan(
        scope=clean_scope(broker=None),
        result=PlanResult.INELIGIBLE,
        pre_registered=False,
        independently_reviewed=False,
    )
    assert plan.result is PlanResult.INELIGIBLE
