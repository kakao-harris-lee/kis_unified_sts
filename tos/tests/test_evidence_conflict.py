"""ERI-EV-004 (core) — duplicate / conflict / continuity (design #4 §4.2, §12)."""

from __future__ import annotations

from hypothesis import given
from tos.evidence import (
    RecordPairKind,
    classify_record_pair,
    is_critical_conflict,
)

from ._evidence_strategies import REQUIRED_FIELD_TEXT, issue_envelope


def test_same_id_different_bytes_is_critical_conflict() -> None:
    """Same record id + different canonical bytes => Critical conflict (§12 line 323)."""
    base = issue_envelope(evidence_record_id="er-1", record_class="INTENT")
    other = issue_envelope(evidence_record_id="er-1", record_class="APPROVAL")
    assert base.canonical_digest != other.canonical_digest
    assert classify_record_pair(base, other) is RecordPairKind.CRITICAL_CONFLICT
    assert is_critical_conflict(base, other) is True


def test_same_idempotency_same_bytes_is_idempotent_dup() -> None:
    """Same idempotency id + same canonical bytes => idempotent duplicate (§12 322)."""
    a = issue_envelope(evidence_record_id="er-1", idempotency_id="idem-1")
    b = issue_envelope(evidence_record_id="er-2", idempotency_id="idem-1")
    assert a.canonical_digest == b.canonical_digest
    assert classify_record_pair(a, b) is RecordPairKind.IDEMPOTENT_DUP


def test_same_idempotency_different_bytes_is_divergent_emission() -> None:
    """Same idempotency id + different bytes => divergent emission (conflict)."""
    a = issue_envelope(
        evidence_record_id="er-1", idempotency_id="idem-1", record_class="INTENT"
    )
    b = issue_envelope(
        evidence_record_id="er-2", idempotency_id="idem-1", record_class="APPROVAL"
    )
    assert classify_record_pair(a, b) is RecordPairKind.DIVERGENT_EMISSION


def test_distinct_records_are_distinct() -> None:
    """Different id + different idempotency => no identity conflict (DISTINCT)."""
    a = issue_envelope(evidence_record_id="er-1", idempotency_id="idem-1")
    b = issue_envelope(evidence_record_id="er-2", idempotency_id="idem-2")
    assert classify_record_pair(a, b) is RecordPairKind.DISTINCT


def test_same_id_same_bytes_is_idempotent_dup() -> None:
    """(MINOR-1) Same record id + same bytes is a duplicate, not a false DISTINCT."""
    a = issue_envelope(evidence_record_id="er-1", idempotency_id="idem-A")
    b = issue_envelope(evidence_record_id="er-1", idempotency_id="idem-B")
    assert a.canonical_digest == b.canonical_digest
    assert classify_record_pair(a, b) is RecordPairKind.IDEMPOTENT_DUP


def test_draft_records_are_not_comparable() -> None:
    """(MINOR-1) A pre-issuance (null-digest) record is not a ledger citizen."""
    from tos.evidence import SafetyEvidenceEnvelope

    d1 = SafetyEvidenceEnvelope(evidence_record_id="er-1")
    d2 = SafetyEvidenceEnvelope(evidence_record_id="er-1")
    assert d1.canonical_digest is None
    assert classify_record_pair(d1, d2) is RecordPairKind.NOT_COMPARABLE
    issued = issue_envelope(evidence_record_id="er-1")
    assert classify_record_pair(d1, issued) is RecordPairKind.NOT_COMPARABLE


@given(rc_a=REQUIRED_FIELD_TEXT, rc_b=REQUIRED_FIELD_TEXT)
def test_conflict_iff_same_id_and_different_bytes(rc_a: str, rc_b: str) -> None:
    """Property: conflict <=> same record id AND different canonical bytes (§4.2)."""
    a = issue_envelope(evidence_record_id="er-1", record_class=rc_a)
    b = issue_envelope(evidence_record_id="er-1", record_class=rc_b)
    conflict = is_critical_conflict(a, b)
    assert conflict is (a.canonical_digest != b.canonical_digest)


def test_conflict_preserves_both_observations() -> None:
    """A conflict contains + preserves both records; neither is merged/overwritten."""
    a = issue_envelope(evidence_record_id="er-1", record_class="INTENT")
    b = issue_envelope(evidence_record_id="er-1", record_class="APPROVAL")
    assert is_critical_conflict(a, b)
    assert a.record_class == "INTENT"
    assert b.record_class == "APPROVAL"
    assert a is not b


def test_continuity_reset_yields_distinct_identity() -> None:
    """A restart/reset (new process_continuity) produces a distinct record (§11 315)."""
    from tos.evidence.envelope import EnvelopeSource

    a = issue_envelope(
        evidence_record_id="er-1",
        idempotency_id="idem-1",
        source=EnvelopeSource(
            principal_id="p",
            workload_identity="w",
            environment_id="e",
            process_continuity_id="cont-1",
        ),
    )
    b = issue_envelope(
        evidence_record_id="er-2",
        idempotency_id="idem-2",
        source=EnvelopeSource(
            principal_id="p",
            workload_identity="w",
            environment_id="e",
            process_continuity_id="cont-2",
        ),
    )
    assert a.canonical_digest != b.canonical_digest
    assert classify_record_pair(a, b) is RecordPairKind.DISTINCT
