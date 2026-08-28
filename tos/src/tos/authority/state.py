"""Authority predicate-input / output state models (ADR-002-003 §5, §12-§14, §17).

Plain frozen models that carry the *injected* state the pure predicates fold over
(design §0.2: everything is a pure function over injected state — no leader election,
consensus, registry, or egress). None derives an id; none mutates in place.

Pure module: ``pydantic`` + stdlib + ``tos.authority`` only; no ``shared.*`` (§0.3).
"""

from __future__ import annotations

from tos.authority._base import AuthorityEffect, FrozenModel


class AuthorityEpochState(FrozenModel):
    """The per-domain current accepted epoch floor (ADR-002-003 §5.1/§5.2/§8.2).

    ``current_epoch_floor`` is the durable, monotonically increasing generation number
    of the only current permissive authority for ``authority_domain`` (§5.2 line 113);
    it never regresses (§10.5 "reuse, reset, or wraparound is prohibited"). A ``None``
    domain or floor is UNKNOWN — currentness is unprovable, so ``authority_epoch_current``
    FENCES (fail-closed, §5.1; SA-INV-002/003).
    """

    authority_domain: str | None = None
    current_epoch_floor: int | None = None


class GenerationVector(FrozenModel):
    """Non-collapsing generation-coordinate vector (design §4.7; ADR-002-003 §27 OQ2).

    ADR-002-003 Safety Authority epoch, ADR-002-012 Writer Epoch, membership / restore
    / recovery generation, time-health generation, process generation, and the profile
    generations SHALL NOT be collapsed into one coordinate ("without collapsing
    authority separation", §27 OQ2 line 953-954). Each is an independent injected
    scalar with its **own** floor; the fence predicates read only their own coordinate
    (§4.3 canary — substituting one coordinate's value for another never satisfies a
    fence). A distinct superset of the ``DECISION-CONTEXT-CAPSULE`` template's
    ``generation_vector`` naming, not a copy (design §4.7 m3): ``safety_authority_epoch``
    is kept (not the template's ``authority_epoch``) so the Writer-Epoch non-collapse
    is enforced by the field name itself. Only ``safety_authority_epoch`` is
    authority-owned / fenced here; the rest are reference-only scalars (their owning ADR
    fences them).
    """

    safety_authority_epoch: int | None = None
    writer_epoch: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    recovery_generation: int | None = None
    time_health_generation: int | None = None
    process_generation: int | None = None
    hard_safety_envelope_generation: int | None = None
    runtime_safety_profile_generation: int | None = None


class CurrentnessWitness(FrozenModel):
    """An online currentness witness (ADR-002-003 §12.1 line 454-456; §9.4).

    ``within_containment_bound`` is ``bool | None`` — the capsule ``Freshness``
    fail-closed pattern (design §5.4): ``None`` means the bound could not be
    established (UNKNOWN) and ``currentness_admissible`` DENIES. A witness that is not
    present, out of bound, or conflicting is inadmissible; only a positively present,
    in-bound, non-conflicting witness admits (§12.2 line 458-465). ``witness_source``
    is opaque audit provenance, never read as authority.
    """

    present: bool = False
    within_containment_bound: bool | None = None
    witness_source: str | None = None
    conflicting: bool = False


class CapabilityValidityInputs(FrozenModel):
    """Injected inputs the 6-part validity predicate folds (ADR-002-003 §1; §9.4; §18).

    Carries the §1 conditions 1/3/4/5 substrate and the §18 key / cross-environment
    facts. Every ``bool | None`` field is fail-closed: ``None`` (UNKNOWN) or the unsafe
    value denies (SA-INV-003 "loss of proof is loss of authority"). ``issuer_key_status``
    and ``revocation_status`` are opaque injected tokens (§18.2 key material / MAC
    verification is deferred to L2+ — SA-EV-012); the model consumes them, never
    verifies a signature.
    """

    currentness: CurrentnessWitness = CurrentnessWitness()
    revocation_status: str | None = None
    superseded: bool | None = None
    consumed: bool | None = None
    issuer_key_status: str | None = None
    environment_and_mode_matches: bool | None = None
    dominating_restriction: bool = False


