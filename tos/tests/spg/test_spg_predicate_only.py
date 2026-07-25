"""Predicate-only substrate: rollback / break-glass / compat / bundle-complete (§6; SPG-EV-007/009/010/011).

These predicates author L1-decidable substrate for register-minimum EV-L2+ items; Phase 1
closes NO EV. Both-ways canaries + the ∅-void hunt (empty required-members => all needed;
empty manifest => vacuous non-match).
"""

from __future__ import annotations

from tos.spg import (
    BreakGlassAction,
    BundleMemberKind,
    break_glass_confined,
    bundle_complete,
    compatibility_manifest_matches,
    missing_config_denies,
    rollback_requires_new_generation,
    rollback_revives_nothing,
)

from ._spg_strategies import (
    all_members,
    compat_query,
    issue_bundle,
    issue_complete_bundle,
    issue_manifest,
    lawful_rollback_inputs,
)

# ---------------------------------------------------------------------------
# §6.1 rollback = new proposal
# ---------------------------------------------------------------------------


def test_lawful_rollback_positive_side() -> None:
    """(canary + §17) A new generation + current validation + approval + re-arm => True."""
    assert rollback_requires_new_generation(lawful_rollback_inputs()) is True


def test_each_missing_rollback_precondition_fails() -> None:
    """(canary - §17 line 452) Reusing an old artifact without any precondition => False."""
    for field in (
        "new_generation_issued",
        "current_schema_valid",
        "current_approval",
        "break_before_make",
        "fresh_rearm",
    ):
        assert (
            rollback_requires_new_generation(lawful_rollback_inputs(**{field: None}))
            is False
        )


def test_rollback_revives_nothing() -> None:
    """(§17 line 452) Rollback revives no old generation / approval — unconditionally True."""
    assert rollback_revives_nothing() is True


# ---------------------------------------------------------------------------
# §6.2 break-glass directional confinement
# ---------------------------------------------------------------------------


def test_break_glass_allows_halt_and_restrictive() -> None:
    """(canary + §8 line 251) HALT / RESTRICTIVE_OVERRIDE are confined-admissible."""
    assert break_glass_confined(BreakGlassAction.HALT) is True
    assert break_glass_confined(BreakGlassAction.RESTRICTIVE_OVERRIDE) is True


def test_break_glass_forbids_expansion_and_rearm() -> None:
    """(canary - §8 line 251) Expand / activate / waive / re-arm are prohibited."""
    for action in (
        BreakGlassAction.EXPAND_ENVELOPE,
        BreakGlassAction.EXPAND_PROFILE,
        BreakGlassAction.WAIVE_VALIDATION,
        BreakGlassAction.ACTIVATE_GENERATION,
        BreakGlassAction.RE_ARM,
    ):
        assert break_glass_confined(action) is False


def test_break_glass_none_fails_closed() -> None:
    """(fail-closed) A None action is not confined-admissible."""
    assert break_glass_confined(None) is False


# ---------------------------------------------------------------------------
# §6.3 consumer compatibility manifest match
# ---------------------------------------------------------------------------


def test_compatibility_exact_match() -> None:
    """(canary +) A manifest declaring the required surface matches."""
    assert compatibility_manifest_matches(issue_manifest(), compat_query()) is True


def test_compatibility_missing_field_denies() -> None:
    """(canary - §16 line 442) A consumer missing a required field is incompatible."""
    query = compat_query(required_fields=("f1", "f2"))  # f2 not declared
    assert compatibility_manifest_matches(issue_manifest(), query) is False


def test_empty_manifest_is_vacuous_non_match() -> None:
    """(∅-seal §6.3) An empty manifest declares nothing => denial (never vacuous match)."""
    empty = issue_manifest(declared_schemas=(), declared_fields=())
    # An empty query would trivially be a subset; the empty-manifest guard must still deny.
    from tos.spg import CompatibilityQuery

    assert compatibility_manifest_matches(empty, CompatibilityQuery()) is False


def test_compatibility_none_fails_closed() -> None:
    """(fail-closed) A None manifest or None query is a non-match."""
    assert compatibility_manifest_matches(None, compat_query()) is False
    assert compatibility_manifest_matches(issue_manifest(), None) is False


# ---------------------------------------------------------------------------
# §6.4 bundle completeness / missing-config containment
# ---------------------------------------------------------------------------


def test_complete_bundle_positive_side() -> None:
    """(canary +) A bundle with all 29 modeled members present/resolved/immutable is complete."""
    assert bundle_complete(issue_complete_bundle()) is True
    assert missing_config_denies(issue_complete_bundle()) is False


def test_empty_required_members_means_all_needed() -> None:
    """(∅-seal §6.4) An empty required set is treated as ALL 29 — an under-filled bundle fails."""
    partial = issue_bundle(members=all_members()[:5])  # only 5 of 29
    assert bundle_complete(partial) is False  # empty required => all 29 needed
    assert missing_config_denies(partial) is True


def test_empty_bundle_members_is_incomplete() -> None:
    """(∅-seal) A bundle with zero members is incomplete (new risk denied)."""
    assert bundle_complete(issue_bundle(members=())) is False
    assert missing_config_denies(issue_bundle(members=())) is True


def test_unresolved_or_mutable_member_fails() -> None:
    """(SPG-INV-002) An unresolved / mutable / unidentified member breaks completeness."""
    from tos.spg import BundleMemberRef

    members = all_members()
    # Corrupt one member: mark it not-resolved.
    corrupted = (
        BundleMemberRef(
            kind=members[0].kind,
            member_id=members[0].member_id,
            resolved=False,
            immutable=True,
        ),
    ) + members[1:]
    bundle = issue_bundle(members=corrupted)
    required = frozenset({members[0].kind})
    assert bundle_complete(bundle, required) is False


def test_missing_specific_required_member_fails() -> None:
    """(fail-closed) Requiring a member absent from the bundle fails closed."""
    bundle = issue_bundle(
        members=(
            next(
                m
                for m in all_members()
                if m.kind is BundleMemberKind.HARD_SAFETY_ENVELOPE
            ),
        )
    )
    # Require a DIFFERENT member that is not present.
    required = frozenset({BundleMemberKind.RUNTIME_SAFETY_PROFILE})
    assert bundle_complete(bundle, required) is False


def test_bundle_complete_none_fails_closed() -> None:
    """(fail-closed) A None bundle is incomplete and denies new risk."""
    assert bundle_complete(None) is False
    assert missing_config_denies(None) is True
