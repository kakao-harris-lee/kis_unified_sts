"""Central capability_admissible fail-closed + status gate (design #10 §5.1; BC-EV-001).

The middle of the contract (ADR §1 line 32): missing / unknown / contradictory / expired /
unsupported / undeclared => reduce or prohibit, never a vacuous ADMISSIBLE. Both-ways
canaries + a drop-one over the non-authorizing statuses, plus the §10 line 584 canary that a
conformance class cannot override a failed mandatory dimension.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.brokercap import (
    Admissibility,
    AssuranceLevel,
    CapabilityDeclaration,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    RequiredCapabilitySet,
    broker_capability_added,
    broker_capability_sufficient,
    capability_admissible,
)

from ._brokercap_strategies import (
    LEVELS,
    issue_profile,
    required_set,
    verified_declaration,
)

_OID = CapabilityDimension.ORDER_IDENTITY
_L3 = AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION


# ---------------------------------------------------------------------------
# Positive side (both-ways canary a)
# ---------------------------------------------------------------------------


def test_all_verified_is_admissible() -> None:
    """(§5.1 canary b) Required dim VERIFIED ∧ level ∧ current ∧ gate => ADMISSIBLE."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    verdict = capability_admissible(
        profile, "entry", required_set(), version_current=True
    )
    assert verdict is Admissibility.ADMISSIBLE
    assert broker_capability_sufficient(profile, required_set(), version_current=True)


# ---------------------------------------------------------------------------
# Fail-closed side (both-ways canary a): undeclared / unknown / status / level / version
# ---------------------------------------------------------------------------


