"""Evidence digest-binding REUSE + independent-identity (design #4 §3.1/§3.3/§4.2).

Reuses the design §3.4 (A) digest contract on the evidence covered content and
demonstrates the crux of §3.1 (b): evidence identity is **independent**, not
``f(digest)``. Two records with identical covered content but different
``evidence_record_id`` share the same ``canonical_digest`` — the very fact that
makes a §12 same-id/different-bytes conflict representable and detectable.
Covers envelope / EIP / receipt / replay.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.canonical import ArtifactStatus
from tos.evidence import SafetyEvidenceEnvelope

from ._evidence_strategies import (
    REQUIRED_FIELD_TEXT,
    SCHEME,
    issue_eip,
    issue_envelope,
    issue_receipt,
    issue_replay,
)

# ---- digest == canonicalize(covered) (REUSE §3.4 (A)) ----------------------


def test_envelope_digest_matches_covered() -> None:
    """An issued envelope's digest equals canonicalize(covered) (§3.3)."""
    env = issue_envelope()
    assert env.canonical_digest == SCHEME.compute_digest(env.covered_content())


def test_all_evidence_artifacts_digest_match_covered() -> None:
    """Every digest-bound evidence artifact self-verifies its digest (§3.2)."""
    for artifact in (issue_envelope(), issue_eip(), issue_receipt(), issue_replay()):
        assert artifact.canonical_digest is not None
        assert artifact.canonical_digest == SCHEME.compute_digest(
            artifact.covered_content()
        )


# ---- id is INDEPENDENT, NOT f(digest) (§3.1 (b), §4.2 crux) ----------------


@given(id_a=REQUIRED_FIELD_TEXT, id_b=REQUIRED_FIELD_TEXT)
def test_identity_independent_of_digest(id_a: str, id_b: str) -> None:
    """Same covered content + different record id => SAME digest (id != f(digest))."""
    a = issue_envelope(evidence_record_id=id_a)
    b = issue_envelope(evidence_record_id=id_b)
    # Identity does not enter the covered preimage, so the digest is unchanged.
    assert a.canonical_digest == b.canonical_digest
    if id_a != id_b:
        assert a.evidence_record_id != b.evidence_record_id


def test_covered_change_changes_digest() -> None:
    """Changing a covered field changes the digest (covered-sensitivity)."""
    a = issue_envelope(record_class="INTENT")
    b = issue_envelope(record_class="APPROVAL")
    assert a.canonical_digest != b.canonical_digest


def test_idempotency_id_excluded_from_digest() -> None:
    """The idempotency id is Layer-0: changing it does not move the digest (§2.1)."""
    a = issue_envelope(idempotency_id="idem-A")
    b = issue_envelope(idempotency_id="idem-B")
    assert a.canonical_digest == b.canonical_digest


# ---- frozen immutability + substitution rejection --------------------------


def test_envelope_is_frozen() -> None:
    """An envelope is immutable: field assignment is rejected (ERI-INV-005)."""
    env = issue_envelope()
    with pytest.raises(ValidationError):
        env.record_class = "OTHER"  # type: ignore[misc]


def test_digest_substitution_rejected() -> None:
    """A substituted (wrong) digest is rejected on reconstruction (§4.1/§4.2)."""
    env = issue_envelope()
    kwargs = env.model_dump()
    kwargs["canonical_digest"] = "0" * 64
    with pytest.raises(ValidationError):
        SafetyEvidenceEnvelope(**kwargs)


def test_mutate_covered_with_stale_digest_rejected() -> None:
    """Changing a covered field while keeping the old digest is rejected."""
    env = issue_envelope()
    kwargs = env.model_dump()
    kwargs["record_class"] = "TAMPERED"  # covered change, digest now stale
    with pytest.raises(ValidationError):
        SafetyEvidenceEnvelope(**kwargs)


# ---- excluded insensitivity + DRAFT pre-issuance ---------------------------


def test_status_change_preserves_digest() -> None:
    """Status is excluded: a SUPERSEDED twin keeps the same digest (§3.3)."""
    env = issue_envelope()
    kwargs = env.model_dump()
    kwargs["status"] = ArtifactStatus.SUPERSEDED
    superseded = SafetyEvidenceEnvelope(**kwargs)
    assert superseded.canonical_digest == env.canonical_digest


def test_integrity_block_excluded_from_digest() -> None:
    """The ledger-placement integrity block is excluded: populating it keeps digest."""
    from tos.evidence.envelope import Integrity

    env = issue_envelope()
    kwargs = env.model_dump()
    kwargs["integrity"] = Integrity(segment_id="seg-9", predecessor_commitment="pc-9")
    with_placement = SafetyEvidenceEnvelope(**kwargs)
    assert with_placement.canonical_digest == env.canonical_digest


def test_draft_envelope_requires_null_digest() -> None:
    """A DRAFT envelope with a non-null digest is unconstructable (§3.2)."""
    with pytest.raises(ValidationError):
        SafetyEvidenceEnvelope(status=ArtifactStatus.DRAFT, canonical_digest="x")


def test_issued_envelope_requires_concrete_independent_id() -> None:
    """An issued envelope with a null independent id is rejected (§2.1)."""
    kwargs = issue_envelope().model_dump()
    kwargs["evidence_record_id"] = None
    with pytest.raises(ValidationError):
        SafetyEvidenceEnvelope(**kwargs)
