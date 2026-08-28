"""RCLP-EV-005 (core) — same-command-id / different-bytes conflict + idempotency.

Because ``command_identity`` is orthogonal to ``canonical_command_digest`` (design
§3.1, ``id != f(digest)``), a same-id / different-bytes command pair is a Critical
integrity conflict (ADR-012 §9 line 270) and a same-id / same-bytes pair is an
idempotent duplicate (RCLP-INV-006). The classifier is the promoted
``tos.canonical.classify_record_pair`` applied to command pairs.
"""

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
    # same id + same bytes
    dup = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    # same id + different bytes
    conflict = issue_command(command_identity="cmd-1", actor_identity="actor-2")
    # different id
    distinct = issue_command(command_identity="cmd-2", actor_identity="actor-1")

    assert _classify(a, dup) is RecordPairKind.IDEMPOTENT_DUP
    assert _classify(a, conflict) is RecordPairKind.CRITICAL_CONFLICT
    assert _classify(a, distinct) is RecordPairKind.DISTINCT
    # A DRAFT command (null digest) is not a ledger citizen => NOT_COMPARABLE.
    from tos.rcl import LedgerCommandRecord

    d1 = LedgerCommandRecord(command_identity="cmd-1")
    assert d1.canonical_digest is None
    assert _classify(a, d1) is RecordPairKind.NOT_COMPARABLE


def test_id_orthogonal_to_digest_keeps_conflict_reachable() -> None:
    """(regression lock) id != f(digest): same command id + different bytes conflicts.

    If identity were derived from the digest, same-id would imply same-bytes and
    CRITICAL_CONFLICT would be unreachable. The reservation identity is likewise
    independent (never reused after terminal release, §9 line 502).
    """
    a = issue_command(command_identity="cmd-1", actor_identity="actor-1")
    b = issue_command(command_identity="cmd-1", actor_identity="actor-2")
    assert a.command_identity == b.command_identity
    assert a.canonical_digest != b.canonical_digest  # id did NOT track the digest
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
