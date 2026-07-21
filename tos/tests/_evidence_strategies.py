"""Shared valid-artifact builders + strategies for the evidence property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design §0.3). The
``issue_*`` / ``make_*`` builders populate the safety-load-bearing covered fields
each artifact's issuance guard demands, so a "valid" fixture is genuinely valid
(not the all-null coverage illusion). Every artifact is built through these.
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.evidence import (
    EdgeType,
    EvidenceCommitReceipt,
    EvidenceGapRecord,
    EvidenceIntegrityPolicy,
    GapStatus,
    RecoverySource,
    ReplayCapsule,
    SafetyEvidenceEnvelope,
)
from tos.evidence.envelope import (
    Causality,
    EnvelopeScope,
    EnvelopeSource,
    Lifecycle,
    Payload,
    TimeEvidence,
)
from tos.evidence.gap import GapRepair, GapResponse
from tos.evidence.policy import EIPIntegrity
from tos.evidence.replay import ReplayBaseline, ReplayExpected, ReplayInputs

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved
#: ``"TBD"`` placeholder the issuance guard rejects — design §3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")


# ---------------------------------------------------------------------------
# Safety Evidence Envelope
# ---------------------------------------------------------------------------


def envelope_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Envelope issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "evidence_record_id": "er-1",
        "idempotency_id": "idem-1",
        "record_class": "INTENT",
        "schema_id": "schema-x",
        "schema_version": "1.0",
        "evidence_integrity_policy_id": "eip-1",
        "evidence_integrity_policy_digest": "eip-digest-1",
        "source": EnvelopeSource(
            principal_id="p-1", workload_identity="w-1", environment_id="paper"
        ),
        "scope": EnvelopeScope(
            safety_cell_id="sc-1",
            capacity_domain_id="cd-1",
            account_id="acct-1",
            broker_id="brk-1",
        ),
        "causality": Causality(correlation_id="corr-1"),
        "payload": Payload(
            content_type="application/json",
            raw_payload_digest="raw-1",
            canonical_payload_digest="canon-1",
        ),
        "time_evidence": TimeEvidence(trustworthy_time_snapshot_id="tt-1"),
        "lifecycle": Lifecycle(retention_class="standard"),
    }
    base.update(overrides)
    return base


def issue_envelope(**overrides: Any) -> SafetyEvidenceEnvelope:
    """Issue a valid :class:`SafetyEvidenceEnvelope` (independent id, digest-bound)."""
    return SafetyEvidenceEnvelope.issue(
        scheme=SCHEME, **envelope_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Evidence Integrity Policy
# ---------------------------------------------------------------------------


def eip_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """EIP issuance kwargs with the required covered integrity fields concrete."""
    base: dict[str, Any] = {
        "policy_id": "eip-1",
        "generation": 1,
        "integrity": EIPIntegrity(
            canonical_serialization="canon-json-0",
            content_digest_algorithm="sha256-nonprod",
        ),
    }
    base.update(overrides)
    return base


def issue_eip(**overrides: Any) -> EvidenceIntegrityPolicy:
    """Issue a valid :class:`EvidenceIntegrityPolicy` (digest-bound, independent id)."""
    return EvidenceIntegrityPolicy.issue(
        scheme=SCHEME, **eip_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Evidence Commit Receipt
# ---------------------------------------------------------------------------


def receipt_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Receipt issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "receipt_id": "rcpt-1",
        "evidence_record_id": "er-1",
        "canonical_record_digest": "rec-digest-1",
        "record_class": "INTENT",
        "evidence_integrity_policy_id": "eip-1",
        "evidence_integrity_policy_digest": "eip-digest-1",
        "store_continuity_id": "store-1",
        "durable_segment_id": "seg-1",
        "integrity_anchor_predecessor": "anchor-0",
        "acknowledgement_rule": "quorum",
        "committed_at_time_snapshot_id": "tt-1",
        "committed_at_monotonic_continuity_id": "mono-1",
        "receipt_signer_identity": "signer-1",
        "receipt_signature": "sig-1",
        "valid_for_request_digest": "req-1",
        "valid_for_scope_digest": "scope-1",
    }
    base.update(overrides)
    return base


def issue_receipt(**overrides: Any) -> EvidenceCommitReceipt:
    """Issue a valid :class:`EvidenceCommitReceipt` (UNVERIFIED, binding-only)."""
    return EvidenceCommitReceipt.issue(
        scheme=SCHEME, **receipt_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Replay Capsule
# ---------------------------------------------------------------------------


def replay_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Replay-capsule issuance kwargs satisfying the §6.2/§15 exact-bind minimums."""
    base: dict[str, Any] = {
        "replay_capsule_id": "rc-1",
        "baseline": ReplayBaseline(repository_commit_sha="sha-1"),
        "inputs": ReplayInputs(
            raw_evidence_record_ids=("er-1",),
            raw_evidence_record_digests=("rd-1",),
        ),
        "expected": ReplayExpected(state_digest="exp-1"),
    }
    base.update(overrides)
    return base


def issue_replay(**overrides: Any) -> ReplayCapsule:
    """Issue a valid :class:`ReplayCapsule` (digest-bound, isolated, exact-bound)."""
    return ReplayCapsule.issue(scheme=SCHEME, **replay_required_kwargs(**overrides))


# ---------------------------------------------------------------------------
# Evidence Gap Record (valid at each status; preconditions satisfied)
# ---------------------------------------------------------------------------


def make_gap(
    status: GapStatus, *, gap_id: str = "gap-1", **overrides: Any
) -> EvidenceGapRecord:
    """Build a valid gap record at ``status`` (design §2.7 preconditions satisfied)."""
    kwargs: dict[str, Any] = {"gap_id": gap_id, "status": status}
    if status in (GapStatus.CONFIRMED, GapStatus.CONTAINED, GapStatus.REPAIRED):
        kwargs["detected_by"] = "detector-1"
    if status is GapStatus.INDEPENDENTLY_REVIEWED:
        kwargs["detected_by"] = "detector-1"
    if status is GapStatus.CONTAINED:
        kwargs["response"] = GapResponse(
            new_risk_blocked=True, containment_generation=1
        )
    if status in (GapStatus.REPAIRED, GapStatus.INDEPENDENTLY_REVIEWED):
        kwargs.setdefault(
            "response", GapResponse(new_risk_blocked=True, containment_generation=1)
        )
        kwargs["repair"] = GapRepair(
            recovered_record_ids=("er-1",),
            recovery_sources=(RecoverySource(source_ref="src-1", custodian="cust-1"),),
            repair_method="reconstruct",
            independently_reviewed=(status is GapStatus.INDEPENDENTLY_REVIEWED),
        )
    kwargs.update(overrides)
    return EvidenceGapRecord(**kwargs)


def gap_chain(*statuses: GapStatus, gap_id: str = "gap-1") -> list[EvidenceGapRecord]:
    """Build an appended gap chain over the given statuses (same ``gap_id``)."""
    return [make_gap(s, gap_id=gap_id) for s in statuses]


CORRELATION_EDGE_TYPES = st.sampled_from(list(EdgeType))
