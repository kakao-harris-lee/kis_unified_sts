"""Pure evidence predicates (design #4 §4, §5, §6)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tos.canonical import FrozenModel, RecordPairKind
from tos.canonical import classify_record_pair as _classify_record_pair_core
from tos.evidence.elements import (
    EdgeType,
    PreservedProperty,
    RedactionProfile,
    RemainingUncertainty,
    RetentionHorizon,
    RetentionRecordClassRule,
)
from tos.evidence.envelope import SafetyEvidenceEnvelope
from tos.evidence.gap import GAP_STATUS_ORDER, EvidenceGapRecord, GapStatus
from tos.evidence.policy import EvidenceIntegrityPolicy
from tos.evidence.receipt import EvidenceCommitReceipt
from tos.evidence.replay import ReplayBaseline, ReplayCapsule
from tos.ordering import Ordering as Ordering
from tos.ordering import OrderingEvent as OrderingEvent
from tos.ordering import compare_order as compare_order


def classify_record_pair(
    a: SafetyEvidenceEnvelope, b: SafetyEvidenceEnvelope
) -> RecordPairKind:
    """Classify two envelopes by shared identity vs canonical bytes (design §4.2)."""
    return _classify_record_pair_core(
        a.evidence_record_id,
        a.canonical_digest,
        b.evidence_record_id,
        b.canonical_digest,
        a_idempotency_id=a.idempotency_id,
        b_idempotency_id=b.idempotency_id,
    )


def is_critical_conflict(a: SafetyEvidenceEnvelope, b: SafetyEvidenceEnvelope) -> bool:
    """Whether two envelopes are a §12 same-id/different-bytes conflict (design §4.2)."""
    return classify_record_pair(a, b) is RecordPairKind.CRITICAL_CONFLICT


def causal_chain_complete(
    record: SafetyEvidenceEnvelope,
    *,
    required_parent_edge_types: Sequence[EdgeType],
    known_targets: Sequence[tuple[str, str]],
) -> bool:
    """Whether a record's causal chain is complete (design §5.3, ADR §12 line 326)."""
    links = record.causality.causal_links
    present_edge_types = {link.edge_type for link in links}
    if any(
        required not in present_edge_types for required in required_parent_edge_types
    ):
        return False
    known = set(known_targets)
    return all((link.target_id, link.target_digest) in known for link in links)


def gap_transition_allowed(from_status: GapStatus, to_status: GapStatus) -> bool:
    """Whether a gap status transition is forward-by-one (design §2.7)."""
    return GAP_STATUS_ORDER.index(to_status) == GAP_STATUS_ORDER.index(from_status) + 1


def gap_chain_valid(records: Sequence[EvidenceGapRecord]) -> bool:
    """Whether an appended gap chain is a valid forward-only progression (§2.7)."""
    if not records:
        return False
    gap_id = records[0].gap_id
    if any(r.gap_id != gap_id for r in records):
        return False
    for earlier, later in zip(records, records[1:]):
        if not gap_transition_allowed(earlier.status, later.status):
            return False
    return True


def gap_chain_current_status(records: Sequence[EvidenceGapRecord]) -> GapStatus:
    """Return the current (head) status of an appended gap chain (design §2.7)."""
    if not records:
        raise ValueError("empty gap chain has no current status")
    return records[-1].status


def gap_blocks_new_risk(record: EvidenceGapRecord) -> bool:
    """Whether a gap record blocks new risk (design §2.7, ERI-INV-003)."""
    return record.response.new_risk_blocked


def repair_preserves_uncertainty(record: EvidenceGapRecord) -> bool:
    """Whether a REPAIRED gap preserves residual uncertainty (design §4.7/§7, EV-012)."""
    if record.status is GapStatus.REPAIRED:
        return record.repair.remaining_uncertainty is not RemainingUncertainty.RESOLVED
    return True


def economic_effects_after_retention(
    economic_effect_ids: Sequence[str], retention_expired_ids: Sequence[str]
) -> frozenset[str]:
    """Economic effects surviving retention expiry (design §4.5, ERI-INV-011)."""
    del retention_expired_ids
    return frozenset(economic_effect_ids)


_HORIZON_RANK: dict[RetentionHorizon, int] = {
    RetentionHorizon.IDEMPOTENCY_REPLAY: 1,
    RetentionHorizon.BROKER_CORRECTION_LATE_FILL: 2,
    RetentionHorizon.VERIFICATION_ACCEPTANCE: 3,
    RetentionHorizon.SAFETY_REVIEW: 4,
    RetentionHorizon.ECONOMIC_EFFECT: 5,
    RetentionHorizon.INCIDENT_LEGAL_HOLD: 6,
}


def effective_retention_horizon(
    rule: RetentionRecordClassRule,
    *,
    horizon_durations_ms: Mapping[RetentionHorizon, int] | None = None,
) -> RetentionHorizon | None:
    """Return the longest-applicable horizon of a retention rule (design §4.5/§17)."""
    if not rule.horizons:
        return None
    if horizon_durations_ms:
        by_duration = [h for h in rule.horizons if h in horizon_durations_ms]
        if by_duration:
            return max(by_duration, key=lambda h: horizon_durations_ms[h])
    return max(rule.horizons, key=lambda h: _HORIZON_RANK[h])


