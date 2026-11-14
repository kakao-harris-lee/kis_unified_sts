"""The vector_complete yolk + the DimensionKey enum-drift seal (design #23 §5.1/§7.2)."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.cur import (
    CONDITIONAL_DIMENSION_KEYS,
    MANDATED_DIMENSION_FLOOR,
    RETIRED_DIMENSION_KEYS,
    CurrentnessRevision,
    DimensionKey,
    dimension_positively_established,
    no_forbidden_placeholder,
    policy_covers_mandated_dimensions,
    single_revision_consistent,
    vector_complete,
)

from ._cur_strategies import (
    clean_dimension,
    clean_dimensions,
    clean_policy,
    clean_revision,
    clean_vector,
    dimension_key,
)

_ADR_S9_NON_CONDITIONAL = frozenset(
    {
        "ENVIRONMENT_SCOPE",
        "CURRENTNESS_POLICY",
        "COMMIT_LOG",
        "SAFETY_AUTHORITY",
        "MONITORING",
        "RELEASE",
        "POST_TRADE",
        "TRUSTWORTHY_TIME",
        "RECOVERY",
        "CRITICAL_INPUT",
        "CONTEXT",
        "CONSTRAINT",
        "CONSTRUCTION",
        "TRADING_APPROVAL",
        "AGGREGATE_RISK",
        "ACTION_FLOW",
        "DECISION_PROOF_INTENT",
        "EGRESS_IDENTITY",
    }
)
_ADR_S9_CONDITIONAL = frozenset({"RESTRICTED_LIVE_TRIAL"})
_S2B_RETIRED = frozenset(
    {
        "CRITICAL_INPUT",
        "CONTEXT",
        "CONSTRAINT",
        "CONSTRUCTION",
        "TRADING_APPROVAL",
        "AGGREGATE_RISK",
        "ACTION_FLOW",
        "DECISION_PROOF_INTENT",
        "EGRESS_IDENTITY",
    }
)


def test_dimension_key_matches_the_adr_s9_derived_set() -> None:
    """(§7.2) DimensionKey == the ADR §9-derived reference set — no drift, CONTEXT included."""
    members = {key.value for key in DimensionKey}
    assert members == _ADR_S9_NON_CONDITIONAL | _ADR_S9_CONDITIONAL


def test_retired_dimensions_are_members_outside_the_floor() -> None:
    """(plan S2-b) The nine retired keys stay enum members but leave the mandated floor."""
    assert {k.value for k in RETIRED_DIMENSION_KEYS} == _S2B_RETIRED
    assert MANDATED_DIMENSION_FLOOR.isdisjoint(RETIRED_DIMENSION_KEYS)
    assert len(MANDATED_DIMENSION_FLOOR) == 9


def test_mandated_floor_is_every_non_conditional_non_retired_member() -> None:
    """(§5.1) The mandated floor == all non-conditional, non-retired members."""
    assert {
        k.value for k in MANDATED_DIMENSION_FLOOR
    } == _ADR_S9_NON_CONDITIONAL - _S2B_RETIRED
    assert {DimensionKey.RESTRICTED_LIVE_TRIAL} == CONDITIONAL_DIMENSION_KEYS
    assert MANDATED_DIMENSION_FLOOR.isdisjoint(CONDITIONAL_DIMENSION_KEYS)


def test_clean_vector_is_complete() -> None:
    """(§5.1 both-ways) A genuinely complete vector + matching policy passes."""
    assert (
        vector_complete(clean_vector(), clean_policy(), MANDATED_DIMENSION_FLOOR)
        is True
    )


def test_none_vector_or_policy_is_incomplete() -> None:
    """(§5.1 ∅-seal) A None vector / policy ⇒ incomplete (never vacuously complete)."""
    assert vector_complete(None, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
    assert vector_complete(clean_vector(), None, MANDATED_DIMENSION_FLOOR) is False


def test_empty_required_dimensions_is_incomplete() -> None:
    """(§5.1 ∅-seal both-ways / §8) A policy with ∅ required set ⇒ incomplete ("Unknown ... material")."""
    empty_policy = clean_policy(required_dimensions=frozenset())
    assert (
        vector_complete(clean_vector(), empty_policy, MANDATED_DIMENSION_FLOOR) is False
    )


def test_empty_dimensions_is_incomplete() -> None:
    """(§5.1 ∅-seal) A vector with ∅ dimensions ⇒ incomplete."""
    vec = clean_vector(dimensions=())
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_unrepresented_dimension_is_incomplete() -> None:
    """(§5.1-3 / §0.4b) A vector missing ONE mandated dimension ⇒ incomplete (aggregate-only axis)."""
    rev = clean_revision()
    missing_one = tuple(
        clean_dimension(dimension_key=key, revision=rev)
        for key in sorted(MANDATED_DIMENSION_FLOOR)
        if key is not DimensionKey.RECOVERY
    )
    vec = clean_vector(revision=rev, dimensions=missing_one)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_dimension_present_but_not_established_is_incomplete() -> None:
    """(§5.2) A dimension present but positively_established is not True ⇒ incomplete."""
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    dims[0] = clean_dimension(
        dimension_key=dimension_key(dims[0]),
        revision=rev,
        positively_established=None,
    )
    vec = clean_vector(revision=rev, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_mixed_revision_is_incomplete() -> None:
    """(§5.3 / §0.4b) A vector whose dimensions span two revisions ⇒ incomplete (leaf-undetectable)."""
    rev_a = clean_revision(revision_id="rev-a", commit_index=10)
    rev_b = clean_revision(revision_id="rev-b", commit_index=11)
    dims = list(clean_dimensions(revision=rev_a))
    dims[-1] = clean_dimension(dimension_key=dimension_key(dims[-1]), revision=rev_b)
    vec = clean_vector(revision=rev_a, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_forbidden_placeholder_is_incomplete() -> None:
    """(§5.4) A dimension using a `latest` / wildcard sentinel ⇒ incomplete."""
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    dims[0] = clean_dimension(
        dimension_key=dimension_key(dims[0]),
        revision=rev,
        bound_digest="latest",
    )
    vec = clean_vector(revision=rev, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_policy_under_declaration_is_incomplete() -> None:
    """(§5.5 / §0.4b) A policy that omits a mandated dimension ⇒ incomplete (aggregate-only axis)."""
    under = MANDATED_DIMENSION_FLOOR - {DimensionKey.RECOVERY}
    under_policy = clean_policy(required_dimensions=under)
    assert (
        vector_complete(clean_vector(), under_policy, MANDATED_DIMENSION_FLOOR) is False
    )


def test_caller_cannot_narrow_the_mandated_floor() -> None:
    """(§5.1 v1.1 MINOR-1) A caller passing a narrower mandate cannot weaken the §9 floor."""
    under = MANDATED_DIMENSION_FLOOR - {DimensionKey.RECOVERY}
    under_policy = clean_policy(required_dimensions=under)
    assert vector_complete(clean_vector(), under_policy, frozenset()) is False
    assert vector_complete(clean_vector(), clean_policy(), frozenset()) is True


def test_dimension_positively_established_requires_every_coordinate() -> None:
    """(§5.2) Missing any identity / generation / digest / revision ⇒ not established."""
    rev = clean_revision()
    assert (
        dimension_positively_established(
            clean_dimension(dimension_key=DimensionKey.CONTEXT, revision=rev)
        )
        is True
    )
    assert dimension_positively_established(None) is False
    for bad in (
        clean_dimension(
            dimension_key=DimensionKey.CONTEXT,
            revision=rev,
            positively_established=False,
        ),
        clean_dimension(
            dimension_key=DimensionKey.CONTEXT,
            revision=rev,
            positively_established=None,
        ),
    ):
        assert dimension_positively_established(bad) is False


def test_single_revision_consistent_both_ways() -> None:
    """(§5.3) One revision passes; a None vector / revision or a mixed revision fails."""
    assert single_revision_consistent(clean_vector()) is True
    assert single_revision_consistent(None) is False
    rev_a = clean_revision(revision_id="a", commit_index=1)
    rev_b = clean_revision(revision_id="b", commit_index=2)
    dims = list(clean_dimensions(revision=rev_a))
    dims[0] = clean_dimension(dimension_key=dimension_key(dims[0]), revision=rev_b)
    assert (
        single_revision_consistent(clean_vector(revision=rev_a, dimensions=tuple(dims)))
        is False
    )


def test_policy_covers_mandated_dimensions_both_ways() -> None:
    """(§5.5 set both-ways) required ⊇ mandated passes; under-declaration / ∅ mandate fails."""
    assert (
        policy_covers_mandated_dimensions(clean_policy(), MANDATED_DIMENSION_FLOOR)
        is True
    )
    assert policy_covers_mandated_dimensions(None, MANDATED_DIMENSION_FLOOR) is False
    assert policy_covers_mandated_dimensions(clean_policy(), frozenset()) is False
    under = clean_policy(
        required_dimensions=MANDATED_DIMENSION_FLOOR - {DimensionKey.RECOVERY}
    )
    assert policy_covers_mandated_dimensions(under, MANDATED_DIMENSION_FLOOR) is False


def test_no_forbidden_placeholder_both_ways() -> None:
    """(§5.4) A clean vector passes; a sentinel-bearing dimension fails; None fails."""
    assert no_forbidden_placeholder(clean_vector()) is True
    assert no_forbidden_placeholder(None) is False
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    dims[0] = clean_dimension(
        dimension_key=dimension_key(dims[0]), revision=rev, bound_digest="*"
    )
    assert (
        no_forbidden_placeholder(clean_vector(revision=rev, dimensions=tuple(dims)))
        is False
    )


@given(dropped=st.sampled_from(sorted(MANDATED_DIMENSION_FLOOR)))
def test_dropping_any_mandated_dimension_denies(dropped: DimensionKey) -> None:
    """(§5.1 property) For EVERY mandated dimension, a vector missing it is incomplete."""
    rev = clean_revision()
    dims = tuple(
        clean_dimension(dimension_key=key, revision=rev)
        for key in sorted(MANDATED_DIMENSION_FLOOR)
        if key is not dropped
    )
    vec = clean_vector(revision=rev, dimensions=dims)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


@given(
    revs=st.lists(
        st.builds(
            CurrentnessRevision,
            revision_id=st.sampled_from(["ra", "rb", "rc"]),
            commit_index=st.integers(min_value=1, max_value=3),
        ),
        min_size=2,
        max_size=2,
        unique_by=lambda r: r.revision_id,
    )
)
def test_any_two_distinct_revisions_make_vector_incomplete(revs: list) -> None:
    """(§5.3 property) Any two DISTINCT revisions across dimensions ⇒ incomplete."""
    rev_a, rev_b = revs
    dims = list(clean_dimensions(revision=rev_a))
    dims[-1] = clean_dimension(dimension_key=dimension_key(dims[-1]), revision=rev_b)
    vec = clean_vector(revision=rev_a, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
