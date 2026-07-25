"""Coordinate non-collapse (design #11 §4.4).

A **test-only** cross-import of the axes that share near-collision tokens — protective
``Admissibility`` / ``GuaranteeLevel`` (protective-decision axis) vs rcl ``CapacityState``
(capacity-consumption axis, e.g. ``TRAPPED_CONSUMED``) and authority ``AuthorityState``
(system-mode axis, e.g. ``DEGRADED_PROTECTIVE``). protective imports **none** of these siblings
at runtime (the import-closure test proves that); this file imports them only to assert type
identity. A test-only import is NOT a package edge (design #11 §3.4/§7.1).
"""

from __future__ import annotations

from tos.authority import AuthorityState
from tos.protective import Admissibility, GuaranteeLevel, ProtectiveActionOutcome
from tos.rcl import CapacityState


def test_trapped_admissibility_is_distinct_type_from_capacity_state() -> None:
    """Admissibility.TRAPPED is not rcl CapacityState.TRAPPED_CONSUMED (distinct types)."""
    assert Admissibility.TRAPPED is not CapacityState.TRAPPED_CONSUMED
    assert type(Admissibility.TRAPPED) is not type(CapacityState.TRAPPED_CONSUMED)
    # The near-collision is only lexical; the values are not even equal strings.
    assert Admissibility.TRAPPED.value == "TRAPPED"
    assert CapacityState.TRAPPED_CONSUMED.value == "TRAPPED_CONSUMED"


def test_guarantee_level_is_distinct_type_from_capacity_state() -> None:
    """GuaranteeLevel tokens are a distinct type from rcl CapacityState (guarantee != capacity)."""
    for level in GuaranteeLevel:
        assert type(level) is not type(CapacityState.TRAPPED_CONSUMED)
    # rcl capacity-state tokens are absent from the protective guarantee vocabulary.
    capacity_values = {c.value for c in CapacityState}
    guarantee_values = {g.value for g in GuaranteeLevel}
    assert capacity_values.isdisjoint(guarantee_values)


def test_degraded_protective_mode_is_authoritys_not_protectives() -> None:
    """The mode token DEGRADED_PROTECTIVE is an authority AuthorityState, absent from protective."""
    assert AuthorityState.DEGRADED_PROTECTIVE.value == "DEGRADED_PROTECTIVE"
    protective_values = (
        {a.value for a in Admissibility}
        | {g.value for g in GuaranteeLevel}
        | {o.value for o in ProtectiveActionOutcome}
    )
    for mode in AuthorityState:
        assert mode.value not in protective_values


def test_admissibility_is_distinct_type_from_authority_state() -> None:
    """protective Admissibility is a distinct type from authority AuthorityState."""
    assert type(Admissibility.ADMISSIBLE) is not type(AuthorityState.LIVE_NORMAL)
