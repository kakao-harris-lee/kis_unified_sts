"""Pure evidence predicates (design #4 §4, §5, §6).

The EV-L1 *functions* whose contract the property tests verify. None is a stored
artifact field; all are computed on demand from the frozen models. They are
conservative / fail-closed — none can turn an unknown, conflict, gap, or
divergence into an authorization.

Contents (design section -> ERI-EV mapping):

* §4.2 : ``classify_record_pair`` — same-id/different-bytes conflict + idempotency
  (ERI-EV-004 core, §12 central predicate).
* §4.3 : ``compare_order`` — causal ordering priority + ambiguity (ERI-EV-006).
* §5.3 : ``causal_chain_complete`` — causal closure / gap-on-omission (ERI-EV-001).
* §2.7 : ``gap_transition_allowed`` / ``gap_chain_valid`` /
  ``gap_chain_current_status`` / ``gap_blocks_new_risk`` — gap state machine
  (ERI-EV-004/012).
* §4.5 : ``economic_effects_after_retention`` / ``effective_retention_horizon`` /
  ``tombstone_admissible`` — retention orthogonality + tombstone (ERI-EV-010,
  ERI-INV-011).
* §6.2 : ``replay_baseline_supported`` / ``baseline_matches`` — baseline binding
  (ERI-EV-008).
* §2.5 B: ``redaction_profile_valid`` / ``redaction_preserves_digest`` — redaction
  preservation (ERI-EV-009, ERI-INV-010).
* §3.5 : ``eip_binding_ok`` — policy-substitution / generation-drift detection.
* §2.2 : ``receipt_binds_record`` / ``receipt_substitution_rejected`` — receipt
  binding + substitution rejection (ERI-EV-002 predicate-only).
* §2.0 : ``corrected_by`` — derived correction back-reference (forward scan).
* §4.6 : ``grants_no_authority`` — authority-absence (ERI-INV-001/014).
* §4.7/§7: ``repair_preserves_uncertainty`` — recovery non-revival (ERI-EV-012).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from tos.canonical import FrozenModel
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

# ===========================================================================
# §4.2 — same-id/different-bytes conflict + idempotency (ERI-EV-004, §12)
# ===========================================================================


class RecordPairKind(StrEnum):
    """Classification of two envelopes sharing identity (design §4.2, ADR §12)."""

    #: Same record id (or idempotency id) + same canonical bytes — a duplicate.
    IDEMPOTENT_DUP = "IDEMPOTENT_DUP"
    #: Same record id + different canonical bytes — a Critical integrity conflict.
    CRITICAL_CONFLICT = "CRITICAL_CONFLICT"
    #: Same idempotency id + different bytes — a divergent logical emission.
    DIVERGENT_EMISSION = "DIVERGENT_EMISSION"
    #: No shared identity constraint is violated.
    DISTINCT = "DISTINCT"
    #: At least one record is pre-issuance (null digest) — not a ledger citizen.
    NOT_COMPARABLE = "NOT_COMPARABLE"


def classify_record_pair(
    a: SafetyEvidenceEnvelope, b: SafetyEvidenceEnvelope
) -> RecordPairKind:
    """Classify two envelopes by shared identity vs canonical bytes (design §4.2).

    Central ledger predicate (ADR §12 line 321-323): because
    ``evidence_record_id`` is orthogonal to ``canonical_digest``, a same-id /
    different-bytes pair is a **Critical integrity conflict** to contain (both
    observations preserved, never merged / last-write-wins). A same-id /
    same-bytes pair — or a same-idempotency / same-bytes pair — is an idempotent
    duplicate; same-idempotency / different-bytes is a divergent emission.

    Only ISSUED ledger citizens are classified: a record with a null
    ``canonical_digest`` is pre-issuance (a DRAFT, not a ledger member), so any
    pair with a null digest is ``NOT_COMPARABLE`` rather than a false conflict
    (MINOR-1).

    Args:
        a: The first envelope.
        b: The second envelope.

    Returns:
        The :class:`RecordPairKind`.
    """
    if a.canonical_digest is None or b.canonical_digest is None:
        return RecordPairKind.NOT_COMPARABLE
    same_bytes = a.canonical_digest == b.canonical_digest
    same_record = (
        a.evidence_record_id is not None
        and a.evidence_record_id == b.evidence_record_id
    )
    if same_record:
        # Same record id: identical bytes is a duplicate, differing bytes is the
        # §12 Critical conflict (independent of idempotency id).
        return (
            RecordPairKind.IDEMPOTENT_DUP
            if same_bytes
            else RecordPairKind.CRITICAL_CONFLICT
        )
    same_idem = a.idempotency_id is not None and a.idempotency_id == b.idempotency_id
    if same_idem:
        return (
            RecordPairKind.IDEMPOTENT_DUP
            if same_bytes
            else RecordPairKind.DIVERGENT_EMISSION
        )
    return RecordPairKind.DISTINCT


def is_critical_conflict(a: SafetyEvidenceEnvelope, b: SafetyEvidenceEnvelope) -> bool:
    """Whether two envelopes are a §12 same-id/different-bytes conflict (design §4.2)."""
    return classify_record_pair(a, b) is RecordPairKind.CRITICAL_CONFLICT


# ===========================================================================
# §4.3 — causal ordering priority + ambiguity (ERI-EV-006)
# ===========================================================================


class Ordering(StrEnum):
    """A pairwise causal-ordering result (design §4.3, ADR §11)."""

    BEFORE = "BEFORE"
    AFTER = "AFTER"
    AMBIGUOUS = "AMBIGUOUS"


class OrderingEvent(FrozenModel):
    """Ordering coordinates for one event (design §4.3, ADR §11 line 306-315).

    Carries the §11 ordering bases in priority order. Cross-continuity
    ``source_native_sequence`` / ``local_monotonic_value`` are never subtracted
    (compared only within the same ``source_continuity_id``); a bare wall clock is
    absent by construction (only a trustworthy-time *interval* ``time_lo``/
    ``time_hi`` participates).
    """

    event_id: str | None = None
    quorum_commit_index: int | None = None
    egress_journal_sequence: int | None = None
    source_continuity_id: str | None = None
    source_native_sequence: int | None = None
    local_monotonic_value: int | None = None
    causal_predecessor_ids: tuple[str, ...] = ()
    time_lo: int | None = None
    time_hi: int | None = None


def _cmp(a: int, b: int) -> Ordering | None:
    """Return BEFORE/AFTER for a strict comparison, or ``None`` when equal."""
    if a < b:
        return Ordering.BEFORE
    if a > b:
        return Ordering.AFTER
    return None


def compare_order(a: OrderingEvent, b: OrderingEvent) -> Ordering:
    """Order two events by the §11 priority, else AMBIGUOUS (design §4.3).

    Priority (ADR §11 line 306-311): quorum commit index -> egress journal
    sequence -> source-native sequence (same continuity only) -> component
    continuity + local monotonic (same continuity only) -> typed causal links ->
    trustworthy-time interval (disjoint only). A bare cross-host wall clock never
    orders (ADR §11 line 304); overlapping time uncertainty is **ambiguous, not
    sorted** (ADR §11 line 313). Cross-continuity monotonic values are never
    subtracted (ADR §11 line 313).

    Args:
        a: The first event.
        b: The second event.

    Returns:
        ``BEFORE`` (a precedes b), ``AFTER`` (a follows b), or ``AMBIGUOUS``.
    """
    if a.quorum_commit_index is not None and b.quorum_commit_index is not None:
        result = _cmp(a.quorum_commit_index, b.quorum_commit_index)
        if result is not None:
            return result
    if a.egress_journal_sequence is not None and b.egress_journal_sequence is not None:
        result = _cmp(a.egress_journal_sequence, b.egress_journal_sequence)
        if result is not None:
            return result
    same_continuity = (
        a.source_continuity_id is not None
        and a.source_continuity_id == b.source_continuity_id
    )
    if same_continuity:
        if (
            a.source_native_sequence is not None
            and b.source_native_sequence is not None
        ):
            result = _cmp(a.source_native_sequence, b.source_native_sequence)
            if result is not None:
                return result
        if a.local_monotonic_value is not None and b.local_monotonic_value is not None:
            result = _cmp(a.local_monotonic_value, b.local_monotonic_value)
            if result is not None:
                return result
    # Typed causal links (immutable id references).
    if b.event_id is not None and b.event_id in a.causal_predecessor_ids:
        return Ordering.AFTER
    if a.event_id is not None and a.event_id in b.causal_predecessor_ids:
        return Ordering.BEFORE
    # Trustworthy-time interval: only disjoint intervals order; overlap => ambiguous.
    if None not in (a.time_lo, a.time_hi, b.time_lo, b.time_hi):
        if a.time_hi < b.time_lo:  # type: ignore[operator]
            return Ordering.BEFORE
        if b.time_hi < a.time_lo:  # type: ignore[operator]
            return Ordering.AFTER
    return Ordering.AMBIGUOUS


# ===========================================================================
# §5.3 — causal closure / gap-on-omission (ERI-EV-001, predicate-only)
# ===========================================================================


def causal_chain_complete(
    record: SafetyEvidenceEnvelope,
    *,
    required_parent_edge_types: Sequence[EdgeType],
    known_targets: Sequence[tuple[str, str]],
) -> bool:
    """Whether a record's causal chain is complete (design §5.3, ADR §12 line 326).

    Complete iff (a) every required parent edge type is present among the record's
    typed causal links, and (b) every link's ``(target_id, target_digest)`` is a
    known (already-present) ledger member. A missing required parent, or a
    child that arrived before its parent (a link whose target is not yet known),
    is an incomplete chain -> Evidence Gap. Owning-boundary capture is runtime
    (L2+); this is the closure predicate only (ERI-EV-001 predicate-only).

    Args:
        record: The envelope whose causal closure is checked.
        required_parent_edge_types: Edge types this record class must carry.
        known_targets: The ``(target_id, target_digest)`` pairs already present.

    Returns:
        ``True`` iff the chain is complete.
    """
    links = record.causality.causal_links
    present_edge_types = {link.edge_type for link in links}
    if any(
        required not in present_edge_types for required in required_parent_edge_types
    ):
        return False
    known = set(known_targets)
    return all((link.target_id, link.target_digest) in known for link in links)


# ===========================================================================
# §2.7 — gap state machine (ERI-EV-004/012)
# ===========================================================================


def gap_transition_allowed(from_status: GapStatus, to_status: GapStatus) -> bool:
    """Whether a gap status transition is forward-by-one (design §2.7).

    Only the immediate successor is allowed: no skip (SUSPECTED->REPAIRED) and no
    regression (REPAIRED->SUSPECTED).

    Args:
        from_status: The current status.
        to_status: The proposed next status.

    Returns:
        ``True`` iff ``to_status`` is exactly one step after ``from_status``.
    """
    return GAP_STATUS_ORDER.index(to_status) == GAP_STATUS_ORDER.index(from_status) + 1


def gap_chain_valid(records: Sequence[EvidenceGapRecord]) -> bool:
    """Whether an appended gap chain is a valid forward-only progression (§2.7).

    All records must share one ``gap_id`` and their statuses must advance by
    exactly one step each (an appended chain, never a mutated field).

    Args:
        records: The gap records in append order (same ``gap_id``).

    Returns:
        ``True`` iff the chain is a valid forward progression.
    """
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
    """Return the current (head) status of an appended gap chain (design §2.7).

    Args:
        records: The gap records in append order.

    Returns:
        The last record's status.

    Raises:
        ValueError: If the chain is empty.
    """
    if not records:
        raise ValueError("empty gap chain has no current status")
    return records[-1].status


def gap_blocks_new_risk(record: EvidenceGapRecord) -> bool:
    """Whether a gap record blocks new risk (design §2.7, ERI-INV-003).

    Fail-closed: any gap not yet independently reviewed keeps new risk blocked; an
    economic-effect gap stays blocked at least through REPAIRED.

    Args:
        record: The gap record.

    Returns:
        ``True`` iff the record blocks new risk.
    """
    # The model already forbids unblocking before INDEPENDENTLY_REVIEWED (§2.7),
    # so a non-reviewed record is guaranteed blocked; the stored flag is returned.
    return record.response.new_risk_blocked


def repair_preserves_uncertainty(record: EvidenceGapRecord) -> bool:
    """Whether a REPAIRED gap preserves residual uncertainty (design §4.7/§7, EV-012).

    Repair appends recovery sources but does not restore former evidence strength
    (ADR §14 line 372): a REPAIRED (not yet independently reviewed) gap keeps
    ``remaining_uncertainty`` non-``RESOLVED``.

    Args:
        record: The gap record.

    Returns:
        ``True`` iff uncertainty is preserved for a REPAIRED gap.
    """
    if record.status is GapStatus.REPAIRED:
        return record.repair.remaining_uncertainty is not RemainingUncertainty.RESOLVED
    return True


# ===========================================================================
# §4.5 — retention orthogonality + tombstone (ERI-EV-010, ERI-INV-011)
# ===========================================================================


def economic_effects_after_retention(
    economic_effect_ids: Sequence[str], retention_expired_ids: Sequence[str]
) -> frozenset[str]:
    """Economic effects surviving retention expiry (design §4.5, ERI-INV-011).

    Retention / expiry / compaction / archival / deletion-approval / legal-hold
    release change only the retention lifecycle; they never expire an order,
    attempt, exposure, UNKNOWN, or commitment. Economic effect is orthogonal to
    retention, so the economic-effect ids are returned unchanged.

    Args:
        economic_effect_ids: The existing economic-effect record ids.
        retention_expired_ids: The ids whose retention window expired (ignored).

    Returns:
        The economic-effect ids, unchanged.
    """
    del retention_expired_ids  # orthogonal — retention never erases economic effect
    return frozenset(economic_effect_ids)


#: Documented **fallback** dominance rank of retention horizons (design §4.5/ADR
#: §17). This encodes *dominance order only* (not durations); the authoritative
#: "longest applicable" horizon is derived from injected per-horizon durations
#: when supplied (MINOR-3). Concrete durations are Phase-0 (§8), so the rank is a
#: conservative fallback in which economic effect and legal hold dominate.
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
    """Return the longest-applicable horizon of a retention rule (design §4.5/§17).

    "Longest applicable" (ADR §17 line 432) is authoritative from injected
    per-horizon durations when supplied: the rule's horizon with the greatest
    injected ``min_retention_ms`` wins. Only when no durations are injected (the
    Phase-0 unapproved-bound case, §8) does this fall back to the documented
    ``_HORIZON_RANK`` dominance ordering. No duration is hard-coded.

    Args:
        rule: The per-record-class retention rule.
        horizon_durations_ms: Optional injected per-horizon retention durations
            (§8 bounds); when given, they determine the longest applicable horizon.

    Returns:
        The dominating :class:`RetentionHorizon`, or ``None`` if none applies.
    """
    if not rule.horizons:
        return None
    if horizon_durations_ms:
        by_duration = [h for h in rule.horizons if h in horizon_durations_ms]
        if by_duration:
            return max(by_duration, key=lambda h: horizon_durations_ms[h])
    return max(rule.horizons, key=lambda h: _HORIZON_RANK[h])


class RetentionSubject(FrozenModel):
    """Live/economic state a retention target may support (design §2.6, §17 line 441).

    Any flag set makes a Tombstone over the target **inadmissible**: compaction
    must never destroy a record supporting an open/unresolved live or economic
    effect.
    """

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
    """Whether a Tombstone over ``subject`` is admissible (design §2.6, ERI-INV-011).

    Rejected (inadmissible) if the target supports any open order / potentially
    live attempt / UNKNOWN / open position / unreleased capacity / unresolved
    external / active incident / accepted evidence / live scope. This is a
    construction-invariant of the model's tombstone representation (MINOR-3):
    real-store compaction preserving reconstructability is an L2+ concern.

    Args:
        subject: The retention subject's live/economic-state flags.

    Returns:
        ``True`` iff a Tombstone may be appended.
    """
    return not any(getattr(subject, name) for name in type(subject).model_fields)


# ===========================================================================
# §6.2 — replay baseline binding (ERI-EV-008)
# ===========================================================================


def baseline_matches(a: ReplayBaseline, b: ReplayBaseline) -> bool:
    """Whether two replay baselines are exactly equal (design §6.2)."""
    return a == b


def replay_baseline_supported(
    capsule: ReplayCapsule, approved_baselines: Sequence[ReplayBaseline]
) -> bool:
    """Whether a capsule's baseline exactly matches an approved baseline (design §6.2).

    Exact bind: if the baseline is not supported (or was changed), the replay
    result is ``UNSUPPORTED_BASELINE`` and can never PASS (ADR §15 line 407).

    Args:
        capsule: The replay capsule.
        approved_baselines: The approved/known baselines.

    Returns:
        ``True`` iff the capsule's baseline matches one approved baseline exactly.
    """
    return any(baseline_matches(capsule.baseline, b) for b in approved_baselines)


def reevaluation_is_distinct_named_result(
    historical: ReplayCapsule, reevaluation: ReplayCapsule
) -> bool:
    """Whether a current-rule re-evaluation is a distinct result, not an overwrite.

    ERI-EV-008 (design §6.2, ADR §15 line 409): re-evaluating a historical replay
    under *current* rules must produce a **distinct named result** — a separate
    capsule/result record — and must never overwrite or supersede the historical
    result. Structurally (append-only) this holds iff the re-evaluation is a
    different record (distinct ``replay_capsule_id``) that binds a different
    baseline than the historical one; the historical capsule is frozen and stays
    unchanged. The §23.7 "re-evaluate in place" shortcut is thereby rejected.

    Args:
        historical: The original (historical-baseline) replay capsule.
        reevaluation: The current-rule re-evaluation capsule.

    Returns:
        ``True`` iff the re-evaluation is a distinct named result (not an overwrite).
    """
    if reevaluation.replay_capsule_id is None:
        return False
    if reevaluation.replay_capsule_id == historical.replay_capsule_id:
        return False
    # A current-rule re-evaluation binds the *current* baseline, distinct from the
    # historical one; sharing the exact historical baseline would be re-running the
    # historical, not re-evaluating under current rules.
    return not baseline_matches(reevaluation.baseline, historical.baseline)


# ===========================================================================
# §2.5 B — redaction preservation (ERI-EV-009, ERI-INV-010)
# ===========================================================================

#: The safety properties a valid redaction profile MUST preserve (ADR §16 line 422).
_REQUIRED_PRESERVED: frozenset[PreservedProperty] = frozenset(PreservedProperty)


def redaction_preserves_digest(profile: RedactionProfile) -> bool:
    """Whether a redaction profile preserves the canonical digest (design §2.5 B)."""
    return profile.preserves_canonical_digest


def redaction_profile_valid(profile: RedactionProfile) -> bool:
    """Whether a redaction profile is valid (design §2.5 B, ERI-INV-010).

    Valid iff it preserves the canonical digest and field presence (a reviewer can
    detect redaction) and declares preservation of every safety property
    (ordering / quantities / economic effect / identities / scope / outcome). A
    profile that drops any of those is INVALID (ADR §22 line 528).

    Args:
        profile: The redaction profile.

    Returns:
        ``True`` iff the profile is valid.
    """
    if not (profile.preserves_canonical_digest and profile.preserves_field_presence):
        return False
    return _REQUIRED_PRESERVED.issubset(set(profile.preserves))


# ===========================================================================
# §3.5 — EIP binding / policy substitution detection
# ===========================================================================


def eip_binding_ok(
    envelope: SafetyEvidenceEnvelope, policy: EvidenceIntegrityPolicy
) -> bool:
    """Whether an envelope's EIP binding matches the policy (design §3.5).

    The envelope binds ``evidence_integrity_policy_id`` /
    ``evidence_integrity_policy_generation`` / ``evidence_integrity_policy_digest``;
    a mismatch against the known policy's ``policy_id`` / ``generation`` /
    ``content_digest`` (the inherited ``canonical_digest``) is
    policy-substitution / generation-drift (ADR §21 line 505).

    Generation is fail-closed (MINOR-2): if the policy carries a concrete
    ``generation``, the envelope must bind the **same** generation — an envelope
    that leaves it null cannot mask same-body generation drift (``generation`` is
    excluded from the EIP ``content_digest``, so a digest match alone does not
    prove the generation).

    Args:
        envelope: The envelope carrying the EIP binding.
        policy: The known EIP.

    Returns:
        ``True`` iff the binding matches the policy exactly.
    """
    if envelope.evidence_integrity_policy_id != policy.policy_id:
        return False
    if envelope.evidence_integrity_policy_digest != policy.canonical_digest:
        return False
    return not (
        policy.generation is not None
        and envelope.evidence_integrity_policy_generation != policy.generation
    )


# ===========================================================================
# §2.2 — receipt binding + substitution rejection (ERI-EV-002 predicate-only)
# ===========================================================================


def receipt_binds_record(
    receipt: EvidenceCommitReceipt, envelope: SafetyEvidenceEnvelope
) -> bool:
    """Whether a receipt binds exactly to a record (design §2.2, ADR §10.2 line 284).

    Args:
        receipt: The commit receipt.
        envelope: The target evidence envelope.

    Returns:
        ``True`` iff the receipt's record id + record digest match the envelope.
    """
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
    """Whether a receipt must be rejected as a substitution (design §2.2, §10.2 286).

    A receipt for another request (``valid_for_request_digest`` mismatch), another
    scope, or a stale/mismatched policy generation or store continuity must be
    rejected. This proves substitution rejection — **not** durable acceptance
    (which stays UNVERIFIED, gap 5).

    Args:
        receipt: The commit receipt.
        expected_request_digest: The request digest the caller expects.
        expected_scope_digest: The scope digest the caller expects.
        expected_policy_generation: The expected EIP generation (checked if given).
        expected_store_continuity_id: The expected store continuity (checked if given).

    Returns:
        ``True`` iff the receipt must be rejected (any binding mismatch).
    """
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


# ===========================================================================
# §2.0 — derived correction back-reference (forward scan)
# ===========================================================================


def corrected_by(
    record_id: str, ledger: Sequence[SafetyEvidenceEnvelope]
) -> tuple[str, ...]:
    """Derive which records correct ``record_id`` by forward scan (design §2.0).

    The correction back-reference is not stored on the original (that would
    violate append-only); it is derived by scanning forward for records that both
    supersede ``record_id`` and carry a ``CORRECTION`` causal link to it.

    Args:
        record_id: The (possibly) corrected record id.
        ledger: The ordered ledger of envelopes.

    Returns:
        The ids of the records that correct ``record_id`` (in ledger order).
    """
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


# ===========================================================================
# §4.6 — authority absence (ERI-INV-001/014)
# ===========================================================================


def grants_no_authority(authority_block: object) -> bool:
    """Whether an authority block grants nothing (design §4.6).

    Args:
        authority_block: Any block exposing only boolean authority flags.

    Returns:
        ``True`` iff every declared flag is ``False``.
    """
    return not any(
        getattr(authority_block, name) is True
        for name in type(authority_block).model_fields  # type: ignore[attr-defined]
    )