def test_undeclared_dimension_is_prohibited() -> None:
    """(§5.1 / BC-INV-001) A required-but-undeclared dimension => PROHIBITED (not-present=unavailable)."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    req = required_set(dimensions=frozenset({CapabilityDimension.CANCELLATION}))
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.PROHIBITED
    )


@pytest.mark.parametrize(
    "status",
    [
        CapabilityStatus.DOCUMENTED_NOT_VERIFIED,
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.CONTRADICTORY,
        CapabilityStatus.UNKNOWN,
        CapabilityStatus.EXPIRED,
    ],
)
def test_non_authorizing_status_is_prohibited(status: CapabilityStatus) -> None:
    """(§5.3 line 146) Each of the 5 non-authorizing statuses => PROHIBITED (drop-one)."""
    decl = CapabilityDeclaration(
        dimension=_OID, status=status, assurance_level=_L3, evidence_reference="ev"
    )
    profile = issue_profile(declarations=(decl,))
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=True)
        is Admissibility.PROHIBITED
    )


def test_unapproved_restriction_is_prohibited() -> None:
    """(§5.1) VERIFIED_WITH_RESTRICTION without an explicit approval => PROHIBITED."""
    decl = CapabilityDeclaration(
        dimension=_OID,
        status=CapabilityStatus.VERIFIED_WITH_RESTRICTION,
        assurance_level=_L3,
        evidence_reference="ev",
        restriction="serialized-only",
        restriction_approved=None,  # not approved => fail-closed
    )
    profile = issue_profile(declarations=(decl,))
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=True)
        is Admissibility.PROHIBITED
    )


def test_approved_restriction_authorizes() -> None:
    """(§5.3 line 146) An explicitly approved VERIFIED_WITH_RESTRICTION authorizes."""
    decl = CapabilityDeclaration(
        dimension=_OID,
        status=CapabilityStatus.VERIFIED_WITH_RESTRICTION,
        assurance_level=_L3,
        evidence_reference="ev",
        restriction="serialized-only",
        restriction_approved=True,
    )
    profile = issue_profile(declarations=(decl,))
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=True)
        is Admissibility.ADMISSIBLE
    )


def test_under_level_is_prohibited() -> None:
    """(§9 line 540) A declared level below the required level => PROHIBITED."""
    decl = verified_declaration(
        dimension=_OID, level=AssuranceLevel.LEVEL_2_CONTROLLED_TEST_VERIFIED
    )
    profile = issue_profile(declarations=(decl,))
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=True)
        is Admissibility.PROHIBITED
    )


def test_unspecified_required_level_fails_closed() -> None:
    """(§5.1) An unspecified required level => PROHIBITED (highest requirement)."""
    profile = issue_profile()
    req = RequiredCapabilitySet(
        required_dimensions=frozenset({_OID}),
        required_level=None,
        minimum_live_gate_satisfied=True,
    )
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.PROHIBITED
    )


def test_minimum_live_gate_unmet_is_prohibited() -> None:
    """(§11 line 607) An unmet minimum-live gate => PROHIBITED (CLASS-D scope)."""
    profile = issue_profile()
    req = required_set(minimum_live_gate_satisfied=None)
    assert (
        capability_admissible(profile, "entry", req, version_current=True)
        is Admissibility.PROHIBITED
    )


def test_version_not_current_is_prohibited() -> None:
    """(§6.1) version_current None / False => PROHIBITED (fail-closed)."""
    profile = issue_profile()
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=None)
        is Admissibility.PROHIBITED
    )
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=False)
        is Admissibility.PROHIBITED
    )


def test_none_profile_or_required_is_prohibited() -> None:
    """(§5.1) A None profile or None required => PROHIBITED (no permissive fallthrough)."""
    assert (
        capability_admissible(None, "entry", required_set(), version_current=True)
        is Admissibility.PROHIBITED
    )
    assert (
        capability_admissible(issue_profile(), "entry", None, version_current=True)
        is Admissibility.PROHIBITED
    )


# ---------------------------------------------------------------------------
# Conformance class cannot override a failed mandatory dimension (§10 line 584)
# ---------------------------------------------------------------------------


def test_class_a_cannot_override_unsupported_dimension() -> None:
    """(§10 line 584) CLASS_A with a mandatory dimension UNSUPPORTED => still PROHIBITED."""
    decl = CapabilityDeclaration(
        dimension=_OID,
        status=CapabilityStatus.UNSUPPORTED,
        assurance_level=_L3,
        evidence_reference="ev",
    )
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE,
        declarations=(decl,),
    )
    assert (
        capability_admissible(profile, "entry", required_set(), version_current=True)
        is Admissibility.PROHIBITED
    )


# ---------------------------------------------------------------------------
# broker_capability_added (§14.1 expansion)
# ---------------------------------------------------------------------------


def test_broker_capability_added_positive() -> None:
    """(§5.2) Delta fully VERIFIED ∧ envelope not expanded ∧ current => True."""
    profile = issue_profile()
    assert broker_capability_added(
        profile, required_set(), version_current=True, envelope_not_expanded=True
    )


def test_broker_capability_added_envelope_expanded_fails_closed() -> None:
    """(§5.2) An expanded envelope => False even with a fully covered delta."""
    profile = issue_profile()
    assert not broker_capability_added(
        profile, required_set(), version_current=True, envelope_not_expanded=None
    )


def test_broker_capability_added_deficient_delta_fails_closed() -> None:
    """(§5.2) A deficient delta dimension => False."""
    profile = issue_profile()
    req = required_set(dimensions=frozenset({CapabilityDimension.REDUCE_ONLY}))
    assert not broker_capability_added(
        profile, req, version_current=True, envelope_not_expanded=True
    )


# ---------------------------------------------------------------------------
# Property: no injected combination yields a vacuous ADMISSIBLE when a required
# dimension is undeclared (structural fail-closed).
# ---------------------------------------------------------------------------


@given(
    level=LEVELS,
    version_current=st.sampled_from([True, False, None]),
    gate=st.sampled_from([True, False, None]),
)
def test_undeclared_never_admissible(
    level: AssuranceLevel, version_current: bool | None, gate: bool | None
) -> None:
    """No injected level / version / gate lifts an undeclared required dimension to ADMISSIBLE."""
    profile = issue_profile(declarations=())  # nothing declared
    req = RequiredCapabilitySet(
        required_dimensions=frozenset({_OID}),
        required_level=level,
        minimum_live_gate_satisfied=gate,
    )
    verdict = capability_admissible(
        profile, "entry", req, version_current=version_current
    )
    assert verdict is not Admissibility.ADMISSIBLE


# ---------------------------------------------------------------------------
# §5.1 unspecified-required doctrine: an EMPTY required_dimensions set is
# fail-closed (treated as all 17 dimensions at the highest level), never a
# vacuous ADMISSIBLE from a zero-iteration loop (code-review MAJOR regression).
# ---------------------------------------------------------------------------


def _all_dimensions_declared(
    level: AssuranceLevel,
) -> tuple[CapabilityDeclaration, ...]:
    """A declaration for every one of the 17 dimensions, VERIFIED at ``level``."""
    return tuple(
        CapabilityDeclaration(
            dimension=dimension,
            status=CapabilityStatus.VERIFIED,
            assurance_level=level,
            evidence_reference="ev",
        )
        for dimension in CapabilityDimension
    )


def _empty_required(**overrides: object) -> RequiredCapabilitySet:
    base = {
        "required_dimensions": frozenset(),  # explicitly empty = unspecified
        "required_level": None,
        "minimum_live_gate_satisfied": True,
    }
    base.update(overrides)
    return RequiredCapabilitySet(**base)  # type: ignore[arg-type]


def test_empty_required_no_declarations_is_prohibited() -> None:
    """(§5.1 MAJOR) Empty required + a declaration-less profile + all positive injections => PROHIBITED.

    The pre-fix zero-iteration loop returned a vacuous ADMISSIBLE here; the doctrine
    substitution (empty => all 17 dimensions at the highest level) forecloses it.
    """
    profile = issue_profile(declarations=())
    assert (
        capability_admissible(profile, "entry", _empty_required(), version_current=True)
        is Admissibility.PROHIBITED
    )


def test_empty_required_sufficient_is_false() -> None:
    """(§5.1 MAJOR) broker_capability_sufficient with an empty required + no declarations => False."""
    profile = issue_profile(declarations=())
    assert (
        broker_capability_sufficient(profile, _empty_required(), version_current=True)
        is False
    )


def test_empty_required_partial_coverage_is_prohibited() -> None:
    """(§5.1 MAJOR) Empty required + only some dimensions VERIFIED => PROHIBITED (needs all 17)."""
    partial = _all_dimensions_declared(AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED)[
        :5
    ]
    profile = issue_profile(declarations=partial)
    assert (
        capability_admissible(profile, "entry", _empty_required(), version_current=True)
        is Admissibility.PROHIBITED
    )


def test_empty_required_all_seventeen_verified_top_level_is_admissible() -> None:
    """(§5.1 MAJOR positive side) Empty required + all 17 VERIFIED at LEVEL_4 + current => ADMISSIBLE.

    The doctrine substitution (all dimensions at the highest level) does not block a genuinely
    complete profile — both-ways is preserved.
    """
    profile = issue_profile(
        declarations=_all_dimensions_declared(
            AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED
        )
    )
    assert (
        capability_admissible(profile, "entry", _empty_required(), version_current=True)
        is Admissibility.ADMISSIBLE
    )


def test_empty_required_all_seventeen_below_top_level_is_prohibited() -> None:
    """(§5.1) Empty required + all 17 VERIFIED but only at LEVEL_3 => PROHIBITED (doctrine wants highest)."""
    profile = issue_profile(
        declarations=_all_dimensions_declared(
            AssuranceLevel.LEVEL_3_RESTRICTED_PRODUCTION
        )
    )
    assert (
        capability_admissible(profile, "entry", _empty_required(), version_current=True)
        is Admissibility.PROHIBITED
    )
