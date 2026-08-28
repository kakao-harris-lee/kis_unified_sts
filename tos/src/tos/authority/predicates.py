"""Pure Safety Authority predicates (design §5, §6; ADR-002-003 §5-§17).

The EV-L1 *functions* whose contract the property tests verify. None is a stored
field; all are computed on demand over **injected** state (design §0.2: no leader
election, consensus, registry, fencing enforcement, or egress — those are runtime,
EV-L2/L3). Every predicate is conservative / **fail-closed**: an empty set, a missing
/ ``None`` coordinate, an unproven witness, or an unknown state can never become
authority, currentness, or a less-conservative transition (§4.1 SA-INV-003 "loss of
proof is loss of authority").

Lease-validity predicates COMPOSE ``tos.time`` (``conservative_usable_lifetime`` /
``anchor_valid``) instead of taking injected ``lease_time_valid`` / ``exclusivity_ok``
booleans (design §3.4 seam-closure, M1/§6.3): a wrong ``True`` injection path does not
exist. The negative-injected-term fail-closed guard of ``conservative_usable_lifetime``
(Time v1.2 code-review REJECT) is inherited by composition.

Contents (design section -> SA-EV substrate mapping; **no SA-EV is closed**, §1):

* §5.1 : ``authority_epoch_current`` / ``authority_epoch_fenced`` — any-None / domain
  mismatch / stale-epoch => fenced (SA-EV-001/002/014 substrate).
* §5.2 : ``permissive_capability_valid`` — 6-part validity, type-gated condition 4
  (M2), numeric-claim precondition (Gap); egress condition 6 not claimed
  (SA-EV-001/003 substrate).
* §5.3 : ``restrictive_dominates`` / ``safer_transition_allowed`` /
  ``permissive_transition_allowed`` / ``restrictive_may_apply_when_stale`` — precedence
  lattice + order-independent HALT dominance (SA-EV-009 substrate).
* §5.4 : ``currentness_admissible`` — within_bound=None => deny (SA-EV-003 substrate).
* §5.5 : ``halt_denies`` — HALT effect classifier (§16.3).
* §6.1 : ``lease_scope_exclusive`` — claimant-present + unique owner (M1; SA-EV-007).
* §6.2 : ``overlapping_reassignment_forbidden`` — hard-fence ∨ expiry-fence (SA-EV-007).
* §6.3 : ``degraded_lease_valid`` — 7-of-8 §13.2 conditions, time + exclusivity
  composed (SA-EV-004/005 substrate).
* §6.4 : ``degraded_lease_invalidated`` — §14.4 events (SA-EV-006/011 substrate).
* §6.5 : ``partition_authority_verdict`` — deny-table, None => all DENIED (SA-EV-003/014).
* §6.6 : ``rearm_gate`` — non-authorizing conjunctive checklist + SoD (SA-EV-010).
* §4.4 : ``recovery_generation_revives_nothing`` — non-revival (SA-INV-011).

Pure module: ``pydantic`` + stdlib + ``tos.authority`` / ``tos.time`` only; no real
clock, no ``shared.*``, no ``tos.rcl`` / ``tos.capsule`` / ``tos.evidence`` (§0.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.authority._base import ArtifactStatus, AuthorityEffect
from tos.authority.records import (
    DegradedLeaseOwnershipRecord,
    SafetyAuthorityCapability,
)
from tos.authority.state import (
    AuthorityEpochState,
    CapabilityValidityInputs,
    CurrentnessWitness,
    LeaseReassignmentInputs,
    PartitionAuthorityVerdict,
    RearmChecklist,
    RearmVerdict,
)
from tos.authority.vocabulary import (
    PRECEDENCE_RANK,
    RESTRICTIVE_DOMINATING_TYPES,
    AuthorityState,
    CapabilityType,
)
from tos.time import (
    HealthState,
    TimeContinuityIdentity,
    anchor_valid,
    conservative_usable_lifetime,
)

#: The injected issuer-key-status token that positively attests a valid issuer (§18.2).
#: Any other value (incl. ``"revoked"`` / ``"unknown"`` / ``None``) fails closed.
_ISSUER_KEY_VALID = "valid"

#: The injected revocation-status token that positively attests "not revoked" (§1-5).
#: Any other value (incl. ``None`` / unknown) fails closed.
_NOT_REVOKED = "not_revoked"

#: Rank of ``DEGRADED_PROTECTIVE`` — a degraded lease is dominated by any strictly
#: safer state (rank above this). (ADR-002-003 §7; §13.2 line 500; §14.4.)
_DEGRADED_PROTECTIVE_RANK: int = PRECEDENCE_RANK[AuthorityState.DEGRADED_PROTECTIVE]

#: Capability types HALT denies (new risk-increasing, re-arm, limit activation; §16.3).
#: Protective / cancel / reconciliation / risk-reducing types are preserved.
_HALT_DENIED_TYPES: frozenset[CapabilityType] = frozenset(
    {
        CapabilityType.NORMAL_RISK_INCREASING,
        CapabilityType.REARM,
        CapabilityType.LIMIT_ACTIVATION,
    }
)

#: The 14 re-arm prerequisites (ADR-002-003 §17.1 line 653-668). Each is load-bearing.
_REARM_PREREQUISITES: tuple[str, ...] = (
    "trustworthy_time_restored",
    "current_epoch_established",
    "stale_epochs_fenced",
    "account_wide_reconciliation_complete",
    "unknown_orders_resolved",
    "unattributed_external_activity_resolved",
    "risk_capacity_ledger_consistency_verified",
    "protective_leases_reconciled",
    "hard_and_runtime_versions_verified",
    "broker_capability_current",
    "no_unresolved_critical_alert",
    "recovery_coordinator_evidence_complete",
    "fresh_live_authorization_issued",
    "explicit_human_dual_control_complete",
)


# ===========================================================================
# §5.1 — authority epoch currentness / fence (fail-closed)
# ===========================================================================


def authority_epoch_current(
    claimed_epoch: int | None,
    authority_domain: str | None,
    state: AuthorityEpochState,
) -> bool:
    """Whether a claimed epoch is current for its domain (§5.1; SA-INV-001/002).

    ``True`` only when every coordinate is concrete, the domain matches, and the
    claimed epoch is at or above the current floor. Any ``None`` coordinate (claimed
    epoch, domain, state domain, or floor), a domain mismatch, or a stale epoch
    (``claimed_epoch < current_epoch_floor``) => ``False`` (fenced). Reads only the
    Safety Authority epoch coordinate — never a Writer / membership / restore / recovery
    / time-health generation (coordinate non-collapse, §4.3/§4.7). "An epoch is not a
    timestamp" (§5.2 line 115): no wall / monotonic comparison. [SA-INV-002; SAFE-011]

    Args:
        claimed_epoch: The epoch the capability claims (``None`` => fenced).
        authority_domain: The capability's authority domain (``None`` => fenced).
        state: The injected per-domain epoch-floor state.

    Returns:
        ``True`` iff the claimed epoch is provably current; ``False`` (fenced) otherwise.
    """
    if (
        claimed_epoch is None
        or authority_domain is None
        or state.authority_domain is None
        or state.current_epoch_floor is None
    ):
        return False
    if authority_domain != state.authority_domain:
        return False
    return claimed_epoch >= state.current_epoch_floor


def authority_epoch_fenced(
    claimed_epoch: int | None,
    authority_domain: str | None,
    state: AuthorityEpochState,
) -> bool:
    """Whether a claimed epoch is FENCED (the negation of :func:`authority_epoch_current`).

    ``True`` (fenced) exactly when currentness cannot be positively established
    (SA-INV-002/003 — a stale or unknown epoch has no authority).
    """
    return not authority_epoch_current(claimed_epoch, authority_domain, state)


# ===========================================================================
# §5.4 — currentness witness / cache != current (fail-closed)
# ===========================================================================


def currentness_admissible(witness: CurrentnessWitness) -> bool:
    """Whether an online currentness witness is admissible (§5.4; §12.1/§12.2).

    ``True`` only when the witness is positively present, within the containment
    bound, and not conflicting. ``within_containment_bound is None`` (unestablished),
    absent, or conflicting => ``False`` (deny) — the capsule ``Freshness`` fail-closed
    pattern (design §5.4). Possession of a capability never substitutes for a witness
    (cache != current, §9.4 line 362-366). [SA-INV-005; SAFE-011]

    Args:
        witness: The injected currentness witness.

    Returns:
        ``True`` iff the witness positively establishes currentness.
    """
    if not witness.present:
        return False
    if witness.within_containment_bound is not True:
        return False
    return not witness.conflicting


# ===========================================================================
# §5.2 — permissive capability validity (6-part, type-gated, egress boundary)
# ===========================================================================


def permissive_capability_valid(
    capability: SafetyAuthorityCapability,
    state: AuthorityEpochState,
    inputs: CapabilityValidityInputs,
    lease_ok: bool,
) -> bool:
    """Whether an execution path may accept a permissive capability (§5.2; §1 line 17-24).

    Models the EV-L1-decidable 5 of the 6 §1 conditions; **condition 6 (final
    broker-egress independent verification) is NOT claimed** — a ``True`` here is only
    the "execution-path necessary conditions 1-5 met" fact, never authorization
    completion (§0.2/§4.1; the boundary is intentional to avoid overclaim). Fail-closed
    throughout:

    * a DRAFT / claim-incomplete capability => invalid (§9.1 "missing claims are
      denial, not defaults").
    * **numeric-claim precondition (Gap)**: ``maximum_quantity`` OR
      ``maximum_risk_vector_effect_or_reservation_identity`` ``None`` => invalid (a
      capability with no bound is unusable — enforced at consumption, not issuance, so
      ISSUED stays reachable under Phase-1 null profile bounds, §2.2).
    * condition 1 (issuer): ``issuer_key_status != "valid"`` => invalid (§18.2).
    * condition 2 (domain + epoch): ``authority_epoch_current`` must hold (§5.1).
    * condition 3 (scope / environment): ``environment_and_mode_matches`` must be
      ``True`` (None/False => invalid — cross-environment isolation, §18.4). The
      account / instrument / action scope match against the live request is a runtime
      comparison (the capability's own scope claims are required-present); that part is
      the enforcement point's, per §0.2.
    * **condition 4 — capability-type gated (M2)**: ``DEGRADED_PROTECTIVE`` is the ONLY
      type whose condition 4 may be met by ``lease_ok`` (and only after §6.3
      ``degraded_lease_valid``). Every other permissive type — including
      ``NORMAL_RISK_INCREASING`` — requires an ONLINE currentness witness
      (``currentness_admissible``); ``lease_ok`` cannot substitute (§9.4 line 366
      "normal risk-increasing capabilities require an online currentness witness";
      SA-INV-005).
    * condition 5 (not consumed / superseded / revoked / dominated): ``consumed`` /
      ``superseded`` must be ``False`` (None/True => invalid), ``revocation_status``
      must positively attest "not revoked", and ``dominating_restriction`` must be
      ``False`` (§1-5).

    Args:
        capability: The permissive capability under test.
        state: The injected per-domain epoch-floor state.
        inputs: The injected validity inputs (currentness / key / env / status).
        lease_ok: Whether §6.3 degraded-lease validity holds (consumed only for a
            ``DEGRADED_PROTECTIVE`` capability).

    Returns:
        ``True`` iff conditions 1-5 hold (necessary, not sufficient — egress is §0.2).
    """
    # Missing / incomplete claims are denial (§9.1 line 337).
    if capability.status == ArtifactStatus.DRAFT:
        return False
    if capability.missing_required_fields():
        return False

    # Numeric-claim precondition (Gap, §5.2): an unbounded capability is unusable.
    if (
        capability.maximum_quantity is None
        or capability.maximum_risk_vector_effect_or_reservation_identity is None
    ):
        return False

    # Condition 1 — authorized issuer identity (§1-1; §18.2).
    if inputs.issuer_key_status != _ISSUER_KEY_VALID:
        return False

    # Condition 2 — current domain + epoch (§1-2; §5.1).
    if not authority_epoch_current(
        capability.safety_authority_epoch, capability.authority_domain, state
    ):
        return False

    # Condition 3 — environment / mode match (§1-3; §18.4 cross-env isolation).
    if inputs.environment_and_mode_matches is not True:
        return False

    # Condition 4 — validity positively established, capability-type gated (§1-4; M2).
    if capability.capability_type == CapabilityType.DEGRADED_PROTECTIVE:
        if not lease_ok:
            return False
    elif not currentness_admissible(inputs.currentness):
        # NORMAL_RISK_INCREASING and every non-degraded-protective permissive type
        # require an online currentness witness; a degraded lease cannot substitute.
        return False

    # Condition 5 — not consumed / superseded / revoked / dominated (§1-5).
    if inputs.consumed is not False:
        return False
    if inputs.superseded is not False:
        return False
    if inputs.revocation_status != _NOT_REVOKED:
        return False
    return not inputs.dominating_restriction

    # Condition 6 — final broker-egress independent verification (§1-6) is runtime and
    # is NOT asserted here (design §0.2/§4.1; a True result is necessary, not complete).


# ===========================================================================
# §5.3 — restrictive dominance + precedence lattice
# ===========================================================================


def is_restrictive_dominating_type(capability_type: CapabilityType | None) -> bool:
    """Whether a capability type dominates any permissive grant (§5.3; §7 line 239-242)."""
    return capability_type in RESTRICTIVE_DOMINATING_TYPES


def restrictive_dominates(
    current_state: AuthorityState,
    outstanding: Sequence[SafetyAuthorityCapability] = (),
) -> bool:
    """Whether a restrictive state / capability dominates any permissive grant (§5.3).

    ``True`` (a permissive grant is dominated / rejected) when the current authority
    state is at ``DEGRADED_PROTECTIVE`` or safer (rank >= 2), OR any outstanding
    capability is a HALT / CONTAIN (restrictive-dominating) type. **Order-independent**:
    the outstanding set is scanned with ``any`` (issue / arrival order is irrelevant —
    "HALT dominates" whether it raced ahead of or behind the permissive grant, §7 line
    239-242; §20 line 746; SA-INV-010). Dominance does NOT consult ``compare_order`` —
    it is a pure precedence judgment, kept separate from issue-sequence audit (§3.2).

    Args:
        current_state: The current authority state.
        outstanding: The outstanding capabilities (order irrelevant).

    Returns:
        ``True`` iff a permissive grant is dominated.
    """
    if PRECEDENCE_RANK[current_state] >= _DEGRADED_PROTECTIVE_RANK:
        return True
    return any(is_restrictive_dominating_type(c.capability_type) for c in outstanding)


def safer_transition_allowed(
    from_state: AuthorityState, to_state: AuthorityState
) -> bool:
    """Whether a safer-state (or equal) transition is allowed (§5.3; §7 line 237-239).

    A transition toward an equal or safer state (``rank[to] >= rank[from]``) is always
    allowed — safer-state transitions may be triggered broadly and cannot enlarge
    authority (§7 line 239). [SA-INV-010; SAFE-041]
    """
    return PRECEDENCE_RANK[to_state] >= PRECEDENCE_RANK[from_state]


def permissive_transition_allowed(
    from_state: AuthorityState,
    to_state: AuthorityState,
    epoch_current: bool | None,
) -> bool:
    """Whether a permissive (less-safe) transition is allowed (§5.3; §7 line 239).

    A transition toward a less-safe state (``rank[to] < rank[from]``) requires the
    current Safety Authority: it is allowed only when ``epoch_current`` is positively
    ``True`` (None/False => not allowed — fail-closed). A safer-or-equal transition is
    always allowed (delegates to :func:`safer_transition_allowed`). [SA-INV-010]

    Args:
        from_state: The current authority state.
        to_state: The proposed next state.
        epoch_current: Whether the current Safety Authority epoch is established
            (``None`` => not allowed for a permissive direction).

    Returns:
        ``True`` iff the transition is permitted.
    """
    if PRECEDENCE_RANK[to_state] >= PRECEDENCE_RANK[from_state]:
        return True
    return epoch_current is True


def restrictive_may_apply_when_stale(
    *, authentic: bool | None, cannot_enlarge: bool | None
) -> bool:
    """Whether a stale but authentic restrictive message may be applied (§5.3; §16.2).

    A stale HALT / restrictive transition may be conservatively applied even when
    normal permissive currentness cannot be established — **only** when it is
    positively authentic and cannot enlarge authority (§7 line 241-242; §16.2 line
    628-630). Both must be ``True``; ``None`` / ``False`` => not applicable
    (fail-closed). A stale *permissive* grant may never be applied — that is enforced
    by :func:`permissive_capability_valid` requiring currentness, not here. The
    "authentic" determination is signature / replay verification (runtime + security,
    §18; SA-EV-013 not-Phase-1) — Phase-1 consumes it as an injected flag.

    Args:
        authentic: Injected authenticity attestation (``None`` => not applicable).
        cannot_enlarge: Injected cannot-enlarge-authority attestation (``None`` =>
            not applicable).

    Returns:
        ``True`` iff the stale restrictive message may be applied.
    """
    return authentic is True and cannot_enlarge is True


# ===========================================================================
# §5.5 — HALT effects (deny classifier; no blind cancel-all)
# ===========================================================================


def halt_denies(capability_type: CapabilityType) -> bool:
    """Whether HALT denies a capability type (§5.5; §16.3 line 634-641).

    ``True`` (denied) for new risk-increasing transmission, re-arm, and limit
    activation; ``False`` (preserved as the safe-state definition allows) for
    protective / cancel / reconciliation / risk-reducing types. HALT does not derive a
    blind cancel-all: the model provides **no** cancel-all operation (§16.4 line
    643-645 — cancellation is protective-ownership + aggregate-risk evaluation, RCL's
    capacity concern, referenced only by scalar; constructive absence).

    Args:
        capability_type: The capability type under HALT.

    Returns:
        ``True`` iff HALT denies this type.
    """
    return capability_type in _HALT_DENIED_TYPES


# ===========================================================================
# §6.1 — degraded lease exclusivity (claimant-present + unique; M1)
# ===========================================================================


def lease_scope_exclusive(
    claimant_ownership_id: str | None,
    owner_records: Sequence[DegradedLeaseOwnershipRecord],
) -> bool:
    """Whether the claimant is the sole owner of its scope + capacity (§6.1; SA-INV-006).

    ``True`` only when (i) ``claimant_ownership_id`` is present in ``owner_records``
    and (ii) the claimant is the **unique** owner of its
    ``(exclusive_scope, referenced_capacity_lease_id)`` key. An **empty set => False**,
    a **claimant absent => False**, **two or more owners of the same key => False**
    (overlapping — Critical, both records preserved). This closes the v1.0 ``<= 1``
    vacuous-True fail-open (``0 <= 1`` on the empty set; M1). An unestablished key
    coordinate (either ``None``) => False (fail-closed — exclusivity cannot be proven).

    Overlapping ownership is **representable** (two records with the same key can be
    constructed) so that this predicate DETECTS it (ADR-002-003 §24 Critical alert),
    isomorphic to RCL preserving a conflicting branch rather than dropping it.

    **Honest boundary**: this decides exclusivity only within the passed
    ``owner_records`` view; whether that view is complete (registry linearizability /
    propagation) is a runtime property Phase-1 cannot prove (§0.2; SA-EV-007
    completeness is EV-L3 fault injection).

    Args:
        claimant_ownership_id: The claimant lease-ownership id (``None`` => False).
        owner_records: The current owner-registry view.

    Returns:
        ``True`` iff the claimant is present and the sole owner of its scope + capacity.
    """
    if claimant_ownership_id is None:
        return False
    claimant = next(
        (r for r in owner_records if r.lease_ownership_id == claimant_ownership_id),
        None,
    )
    if claimant is None:
        return False
    if (
        claimant.exclusive_scope is None
        or claimant.referenced_capacity_lease_id is None
    ):
        return False  # exclusivity coordinates unestablished => fail-closed
    key = (claimant.exclusive_scope, claimant.referenced_capacity_lease_id)
    owners_of_key = [
        r
        for r in owner_records
        if (r.exclusive_scope, r.referenced_capacity_lease_id) == key
    ]
    return len(owners_of_key) == 1


# ===========================================================================
# §6.2 — overlapping failover forbidden (hard-fence ∨ lease-expiry-fence)
# ===========================================================================


def overlapping_reassignment_forbidden(inputs: LeaseReassignmentInputs) -> bool:
    """Whether overlapping-scope reassignment is FORBIDDEN (§6.2; SA-INV-007; §14.5).

    ``True`` (forbidden) unless one of ``hard_fence_proven`` or
    ``lease_expiry_fence_elapsed`` is positively ``True``. Both ``None`` / ``False`` =>
    forbidden (fail-closed). Epoch advancement alone does NOT unlock reassignment (§14.5
    line 580 "Epoch advancement alone does not prove that the former offline lease can
    no longer transmit") — this predicate never reads an epoch, so advancing one changes
    nothing. The hard fence itself is runtime + broker (§5.8; SA-EV-008 not-Phase-1);
    the lease-expiry-fence duration is a missing profile key (§8 — Phase-0 flag).

    Args:
        inputs: The injected reassignment inputs.

    Returns:
        ``True`` iff reassignment is forbidden.
    """
    return not (
        inputs.hard_fence_proven is True or inputs.lease_expiry_fence_elapsed is True
    )


# ===========================================================================
# §6.3 — degraded lease validity (time + exclusivity composed; 7 of 8 conditions)
# ===========================================================================


def degraded_lease_valid(
    lease_ownership: DegradedLeaseOwnershipRecord,
    owner_registry_view: Sequence[DegradedLeaseOwnershipRecord],
    *,
    protective_classification_present: bool | None,
    broker_capability_permits: bool | None,
    dominating_state: AuthorityState,
    health_state: HealthState,
    continuity_now: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
) -> bool:
    """Whether a degraded protective lease is valid for a new action (§6.3; §13.2).

    Models **7 of the 8** ADR §13.2 conditions (line 491-500); the 8th
    (broker-egress validates the lease and action, line 499) is deferred to runtime,
    isomorphic to §5.2 condition 6 (tos is non-transmitting; SA-EV-008/013 boundary).
    All conditions are fail-closed — any unmet / ``None`` => invalid:

    1. protective classification present (injected flag, ADR-002-001);
    2. pre-committed protective capacity + exclusive sub-consumption (the record's RCL
       scalar references present);
    3. a valid Degraded Protective Lease exists (the ownership record is ISSUED);
    4. local monotonic validity positively established — ``conservative_usable_lifetime``
       is not ``None`` AND ``anchor_valid`` is ``True`` (``tos.time`` composed, §3.4;
       inherits the negative-term fail-closed guard);
    5. scope not overlapping — ``lease_scope_exclusive`` over the passed registry view
       (composed internally; no injected ``exclusivity_ok`` seam, M1);
    6. broker capability permits (injected flag — broker-agnostic capability class);
    7. no dominating safer state — the current dominating state is not strictly safer
       than ``DEGRADED_PROTECTIVE`` (rank not above it) AND the time-health state is
       ``DEGRADED_HOLDOVER`` or ``TRUSTED``.

    Args:
        lease_ownership: The lease-ownership record under test.
        owner_registry_view: The owner-registry view for the exclusivity check.
        protective_classification_present: ADR-002-001 protective classification flag.
        broker_capability_permits: Broker-capability-class permission flag.
        dominating_state: The current dominating authority state.
        health_state: The current time-health state (``tos.time``).
        continuity_now: The current monotonic continuity identity (``tos.time``).
        suspension_ms: Observed suspension magnitude (``None`` => invalid).
        max_suspension_ms: Injected max suspension bound (``None`` => invalid).
        issued_lifetime: Lifetime issued while TRUSTED.
        elapsed_monotonic: Same-continuity elapsed since issue.
        source_transport_uncertainty: Injected transport uncertainty bound.
        max_drift_error: Injected max drift error bound.
        suspension_uncertainty: Injected suspension uncertainty bound.
        safety_margin: Injected approved safety margin.

    Returns:
        ``True`` iff all 7 modeled conditions hold.
    """
    # 1. protective classification (ADR-002-001).
    if protective_classification_present is not True:
        return False
    # 2. pre-committed protective capacity + exclusive sub-consumption (RCL scalars).
    if (
        lease_ownership.referenced_capacity_lease_id is None
        or lease_ownership.referenced_protective_pool_identity is None
    ):
        return False
    # 3. a valid Degraded Protective Lease exists (ISSUED ownership record).
    if (
        lease_ownership.status == ArtifactStatus.DRAFT
        or lease_ownership.canonical_digest is None
    ):
        return False
    # 4. local monotonic validity positively established (tos.time composed).
    if (
        conservative_usable_lifetime(
            issued_lifetime=issued_lifetime,
            elapsed_monotonic=elapsed_monotonic,
            source_transport_uncertainty=source_transport_uncertainty,
            max_drift_error=max_drift_error,
            suspension_uncertainty=suspension_uncertainty,
            safety_margin=safety_margin,
        )
        is None
    ):
        return False
    if not anchor_valid(
        continuity_now,
        lease_ownership.local_monotonic_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    ):
        return False
    # 5. scope not overlapping (exclusivity composed internally; M1).
    if not lease_scope_exclusive(
        lease_ownership.lease_ownership_id, owner_registry_view
    ):
        return False
    # 6. broker capability permits (broker-agnostic capability class).
    if broker_capability_permits is not True:
        return False
    # 7. no dominating safer state + admissible time-health state.
    #    (ADR §13.2 line 500 "no dominating safer state forbids transmission" + §14.4
    #    "dominating CONTAINED / HALTED"; the safer state has the HIGHER precedence rank
    #    — design #6 v1.2 erratum: §6.3 condition 7 uses ``>``, correcting the v1.1
    #    transposition; rationale recorded in the design doc §6.3/§10.1 v1.2.)
    if PRECEDENCE_RANK[dominating_state] > _DEGRADED_PROTECTIVE_RANK:
        return False
    return health_state in {HealthState.DEGRADED_HOLDOVER, HealthState.TRUSTED}


# ===========================================================================
# §6.4 — degraded lease invalidating events (§14.4)
# ===========================================================================


def degraded_lease_invalidated(
    lease_ownership: DegradedLeaseOwnershipRecord,
    owner_registry_view: Sequence[DegradedLeaseOwnershipRecord],
    *,
    continuity_now: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
    protective_capacity_exhausted: bool | None,
    hard_envelope_incompatible: bool | None,
    broker_profile_revoked: bool | None,
    dominating_state: AuthorityState,
) -> bool:
    """Whether a degraded lease is invalidated for new actions (§6.4; §14.4 line 563-576).

    ``True`` (invalidated) if ANY §14.4 event holds: process restart / host reboot /
    monotonic reset / discontinuity / suspension beyond bound (``anchor_valid`` False),
    holdover budget expired (``conservative_usable_lifetime`` None), exclusive-owner
    proof lost (``lease_scope_exclusive`` False — composed, not an injected bool),
    protective capacity exhausted, Hard Envelope incompatibility, broker-profile
    revocation, or a dominating ``CONTAINED`` / ``HALTED`` state. The three injected
    event flags fail closed: ``True`` **or** ``None`` (unknown) invalidates — only an
    explicit ``False`` clears them (a lease's continued validity must be positively
    provable). [SA-INV-009; SA-EV-006/011]

    Args:
        lease_ownership: The lease-ownership record under test.
        owner_registry_view: The owner-registry view for the exclusivity check.
        continuity_now: The current monotonic continuity identity (``tos.time``).
        suspension_ms: Observed suspension magnitude.
        max_suspension_ms: Injected max suspension bound.
        issued_lifetime: Lifetime issued while TRUSTED.
        elapsed_monotonic: Same-continuity elapsed since issue.
        source_transport_uncertainty: Injected transport uncertainty bound.
        max_drift_error: Injected max drift error bound.
        suspension_uncertainty: Injected suspension uncertainty bound.
        safety_margin: Injected approved safety margin.
        protective_capacity_exhausted: RCL-scalar exhaustion flag (None => invalidated).
        hard_envelope_incompatible: Hard Envelope incompatibility flag (None => invalidated).
        broker_profile_revoked: Broker-profile revocation flag (None => invalidated).
        dominating_state: The current dominating authority state.

    Returns:
        ``True`` iff the lease is invalidated for new actions.
    """
    if not anchor_valid(
        continuity_now,
        lease_ownership.local_monotonic_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    ):
        return True
    if (
        conservative_usable_lifetime(
            issued_lifetime=issued_lifetime,
            elapsed_monotonic=elapsed_monotonic,
            source_transport_uncertainty=source_transport_uncertainty,
            max_drift_error=max_drift_error,
            suspension_uncertainty=suspension_uncertainty,
            safety_margin=safety_margin,
        )
        is None
    ):
        return True
    if not lease_scope_exclusive(
        lease_ownership.lease_ownership_id, owner_registry_view
    ):
        return True
    if protective_capacity_exhausted is not False:
        return True
    if hard_envelope_incompatible is not False:
        return True
    if broker_profile_revoked is not False:
        return True
    return PRECEDENCE_RANK[dominating_state] > _DEGRADED_PROTECTIVE_RANK


# ===========================================================================
# §6.5 — partition authority deny-table + registry-unavailable
# ===========================================================================


def partition_authority_verdict(
    control_plane_verifiable: bool | None,
) -> PartitionAuthorityVerdict:
    """The per-action verdict when the safety control plane is (un)verifiable (§6.5; §13.1).

    When the control plane cannot be verified (``control_plane_verifiable`` is
    ``False`` **or** ``None`` — the latter covering an unavailable Epoch Registry,
    §20 line 749), every new-authority action is DENIED (fail-closed — no vacuous
    permit). ``automatic_rearm_denied`` is ``True`` **unconditionally** (§13.5 line 517
    "Rejoin does not automatically restore live mode"). Existing orders / fills /
    positions / reservations are always PRESERVED (§13.1 line 487; SA-INV-004 — a
    partition neither creates nor releases economic effect).

    Args:
        control_plane_verifiable: Injected control-plane verifiability (``None`` =>
            unknown => fail-closed).

    Returns:
        The :class:`~tos.authority.state.PartitionAuthorityVerdict`.
    """
    denied = control_plane_verifiable is None or control_plane_verifiable is False
    return PartitionAuthorityVerdict(
        new_normal_risk_increasing_denied=denied,
        new_aggregate_capacity_commitment_denied=denied,
        normal_capability_renewal_denied=denied,
        live_rearm_denied=denied,
        limit_enlargement_denied=denied,
        automatic_rearm_denied=True,
    )


# ===========================================================================
# §6.6 — re-arm gate (non-authorizing conjunctive checklist + SoD)
# ===========================================================================


def rearm_gate(checklist: RearmChecklist) -> RearmVerdict:
    """The non-authorizing re-arm gate (§6.6; §17.1/§17.2; SA-INV-013/014).

    ``armable`` is ``True`` only when **all 14** prerequisites are positively ``True``
    AND separation of duties holds (both dual-control principals are present and
    distinct). Any ``False`` / ``None`` (UNKNOWN) prerequisite, or a shared / missing
    principal => not armable (SA-INV-013 "no timeout, service recovery, leader
    election, reconciliation completion event, or system restart may automatically
    re-arm"; SA-INV-014 SoD). The verdict is **non-authorizing**: its
    ``authority_effect`` is all-false — ``armable=True`` reports only that the
    prerequisites are met, it grants no live authority (§8.4 line 291; re-arm then
    issues new capabilities under the current epoch, §17.3, which re-run §5.2).

    Args:
        checklist: The injected 14-item checklist + dual-control principals.

    Returns:
        The :class:`~tos.authority.state.RearmVerdict` (non-authorizing).
    """
    all_prerequisites = all(
        getattr(checklist, name) is True for name in _REARM_PREREQUISITES
    )
    separation_of_duties = (
        checklist.limit_enlarger_principal is not None
        and checklist.armer_principal is not None
        and checklist.limit_enlarger_principal != checklist.armer_principal
    )
    return RearmVerdict(
        armable=all_prerequisites and separation_of_duties,
        authority_effect=AuthorityEffect(),
    )


# ===========================================================================
# §4.4 — non-revival (SA-INV-011)
# ===========================================================================


def recovery_generation_revives_nothing(
    *,
    invalidated_under_generation: int | None,
    new_generation: int | None,
) -> bool:
    """Whether a new generation revives an earlier invalidation — never (§4.4; SA-INV-011).

    Unconditionally ``True``: a capability / lease / authority invalidated under
    generation N is **not** revived by generation N+1 or any later one. "Re-arm SHALL
    issue new capabilities under the current epoch. Previously issued live capabilities
    are not revived" (§17.3 line 676-678); once ``HALTED``, no previously issued
    permissive capability restores live operation (SA-INV-011). The model provides
    **no** operation mapping a generation / epoch increase to validity restoration; this
    predicate documents and fixes that absence (isomorphic to the Trustworthy Time / RCL
    ``recovery_generation_revives_nothing``).

    Args:
        invalidated_under_generation: The generation under which it was invalidated.
        new_generation: A later recovery / restore generation.

    Returns:
        ``True`` always (non-revival holds).
    """
    del invalidated_under_generation, new_generation  # no revival path exists
    return True
