"""retention_deletable predicate + Tombstone tests (design #40 D3-c; ADR-002-016 :432-443).

Deliberately a separate file from the pre-existing ``test_evidence_retention.py``
(Phase 1's ``RetentionSubject``/``tombstone_admissible``/``effective_retention_horizon``
coverage) — this file covers the Phase 2 D3.1 additive predicate over concrete
per-class minimum-day durations, per :mod:`tos.evidence.retention`'s own module
docstring "deliberately separate ... reported not merged" note.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.evidence import Tombstone, retention_deletable

_MINIMUMS = {"INTENT": 30, "ORDER": 90}


# ===========================================================================
# retention_deletable — truth table
# ===========================================================================


def test_deletable_true_when_age_meets_minimum() -> None:
    assert (
        retention_deletable(
            "INTENT", 30, _MINIMUMS, holds_active=False, open_or_live=False
        )
        is True
    )


def test_deletable_true_when_age_exceeds_minimum() -> None:
    assert (
        retention_deletable(
            "INTENT", 45, _MINIMUMS, holds_active=False, open_or_live=False
        )
        is True
    )


def test_deletable_false_when_age_below_minimum() -> None:
    assert (
        retention_deletable(
            "INTENT", 29, _MINIMUMS, holds_active=False, open_or_live=False
        )
        is False
    )


@pytest.mark.parametrize(
    "record_class,age_days,minimum_days_by_class,holds_active,open_or_live",
    [
        # None-axis: every argument's None must refuse, independently.
        (None, 30, _MINIMUMS, False, False),
        ("INTENT", None, _MINIMUMS, False, False),
        ("INTENT", 30, None, False, False),
        ("INTENT", 30, _MINIMUMS, None, False),
        ("INTENT", 30, _MINIMUMS, False, None),
    ],
)
def test_deletable_none_axis_never_admits(
    record_class, age_days, minimum_days_by_class, holds_active, open_or_live
) -> None:
    assert (
        retention_deletable(
            record_class, age_days, minimum_days_by_class, holds_active, open_or_live
        )
        is False
    )


def test_deletable_true_holds_active_never_admits() -> None:
    """holds_active=True refuses (an active hold blocks deletion outright)."""
    assert (
        retention_deletable(
            "INTENT", 30, _MINIMUMS, holds_active=True, open_or_live=False
        )
        is False
    )


def test_deletable_true_open_or_live_never_admits() -> None:
    """open_or_live=True refuses (ADR-002-016 :441 — open/live records are
    never deletable regardless of age)."""
    assert (
        retention_deletable(
            "INTENT", 3650, _MINIMUMS, holds_active=False, open_or_live=True
        )
        is False
    )


def test_deletable_unconfigured_class_never_admits() -> None:
    """A record class with no entry in minimum_days_by_class refuses — no
    configured minimum is not the same as "no minimum required" (fail-closed,
    not vacuous pass, playbook §2.B)."""
    assert (
        retention_deletable(
            "UNCONFIGURED_CLASS",
            99999,
            _MINIMUMS,
            holds_active=False,
            open_or_live=False,
        )
        is False
    )


def test_deletable_negative_age_never_admits() -> None:
    assert (
        retention_deletable(
            "INTENT", -1, _MINIMUMS, holds_active=False, open_or_live=False
        )
        is False
    )


# ===========================================================================
# Tombstone
# ===========================================================================


def test_tombstone_constructs_with_non_blank_dual_control_ref() -> None:
    tombstone = Tombstone(
        record_id="rec-1",
        record_class="INTENT",
        deleted_at="time-snapshot-1",
        dual_control_ref="approval-abc",
    )
    assert tombstone.dual_control_ref == "approval-abc"


@pytest.mark.parametrize("dual_control_ref", [None, "", "   "])
def test_tombstone_rejects_missing_or_blank_dual_control_ref(dual_control_ref) -> None:
    with pytest.raises(ValidationError):
        Tombstone(record_id="rec-1", dual_control_ref=dual_control_ref)


def test_tombstone_frozen() -> None:
    tombstone = Tombstone(dual_control_ref="approval-abc")
    with pytest.raises((TypeError, ValueError)):
        tombstone.dual_control_ref = "approval-xyz"  # type: ignore[misc]
