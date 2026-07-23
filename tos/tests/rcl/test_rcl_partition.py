"""Partition deny-table + worst-credible union + non-revival (§6.5; RCLP-EV-004/012).

Under (loss of) quorum every operational action is denied while committed effects
are preserved; disaster-recovery union covers unbounded histories conservatively;
and no generation increase revives an invalidation.
"""

from __future__ import annotations

import pytest
from tos.rcl import (
    CredibleHistory,
    credible_union_capacity,
    partition_verdict,
    recovery_generation_revives_nothing,
)

from ._rcl_strategies import vec

_DENIED_FLAGS = (
    "new_mutation_denied",
    "capability_authorization_denied",
    "capability_claim_denied",
    "transmission_denied",
    "capacity_release_denied",
    "membership_change_denied",
    "automatic_rearm_denied",
)
_PRESERVED_FLAGS = (
    "committed_effects_preserved",
    "potentially_live_preserved",
    "unknown_preserved",
    "trapped_preserved",
    "protective_preserved",
)


def test_quorum_unknown_denies_everything() -> None:
    """(canary) quorum_available=None => every action DENIED (no vacuous permit)."""
    verdict = partition_verdict(None)
    assert all(getattr(verdict, flag) is True for flag in _DENIED_FLAGS)


def test_no_quorum_denies_everything() -> None:
    """quorum_available=False => every action DENIED."""
    verdict = partition_verdict(False)
    assert all(getattr(verdict, flag) is True for flag in _DENIED_FLAGS)


def test_committed_effects_always_preserved() -> None:
    """Committed / potentially-live / UNKNOWN / trapped / protective usage preserved."""
    for quorum in (None, False, True):
        verdict = partition_verdict(quorum)
        assert all(getattr(verdict, flag) is True for flag in _PRESERVED_FLAGS)


def test_quorum_restoration_does_not_auto_rearm() -> None:
    """Quorum restoration never automatically re-arms (§1 line 37) — always denied."""
    verdict = partition_verdict(True)
    assert verdict.automatic_rearm_denied is True
    # But normal operational actions are permitted with quorum.
    assert verdict.new_mutation_denied is False
    assert verdict.capability_authorization_denied is False


# ---- worst-credible union / no last-write-wins (§18 line 472) --------------


def test_all_bounded_union_is_worst_case_max() -> None:
    """Union of bounded histories is the per-dimension maximum (not a chosen branch)."""
    histories = [
        CredibleHistory(history_id="h1", capacity=vec(d=5), bounded=True),
        CredibleHistory(history_id="h2", capacity=vec(d=9), bounded=True),
    ]
    union = credible_union_capacity(histories)
    assert union.magnitude("d") == 9  # worst credible union, not last-write-wins


def test_unbounded_history_forces_unknown_never_dropped() -> None:
    """(canary) An unbounded history => conservative UNKNOWN, never dropped (§18 472)."""
    histories = [
        CredibleHistory(history_id="h1", capacity=vec(d=5), bounded=True),
        CredibleHistory(history_id="h2", capacity=vec(d=3), bounded=False),
    ]
    union = credible_union_capacity(histories)
    assert union.magnitude("d") is None  # UNKNOWN, capacity-consuming


def test_empty_histories_is_fail_closed() -> None:
    """(canary) An empty history set must not read as zero capacity — it raises."""
    with pytest.raises(ValueError):
        credible_union_capacity([])


def test_conflicting_branches_both_contribute_no_merge() -> None:
    """Conflicting histories both contribute to the union (no last-write-wins merge)."""
    histories = [
        CredibleHistory(history_id="h1", capacity=vec(a=5, b=1), bounded=True),
        CredibleHistory(history_id="h2", capacity=vec(a=1, b=8), bounded=True),
    ]
    union = credible_union_capacity(histories)
    # Neither branch overwrites the other: each dimension is the max across both.
    assert union.magnitude("a") == 5
    assert union.magnitude("b") == 8


# ---- non-revival (RCLP-INV-011) --------------------------------------------


def test_generation_increase_revives_nothing() -> None:
    """A new generation never revives an earlier invalidation (always True)."""
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=1, new_generation=5
        )
        is True
    )
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=None, new_generation=None
        )
        is True
    )


def test_no_revive_operation_exists() -> None:
    """The model exposes no 'generation increase => validity restored' operation.

    The only name mentioning revival is ``recovery_generation_revives_nothing`` — the
    predicate that *documents* the absence (returns True) — not a revive operation.
    """
    import tos.rcl as rcl

    revive_names = [
        name
        for name in dir(rcl)
        if name != "recovery_generation_revives_nothing"
        and any(
            token in name.lower()
            for token in ("revive", "reactivate", "rearm", "restore_authority")
        )
    ]
    assert revive_names == []
