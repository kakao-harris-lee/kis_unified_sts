"""The vector_complete yolk + the DimensionKey enum-drift seal (design #23 §5.1/§7.2).

``vector_complete`` (CUR-EV-001 substrate) is the aggregator's own axis: every mandated dimension
present + positively established + one revision + policy complete + no placeholder. The failures it
catches — an unrepresented dimension (§5.1-3), a mixed revision (§5.3), a policy under-declaration
(§5.5) — are each **undetectable by any per-decision leaf** (§0.4b), so this is **not** a leaf-AND.
The ∅-seal is both-ways (a genuinely complete vector passes; an absent policy / required set /
dimension set fails). The **enum-drift property** asserts ``DimensionKey`` == the ADR §9-derived
reference set (CONTEXT included) — had this regression existed at authoring time, the v1.1 MAJOR-2
CONTEXT omission would have been caught immediately (§7.2).

Regime tag: completeness predicate substrate only; CUR-EV-001 NOT_IMPLEMENTED (``EV-L1/3`` — ``/3``
integration / adversarial pending); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.cur import (
    CONDITIONAL_DIMENSION_KEYS,
    MANDATED_DIMENSION_FLOOR,
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
)

#: The ADR §9-derived reference dimension catalogue (design #23 §2.2 verbatim; CONTEXT included as a
#: SEPARATE dimension from CRITICAL_INPUT — the v1.1 MAJOR-2 anchor). Any enum drift below / away
#: from this fixed set fails the property, so the enum can never silently regress off the ADR.
# HONESTY NOTE (code-review MINOR-1): this is a MANUALLY-TRANSCRIBED regression anchor,
# not a parsed derivation of ADR SS9 - it prevents single-sided enum edits (changing
# DimensionKey without consciously updating this set), but a coordinated two-sided edit
# or an ADR SS9 text change is NOT detected here; the design doc SS7.2 3-source check
# (SS2.2 enum <-> SS2.4 prose <-> ADR SS9) remains the human-review obligation.
_ADR_S9_NON_CONDITIONAL = frozenset(
    {
        "ENVIRONMENT_SCOPE",
        "CURRENTNESS_POLICY",
        "COMMIT_LOG",
        "SAFETY_AUTHORITY",
        "SAFETY_ENVELOPE_PROFILE",
        "DEVIATION",
        "INCIDENT",
        "MONITORING",
        "RELEASE",
        "POST_TRADE",
        "TRUSTWORTHY_TIME",
        "RECOVERY",
        "CRITICAL_INPUT",
        "CONTEXT",  # v1.1 MAJOR-2: a SEPARATE dimension from CRITICAL_INPUT (ADR §9:259)
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


# ---------------------------------------------------------------------------
# DimensionKey enum-drift seal (§7.2 — the v1.1 MAJOR-2 catch)
# ---------------------------------------------------------------------------


def test_dimension_key_matches_the_adr_s9_derived_set() -> None:
    """(§7.2) DimensionKey == the ADR §9-derived reference set — no drift, CONTEXT included."""
    members = {key.value for key in DimensionKey}
    assert members == _ADR_S9_NON_CONDITIONAL | _ADR_S9_CONDITIONAL


def test_context_is_a_separate_mandated_dimension_from_critical_input() -> None:
    """(§7.2 / v1.1 MAJOR-2) CONTEXT and CRITICAL_INPUT are BOTH separate mandated dimensions."""
    assert DimensionKey.CONTEXT in MANDATED_DIMENSION_FLOOR
    assert DimensionKey.CRITICAL_INPUT in MANDATED_DIMENSION_FLOOR
    assert DimensionKey.CONTEXT is not DimensionKey.CRITICAL_INPUT


def test_mandated_floor_is_every_non_conditional_member() -> None:
    """(§5.1) The mandated floor == all non-conditional members; the only exclusion is conditional."""
    assert {k.value for k in MANDATED_DIMENSION_FLOOR} == _ADR_S9_NON_CONDITIONAL
    assert {DimensionKey.RESTRICTED_LIVE_TRIAL} == CONDITIONAL_DIMENSION_KEYS
    assert MANDATED_DIMENSION_FLOOR.isdisjoint(CONDITIONAL_DIMENSION_KEYS)


# ---------------------------------------------------------------------------
# vector_complete — the yolk (§5.1)
# ---------------------------------------------------------------------------


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
        if key
        is not DimensionKey.CONTEXT  # drop CONTEXT specifically (the MAJOR-2 case)
    )
    vec = clean_vector(revision=rev, dimensions=missing_one)
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_dimension_present_but_not_established_is_incomplete() -> None:
    """(§5.2) A dimension present but positively_established is not True ⇒ incomplete."""
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    # Flip ONE dimension to not-established (None).
    dims[0] = clean_dimension(
        dimension_key=dims[0].dimension_key,
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
    dims[-1] = clean_dimension(dimension_key=dims[-1].dimension_key, revision=rev_b)
    vec = clean_vector(revision=rev_a, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_forbidden_placeholder_is_incomplete() -> None:
    """(§5.4) A dimension using a `latest` / wildcard sentinel ⇒ incomplete."""
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    dims[0] = clean_dimension(
        dimension_key=dims[0].dimension_key,
        revision=rev,
        bound_digest="latest",  # forbidden sentinel (§9 line 266)
    )
    vec = clean_vector(revision=rev, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False


def test_policy_under_declaration_is_incomplete() -> None:
    """(§5.5 / §0.4b) A policy that omits a mandated dimension ⇒ incomplete (aggregate-only axis)."""
    under = MANDATED_DIMENSION_FLOOR - {DimensionKey.CONTEXT}
    under_policy = clean_policy(required_dimensions=under)
    assert (
        vector_complete(clean_vector(), under_policy, MANDATED_DIMENSION_FLOOR) is False
    )


def test_caller_cannot_narrow_the_mandated_floor() -> None:
    """(§5.1 v1.1 MINOR-1) A caller passing a narrower mandate cannot weaken the §9 floor.

    Even if the caller passes an empty / narrow ``mandated``, the floor is applied — a policy that
    under-declares the full §9 floor is still rejected (the caller-narrowing attack is neutralized).
    """
    under = MANDATED_DIMENSION_FLOOR - {DimensionKey.CONTEXT}
    under_policy = clean_policy(required_dimensions=under)
    # Caller tries to narrow the mandate to nothing — the floor still requires CONTEXT.
    assert vector_complete(clean_vector(), under_policy, frozenset()) is False
    # A complete vector + full policy still passes even with a narrow caller mandate (both-ways).
    assert vector_complete(clean_vector(), clean_policy(), frozenset()) is True


# ---------------------------------------------------------------------------
# supporting predicates
# ---------------------------------------------------------------------------


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
    dims[0] = clean_dimension(dimension_key=dims[0].dimension_key, revision=rev_b)
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
        required_dimensions=MANDATED_DIMENSION_FLOOR - {DimensionKey.CONTEXT}
    )
    assert policy_covers_mandated_dimensions(under, MANDATED_DIMENSION_FLOOR) is False


def test_no_forbidden_placeholder_both_ways() -> None:
    """(§5.4) A clean vector passes; a sentinel-bearing dimension fails; None fails."""
    assert no_forbidden_placeholder(clean_vector()) is True
    assert no_forbidden_placeholder(None) is False
    rev = clean_revision()
    dims = list(clean_dimensions(revision=rev))
    dims[0] = clean_dimension(
        dimension_key=dims[0].dimension_key, revision=rev, bound_digest="*"
    )
    assert (
        no_forbidden_placeholder(clean_vector(revision=rev, dimensions=tuple(dims)))
        is False
    )


# ---------------------------------------------------------------------------
# property — dropping any single mandated dimension always denies (§5.1 exhaustive)
# ---------------------------------------------------------------------------


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
    dims[-1] = clean_dimension(dimension_key=dims[-1].dimension_key, revision=rev_b)
    vec = clean_vector(revision=rev_a, dimensions=tuple(dims))
    assert vector_complete(vec, clean_policy(), MANDATED_DIMENSION_FLOOR) is False
