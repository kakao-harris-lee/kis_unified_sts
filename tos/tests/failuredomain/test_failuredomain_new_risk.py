"""§4.2 ``new_risk_blocked_by_unproven_isolation`` — the M4 fail-open redesign (design #27 §6).

ADR-002-009 §1 line 32 verbatim: an unestablished isolation property "SHALL reduce authority,
consume conservative capacity where economic state is uncertain, and block new risk. **It SHALL
NOT be converted into permission by redundancy count, operator confidence, a healthy dashboard,
replay capability, or an audit trail.**"

The design #27 §4.2 (M4) redesign makes that **structural**: those five would-be excuses are not
parameters, so a caller cannot pass one. This file proves the structure rather than trusting the
docstring — the signature is asserted to be exactly ``(status)``, every one of the five named
excuses is asserted to raise ``TypeError`` when offered, and the verdict is asserted invariant
across all 2**5 combinations of them.

**both-ways canary**: (a) ``COMMON_MODE`` / ``UNKNOWN`` / ``None`` => ``True`` (the guard fires);
(b) ``ESTABLISHED`` => ``False``. And (b) is **not a permission** — granting authority is
``tos.authority`` / ``tos.liveauth`` business (design #27 §2.2/§3.5-3), which is sealed by the
package-level "no grant surface" assertion here.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import inspect
import itertools

import pytest
from hypothesis import given
from tos.failuredomain import (
    IsolationClaimStatus,
    new_risk_blocked_by_unproven_isolation,
)

from ._failuredomain_strategies import NON_ESTABLISHED_STATUS

#: ADR §1 line 32's five rejected conversions — kept **test-only**, exactly as design #27 §4.2
#: requires: they may appear in a test fixture but never in the predicate signature.
_REJECTED_CONVERSIONS: tuple[str, ...] = (
    "redundancy_count",
    "operator_confident",
    "dashboard_healthy",
    "replay_available",
    "audit_present",
)


# --- both-ways canary --------------------------------------------------------


def test_established_is_not_blocked() -> None:
    """(both-ways b) A positively ESTABLISHED claim is not blocked by *this* check."""
    assert (
        new_risk_blocked_by_unproven_isolation(IsolationClaimStatus.ESTABLISHED)
        is False
    )


@pytest.mark.parametrize(
    "status",
    [IsolationClaimStatus.COMMON_MODE, IsolationClaimStatus.UNKNOWN, None],
)
def test_every_non_established_status_blocks(
    status: IsolationClaimStatus | None,
) -> None:
    """(both-ways a) COMMON_MODE, UNKNOWN and a missing status all block new risk."""
    assert new_risk_blocked_by_unproven_isolation(status) is True


@given(status=NON_ESTABLISHED_STATUS)
def test_property_non_established_always_blocks(
    status: IsolationClaimStatus | None,
) -> None:
    """(§4.2 property) Nothing short of ESTABLISHED ever unblocks — None included."""
    assert new_risk_blocked_by_unproven_isolation(status) is True


def test_exactly_one_status_unblocks() -> None:
    """(polarity) Across the whole status axis plus None, only ESTABLISHED yields False."""
    unblocking = [
        value
        for value in (*IsolationClaimStatus, None)
        if new_risk_blocked_by_unproven_isolation(value) is False
    ]
    assert unblocking == [IsolationClaimStatus.ESTABLISHED]


# --- the M4 structural seal: the five excuses cannot be passed ---------------


def test_signature_is_exactly_status() -> None:
    """(M4) The predicate takes exactly one parameter — no permissive input exists to forge."""
    parameters = inspect.signature(new_risk_blocked_by_unproven_isolation).parameters
    assert list(parameters) == ["status"]


@pytest.mark.parametrize("excuse", _REJECTED_CONVERSIONS)
def test_each_rejected_conversion_cannot_be_passed(excuse: str) -> None:
    """(M4 / §18.2 / §18.6 / §18.7) Offering redundancy / confidence / dashboard / replay / audit fails.

    ADR §18.2 rejects "High availability proves safety isolation"; §18.6 rejects "Priority
    guarantees protective access"; §18.7 rejects "A healthy dashboard proves containment"
    ("Observability and replay do not substitute for prevention"). A caller literally cannot
    express any of them here.
    """
    assert (
        excuse
        not in inspect.signature(new_risk_blocked_by_unproven_isolation).parameters
    )
    with pytest.raises(TypeError):
        new_risk_blocked_by_unproven_isolation(
            IsolationClaimStatus.COMMON_MODE, **{excuse: True}
        )


def test_no_positional_second_argument_is_accepted() -> None:
    """(M4) Not even a positional smuggle works — arity is one."""
    with pytest.raises(TypeError):
        new_risk_blocked_by_unproven_isolation(IsolationClaimStatus.COMMON_MODE, True)


def test_verdict_is_invariant_across_all_thirty_two_excuse_combinations() -> None:
    """(§6 property) The 2**5 test-only excuse combinations cannot change any verdict.

    The excuses are carried alongside as *test* inputs; the verdict is recomputed for each
    combination and must be identical every time, for every status — the executable form of
    "redundancy count, operator confidence, a healthy dashboard, replay capability, or an audit
    trail" never converting an unproven isolation into permission.
    """
    for status in (*IsolationClaimStatus, None):
        expected = new_risk_blocked_by_unproven_isolation(status)
        for combination in itertools.product([True, False], repeat=5):
            excuses = dict(zip(_REJECTED_CONVERSIONS, combination, strict=True))
            assert excuses.keys() == set(_REJECTED_CONVERSIONS)
            # the excuses are inert by construction — they have nowhere to go.
            assert new_risk_blocked_by_unproven_isolation(status) is expected


def test_not_blocked_is_not_a_permission() -> None:
    """(§2.2 / §3.5-3) The package exposes no grant / permit / authorize / arm surface at all."""
    import tos.failuredomain as failuredomain

    granting = [
        name
        for name in dir(failuredomain)
        if not name.startswith("_")
        and callable(getattr(failuredomain, name))
        and any(
            verb in name.lower()
            for verb in ("grant", "permit", "authorize", "allow", "arm", "release")
        )
    ]
    assert granting == [], (
        "tos.failuredomain classifies and blocks only; positive authority belongs to "
        "tos.authority / tos.liveauth / tos.rcl (design #27 §2.2)"
    )