class RetentionSubject(FrozenModel):
    """Live/economic state a retention target may support (design §2.6, §17 line 441)."""

    open_order: bool = False
    potentially_live_attempt: bool = False
    unknown_present: bool = False
    open_position: bool = False
    unreleased_capacity: bool = False
    unresolved_external: bool = False
    active_incident: bool = False
    accepted_evidence: bool = False
    live_scope: bool = False


def tombstone_admissible(subject: RetentionSubject) -> bool:
    """Whether a Tombstone over ``subject`` is admissible (design §2.6, ERI-INV-011)."""
    return not any(getattr(subject, name) for name in type(subject).model_fields)


def baseline_matches(a: ReplayBaseline, b: ReplayBaseline) -> bool:
    """Whether two replay baselines are exactly equal (design §6.2)."""
    return a == b


def replay_baseline_supported(
    capsule: ReplayCapsule, approved_baselines: Sequence[ReplayBaseline]
) -> bool:
    """Whether a capsule's baseline exactly matches an approved baseline (design §6.2)."""
    return any(baseline_matches(capsule.baseline, b) for b in approved_baselines)


def reevaluation_is_distinct_named_result(
    historical: ReplayCapsule, reevaluation: ReplayCapsule
) -> bool:
    """Whether a current-rule re-evaluation is a distinct result, not an overwrite."""
    if reevaluation.replay_capsule_id is None:
        return False
    if reevaluation.replay_capsule_id == historical.replay_capsule_id:
        return False
    return not baseline_matches(reevaluation.baseline, historical.baseline)


_REQUIRED_PRESERVED: frozenset[PreservedProperty] = frozenset(PreservedProperty)


def redaction_preserves_digest(profile: RedactionProfile) -> bool:
    """Whether a redaction profile preserves the canonical digest (design §2.5 B)."""
    return profile.preserves_canonical_digest


def redaction_profile_valid(profile: RedactionProfile) -> bool:
    """Whether a redaction profile is valid (design §2.5 B, ERI-INV-010)."""
    if not (profile.preserves_canonical_digest and profile.preserves_field_presence):
        return False
    return _REQUIRED_PRESERVED.issubset(set(profile.preserves))


def eip_binding_ok(
    envelope: SafetyEvidenceEnvelope, policy: EvidenceIntegrityPolicy
) -> bool:
    """Whether an envelope's EIP binding matches the policy (design §3.5)."""
    if envelope.evidence_integrity_policy_id != policy.policy_id:
        return False
    if envelope.evidence_integrity_policy_digest != policy.canonical_digest:
        return False
    return not (
        policy.generation is not None
        and envelope.evidence_integrity_policy_generation != policy.generation
    )


def receipt_binds_record(
    receipt: EvidenceCommitReceipt, envelope: SafetyEvidenceEnvelope
) -> bool:
    """Whether a receipt binds exactly to a record (design §2.2, ADR §10.2 line 284)."""
    return (
        receipt.evidence_record_id is not None
        and receipt.evidence_record_id == envelope.evidence_record_id
        and receipt.canonical_record_digest is not None
        and receipt.canonical_record_digest == envelope.canonical_digest
    )


def receipt_substitution_rejected(
    receipt: EvidenceCommitReceipt,
    *,
    expected_request_digest: str,
    expected_scope_digest: str,
    expected_policy_generation: int | None = None,
    expected_store_continuity_id: str | None = None,
) -> bool:
    """Whether a receipt must be rejected as a substitution (design §2.2, §10.2 286)."""
    if receipt.valid_for_request_digest != expected_request_digest:
        return True
    if receipt.valid_for_scope_digest != expected_scope_digest:
        return True
    if (
        expected_policy_generation is not None
        and receipt.evidence_integrity_policy_generation != expected_policy_generation
    ):
        return True
    return (
        expected_store_continuity_id is not None
        and receipt.store_continuity_id != expected_store_continuity_id
    )


def corrected_by(
    record_id: str, ledger: Sequence[SafetyEvidenceEnvelope]
) -> tuple[str, ...]:
    """Derive which records correct ``record_id`` by forward scan (design §2.0)."""
    correctors: list[str] = []
    for env in ledger:
        if env.lifecycle.supersedes_record_id != record_id:
            continue
        has_correction_edge = any(
            link.edge_type is EdgeType.CORRECTION and link.target_id == record_id
            for link in env.causality.causal_links
        )
        if has_correction_edge and env.evidence_record_id is not None:
            correctors.append(env.evidence_record_id)
    return tuple(correctors)


def grants_no_authority(authority_block: object) -> bool:
    """Whether an authority block grants nothing (design §4.6)."""
    return not any(
        getattr(authority_block, name) is True
        for name in type(authority_block).model_fields  # type: ignore[attr-defined]
    )
