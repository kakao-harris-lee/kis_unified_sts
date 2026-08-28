"""Currentness witness / cache != current (§5.4; §9.4; §12; SA-EV-003 substrate).

An online currentness witness is admissible only when positively present, within the
containment bound, and non-conflicting; ``within_containment_bound=None`` (unestablished)
denies — the capsule ``Freshness`` fail-closed pattern. No grace-period operation exists
after currentness loss (§12.3).
"""

from __future__ import annotations

import tos.authority as authority
from tos.authority import CurrentnessWitness, currentness_admissible

from ._authority_strategies import fresh_witness


def test_fresh_witness_is_admissible() -> None:
    """A present, in-bound, non-conflicting witness is admissible (guard not const-False)."""
    assert currentness_admissible(fresh_witness()) is True


def test_absent_witness_denied() -> None:
    """(canary) An absent witness => deny (possession never substitutes, §9.4)."""
    assert currentness_admissible(fresh_witness(present=False)) is False


def test_within_bound_none_denied() -> None:
    """(canary) within_containment_bound=None (UNKNOWN) => deny (fail-closed, §5.4)."""
    assert currentness_admissible(fresh_witness(within_containment_bound=None)) is False


def test_within_bound_false_denied() -> None:
    """A witness out of the containment bound => deny (§12.2)."""
    assert (
        currentness_admissible(fresh_witness(within_containment_bound=False)) is False
    )


def test_conflicting_witness_denied() -> None:
    """(canary) A conflicting witness => deny (§12.2 line 458-465)."""
    assert currentness_admissible(fresh_witness(conflicting=True)) is False


def test_default_witness_denied() -> None:
    """A default (all-empty) witness is inadmissible — never a vacuous admit."""
    assert currentness_admissible(CurrentnessWitness()) is False


def test_guard_fires_both_ways() -> None:
    """The predicate is neither constant-True nor constant-False."""
    admit = currentness_admissible(fresh_witness())
    deny = currentness_admissible(fresh_witness(present=False))
    assert admit is True and deny is False


def test_no_grace_period_operation_exists() -> None:
    """(canary §12.3) The model exposes no post-currentness-loss grace operation."""
    grace_names = [
        name
        for name in dir(authority)
        if any(token in name.lower() for token in ("grace", "grace_period"))
    ]
    assert grace_names == []
