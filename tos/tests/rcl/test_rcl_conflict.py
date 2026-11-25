"""RCLP-EV-005 (core) — same-command-id / different-bytes conflict + idempotency."""

from __future__ import annotations

from hypothesis import given
from tos.canonical import RecordPairKind, classify_record_pair

from ._rcl_strategies import REQUIRED_FIELD_TEXT, issue_command


def _classify(a, b) -> RecordPairKind:
    """Classify two RCL command records by (command_identity, canonical_digest)."""
    return classify_record_pair(
        a.command_identity, a.canonical_digest, b.command_identity, b.canonical_digest
    )


def test_all_four_kinds_reachable_on_command_pairs() -> None:
    """NOT_COMPARABLE / IDEMPOTENT_DUP / CRITICAL_CONFLICT / DISTINCT all reachable."""
    a = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    dup = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    conflict = issue_command(command_identity="cmd-1", actor_identity="actor-2")
    distinct = issue_command(command_identity="cmd-2", actor_identity="actor-1")

    assert _classify(a, dup) is RecordPairKind.IDEMPOTENT_DUP
    assert _classify(a, conflict) is RecordPairKind.CRITICAL_CONFLICT
    assert _classify(a, distinct) is RecordPairKind.DISTINCT
    from tos.rcl import LedgerCommandRecord

    d1 = LedgerCommandRecord(command_identity="cmd-1")
    assert d1.canonical_digest is None
    assert _classify(a, d1) is RecordPairKind.NOT_COMPARABLE


def test_id_orthogonal_to_digest_keeps_conflict_reachable() -> None:
    """(regression lock) id != f(digest): same command id + different bytes conflicts."""
    a = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    b = issue_command(command_identity="cmd-1", actor_identity="actor-2")
    assert a.command_identity == b.command_identity
    assert a.canonical_digest != b.canonical_digest
    assert _classify(a, b) is RecordPairKind.CRITICAL_CONFLICT


@given(role_a=REQUIRED_FIELD_TEXT, role_b=REQUIRED_FIELD_TEXT)
def test_conflict_iff_same_id_and_different_bytes(role_a: str, role_b: str) -> None:
    """Property: same-id conflict <=> canonical bytes differ (§4.5)."""
    a = issue_command(command_identity="cmd-1", permitted_command_role=role_a)
    b = issue_command(command_identity="cmd-1", permitted_command_role=role_b)
    kind = _classify(a, b)
    if a.canonical_digest == b.canonical_digest:
        assert kind is RecordPairKind.IDEMPOTENT_DUP
    else:
        assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_conflict_preserves_both_records() -> None:
    """A conflict contains + preserves both records; neither is merged/overwritten."""
    a = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    b = issue_command(command_identity="cmd-1", actor_identity="actor-2")
    assert _classify(a, b) is RecordPairKind.CRITICAL_CONFLICT
    assert a.actor_identity == "actor-1"
    assert b.actor_identity == "actor-2"
    assert a is not b