class LeaseReassignmentInputs(FrozenModel):
    """Injected inputs the overlapping-reassignment predicate folds (ADR-002-003 §14.5).

    Before assigning overlapping scope to a new owner, one of ``hard_fence_proven``
    (§5.8 — former owner cannot transmit) or ``lease_expiry_fence_elapsed`` (§5.9 —
    worst-case waiting barrier elapsed) SHALL be positively established (§14.5 line
    582-585). Both are ``bool | None``: ``None`` (unknown) or ``False`` forbids
    reassignment (fail-closed). ``hard_fence_proven`` is an injected flag — the actual
    hard fence is runtime + broker (SA-EV-008 not-Phase-1).
    """

    prior_owner_scope: str | None = None
    hard_fence_proven: bool | None = None
    lease_expiry_fence_elapsed: bool | None = None


class RearmChecklist(FrozenModel):
    """The 14 re-arm prerequisites + dual-control principals (ADR-002-003 §17.1/§17.2).

    Every prerequisite is ``bool | None`` and load-bearing: all 14 must be positively
    ``True`` and the two dual-control principals must differ for ``rearm_gate`` to
    report armable; any ``False`` / ``None`` (UNKNOWN) is not armable (SA-INV-013 "no
    timeout, service recovery, leader election, reconciliation completion event, or
    system restart may automatically re-arm"). ``limit_enlarger_principal`` /
    ``armer_principal`` realize separation of duties (SA-INV-014, §17.2 line 670-674):
    the principal enlarging limits SHALL NOT be the sole principal arming.
    """

    trustworthy_time_restored: bool | None = None
    current_epoch_established: bool | None = None
    stale_epochs_fenced: bool | None = None
    account_wide_reconciliation_complete: bool | None = None
    unknown_orders_resolved: bool | None = None
    unattributed_external_activity_resolved: bool | None = None
    risk_capacity_ledger_consistency_verified: bool | None = None
    protective_leases_reconciled: bool | None = None
    hard_and_runtime_versions_verified: bool | None = None
    broker_capability_current: bool | None = None
    no_unresolved_critical_alert: bool | None = None
    recovery_coordinator_evidence_complete: bool | None = None
    fresh_live_authorization_issued: bool | None = None
    explicit_human_dual_control_complete: bool | None = None

    limit_enlarger_principal: str | None = None
    armer_principal: str | None = None


class PartitionAuthorityVerdict(FrozenModel):
    """Per-action allow/preserve verdict under an unverifiable control plane (§13.1).

    ``*_denied`` flags are the §13.1 line 480-485 DENIED set; ``automatic_rearm_denied``
    is unconditionally ``True`` (§13.5 line 517 "Rejoin does not automatically restore
    live mode"). ``existing_*_preserved`` flags are always ``True`` — existing orders,
    fills, positions, and reservations continue to be tracked conservatively (§13.1
    line 487); a partition neither creates nor releases economic effect (SA-INV-004).
    """

    new_normal_risk_increasing_denied: bool
    new_aggregate_capacity_commitment_denied: bool
    normal_capability_renewal_denied: bool
    live_rearm_denied: bool
    limit_enlargement_denied: bool
    automatic_rearm_denied: bool
    existing_orders_preserved: bool = True
    existing_fills_preserved: bool = True
    existing_positions_preserved: bool = True
    existing_reservations_preserved: bool = True


class RearmVerdict(FrozenModel):
    """The result of the re-arm gate (ADR-002-003 §17.1; §8.4).

    ``armable`` reports only whether every prerequisite + dual control is present — it
    is **non-authorizing**: ``authority_effect`` is all-false (§8.4 line 291 "assembles
    re-arm prerequisites but does not grant live authority"; SA-INV-013). A ``True``
    ``armable`` does not revive any old capability — re-arm issues new capabilities under
    the current epoch (§17.3), which re-run their own §5.2 validity.
    """

    armable: bool
    authority_effect: AuthorityEffect = AuthorityEffect()
