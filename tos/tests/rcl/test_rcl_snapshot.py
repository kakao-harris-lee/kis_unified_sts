"""Snapshot completeness for authoritative restore (§4.4; RCLP-INV-009).

A snapshot missing any completeness element is inadmissible (ADR-012 §21 line 528).
The fixture builds a complete snapshot; each test drops one element and asserts
inadmissibility — a vacuous "admissible" is forbidden.
"""

from __future__ import annotations

import pytest
from tos.rcl import SnapshotCompleteness, snapshot_admissible_for_restore

from ._rcl_strategies import complete_completeness, issue_snapshot


def test_complete_snapshot_is_admissible() -> None:
    """A snapshot with every completeness element present is admissible."""
    assert snapshot_admissible_for_restore(issue_snapshot()) is True


@pytest.mark.parametrize("element", SnapshotCompleteness._ELEMENTS)
def test_missing_any_element_is_inadmissible(element: str) -> None:
    """(canary) Dropping any completeness element => inadmissible (fail-closed)."""
    completeness = complete_completeness(**{element: None})
    snapshot = issue_snapshot(completeness=completeness)
    assert snapshot_admissible_for_restore(snapshot) is False


def test_missing_idempotency_keys_specifically_inadmissible() -> None:
    """(canary) A snapshot missing idempotency keys is inadmissible (§21 line 528)."""
    snapshot = issue_snapshot(
        completeness=complete_completeness(command_idempotency_keys=None)
    )
    assert snapshot_admissible_for_restore(snapshot) is False


def test_missing_capability_use_specifically_inadmissible() -> None:
    """(canary) A snapshot missing capability-use state is inadmissible (§21 line 528)."""
    snapshot = issue_snapshot(
        completeness=complete_completeness(capability_use_state=None)
    )
    assert snapshot_admissible_for_restore(snapshot) is False


def test_empty_completeness_is_inadmissible() -> None:
    """A default (all-missing) completeness block is inadmissible (no vacuous admit)."""
    snapshot = issue_snapshot(completeness=SnapshotCompleteness())
    assert snapshot_admissible_for_restore(snapshot) is False


def test_non_vacuous_element_set() -> None:
    """The required completeness element set is non-empty (guard is meaningful)."""
    assert SnapshotCompleteness._ELEMENTS
