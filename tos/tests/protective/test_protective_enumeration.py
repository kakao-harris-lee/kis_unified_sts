"""Central completeness invariants (design #11 §4.1/§4.2/§5.1/§5.2 — PRD-EV-001/002 substrate).

The two central completeness predicates, both-ways + drop-one + the empty-collection
fail-closed hunt (the #10 code-review empty-collection MAJOR lesson): an unenumerated domain
resolves ``UNAVAILABLE`` and makes enumeration incomplete; an unassigned guarantee resolves to
the lowest and makes assignment incomplete; ``PRIORITIZED_ONLY`` is never reserved; a claimed
reserved level without evidence is downgraded. None of these tests claims PRD-EV closure
(``/3`` / ``+Broker`` remain; design #11 §1).
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given
from tos.protective import (
    GuaranteeLevel,
    ProtectiveResourceDomain,
    domain_enumeration_complete,
    guarantee_assignment_complete,
    guarantee_level_resolved,
    is_reserved_guarantee,
)

from ._protective_strategies import (
    NON_RESERVED_LEVELS,
    drop_domain,
    issue_profile,
    reserved_declaration,
)

# ---------------------------------------------------------------------------
# §5.1 domain_enumeration_complete (PRD-EV-001 substrate)
# ---------------------------------------------------------------------------


def test_all_seven_declared_is_complete() -> None:
    """(§5.1 canary b) All 7 required domains declared => complete (positive side)."""
    assert domain_enumeration_complete(issue_profile()) is True


@pytest.mark.parametrize("dropped", list(ProtectiveResourceDomain))
def test_drop_one_domain_is_incomplete(dropped: ProtectiveResourceDomain) -> None:
    """(§5.1 canary a / drop-one) Dropping any one required domain => incomplete."""
    profile = issue_profile(declarations=drop_domain(dropped))
    assert domain_enumeration_complete(profile) is False
    # ... and the dropped domain resolves to UNAVAILABLE (§4.2 most-restrictive).
    assert guarantee_level_resolved(dropped, profile) is GuaranteeLevel.UNAVAILABLE


def test_empty_declarations_is_incomplete_not_vacuous() -> None:
    """(∅ fail-closed) Empty declarations + non-empty required => False (no vacuous True)."""
    profile = issue_profile(declarations=())
    assert domain_enumeration_complete(profile) is False


def test_empty_required_is_floored_to_seven_not_vacuous() -> None:
    """(∅ fail-closed / §5.1) An explicitly EMPTY required set is the 7-domain floor, not vacuous."""
    # Empty required against an empty profile must NOT vacuously pass.
    assert (
        domain_enumeration_complete(issue_profile(declarations=()), frozenset())
        is False
    )
    # Empty required against a fully-declared profile is the floor => complete.
    assert domain_enumeration_complete(issue_profile(), frozenset()) is True


def test_none_required_floored_to_seven() -> None:
    """(§5.1) A None required set is the 7-domain floor (fail-closed)."""
    assert domain_enumeration_complete(issue_profile(), None) is True
    assert domain_enumeration_complete(issue_profile(declarations=()), None) is False


def test_none_profile_incomplete() -> None:
    """(§5.1) A None profile => incomplete (fail-closed)."""
    assert domain_enumeration_complete(None) is False


def test_widened_required_beyond_declared_is_incomplete() -> None:
    """(§5.1 rule 3) A required set widened past the declared floor => incomplete."""
    # A profile declaring only one domain, but a required set of two.
    only_one = issue_profile(
        declarations=(
            reserved_declaration(
                domain=ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH
            ),
        )
    )
    required = frozenset(
        {
            ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH,
            ProtectiveResourceDomain.NETWORK_AND_CONTROL_PATH,
        }
    )
    assert domain_enumeration_complete(only_one, required) is False


# ---------------------------------------------------------------------------
# §5.2 guarantee_level_resolved / is_reserved_guarantee (PRD-EV-002 substrate)
# ---------------------------------------------------------------------------


def test_unassigned_resolves_unavailable() -> None:
    """(§5.2 canary a) A declaration with a None level resolves UNAVAILABLE."""
    profile = issue_profile(
        declarations=(
            reserved_declaration(
                domain=ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH,
                guarantee_level=None,
            ),
        )
    )
    assert (
        guarantee_level_resolved(
            ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH, profile
        )
        is GuaranteeLevel.UNAVAILABLE
    )


def test_physically_reserved_with_evidence_is_reserved() -> None:
    """(§5.2 canary b) PHYSICALLY_RESERVED + both evidence flags => reserved (positive side)."""
    decl = reserved_declaration(guarantee_level=GuaranteeLevel.PHYSICALLY_RESERVED)
    assert is_reserved_guarantee(decl) is True


def test_physically_reserved_without_failure_independence_downgrades() -> None:
    """(§5.2 / §4.2 line 217) PHYSICALLY_RESERVED without evidence is downgraded / not reserved."""
    decl = reserved_declaration(
        guarantee_level=GuaranteeLevel.PHYSICALLY_RESERVED,
        failure_independence_evidenced=None,
    )
    assert is_reserved_guarantee(decl) is False
    profile = issue_profile(declarations=(decl, *drop_domain(decl.domain)))
    # resolved is downgraded to PRIORITIZED_ONLY (a claim never outranks its evidence).
    assert (
        guarantee_level_resolved(decl.domain, profile)
        is GuaranteeLevel.PRIORITIZED_ONLY
    )


def test_logically_reserved_requires_common_mode_note() -> None:
    """(§12.4 line 547) LOGICALLY_RESERVED is reserved only with a common-mode note."""
    with_note = reserved_declaration(guarantee_level=GuaranteeLevel.LOGICALLY_RESERVED)
    assert is_reserved_guarantee(with_note) is True
    without_note = reserved_declaration(
        guarantee_level=GuaranteeLevel.LOGICALLY_RESERVED, common_mode_note=None
    )
    assert is_reserved_guarantee(without_note) is False


@given(level=NON_RESERVED_LEVELS)
def test_prioritized_best_effort_unavailable_never_reserved(
    level: GuaranteeLevel,
) -> None:
    """(§3.1.4 line 144) PRIORITIZED_ONLY / BEST_EFFORT / UNAVAILABLE are never reserved."""
    decl = reserved_declaration(guarantee_level=level)
    assert is_reserved_guarantee(decl) is False


def test_none_declaration_not_reserved() -> None:
    """(∅ fail-closed) is_reserved_guarantee(None) => False."""
    assert is_reserved_guarantee(None) is False


# ---------------------------------------------------------------------------
# guarantee_assignment_complete
# ---------------------------------------------------------------------------


def test_all_evidenced_levels_is_complete() -> None:
    """(§5.2 canary b) Every domain evidenced-level assigned => complete (positive side)."""
    assert guarantee_assignment_complete(issue_profile()) is True


def test_explicit_unavailable_counts_as_assigned() -> None:
    """(§5.2) An explicit UNAVAILABLE is an evidenced assignment (not implicit)."""
    decls = tuple(
        (
            reserved_declaration(domain=d, guarantee_level=GuaranteeLevel.UNAVAILABLE)
            if d is ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH
            else reserved_declaration(domain=d)
        )
        for d in ProtectiveResourceDomain
    )
    # enumeration is complete (all declared), and an explicit level (even UNAVAILABLE) counts.
    assert guarantee_assignment_complete(issue_profile(declarations=decls)) is True


def test_implicit_unassigned_is_incomplete() -> None:
    """(§5.2 canary a) A declared domain with a None level (implicit UNAVAILABLE) => incomplete."""
    decls = tuple(
        (
            reserved_declaration(domain=d, guarantee_level=None)
            if d is ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH
            else reserved_declaration(domain=d)
        )
        for d in ProtectiveResourceDomain
    )
    assert guarantee_assignment_complete(issue_profile(declarations=decls)) is False


def test_assignment_incomplete_when_enumeration_incomplete() -> None:
    """(§5.2) Assignment completeness requires enumeration completeness first."""
    profile = issue_profile(
        declarations=drop_domain(ProtectiveResourceDomain.NETWORK_AND_CONTROL_PATH)
    )
    assert guarantee_assignment_complete(profile) is False


def test_assignment_empty_declarations_incomplete() -> None:
    """(∅ fail-closed) Empty declarations => assignment incomplete (no vacuous pass)."""
    assert guarantee_assignment_complete(issue_profile(declarations=())) is False


@given(level=st.sampled_from(list(GuaranteeLevel)))
def test_resolved_is_total_and_matches_evidenced_level(level: GuaranteeLevel) -> None:
    """guarantee_level_resolved is total and, with full evidence, equals the declared level."""
    # reserved_declaration supplies both evidence flags (+ common-mode note), so every level
    # is demonstrated and resolves unchanged — never a silent downgrade of an evidenced level.
    profile = issue_profile(
        declarations=(
            reserved_declaration(
                domain=ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH,
                guarantee_level=level,
            ),
        )
    )
    resolved = guarantee_level_resolved(
        ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH, profile
    )
    assert isinstance(resolved, GuaranteeLevel)
    assert resolved is level
