"""Pure RCL predicates (RCL design §4, §5, §6).

The EV-L1 *functions* whose contract the property tests verify. None is a stored
field; all are computed on demand over **injected** state (RCL design §0.2: no
consensus, quorum, persistence I/O, or egress — those are runtime, EV-L2/L3). Every
predicate is conservative / **fail-closed**: an empty set, a missing / ``None``
coordinate, an unproven benefit, or an unknown dimension can never become an
authorization, headroom, or a less-conservative transition.

Contents (design section -> EV mapping):

* §5.1 : ``within_limits`` / ``apply_benefit`` — missing-dimension = restrictive
  (empty-set fail-open canary) + benefit = 0 unless positively proven.
* §5.2 : ``apply_committed`` / ``fold_commands`` / ``available_headroom`` —
  deterministic reducer, no-double-spend (aggregate envelope INV-001, CAS),
  idempotency (RCLP-INV-006), producer-optimism canary (RCLP-EV-001 L1 slice).
* §5.4 : ``transition_allowed`` — conservatism partial order; timeout / absence /
  operator-assumption may only increase conservatism.
* §6.1 : ``writer_fenced`` — stale / removed / restored / stale-revision + any-None
  coordinate => FENCED (RCLP-EV-003 substrate).
* §4.1 : ``grant_authorizes_exact_request`` / ``grants_no_authority`` — capacity !=
  authority (RCLP-INV-001/012).
* §6.4 : ``capability_authorization_valid`` / ``claim_capability`` — capacity ->
  capability binding + claim nonce-once (RCLP-EV-006 L1; send boundary deferred).
* §6.5 : ``partition_verdict`` / ``credible_union_capacity`` /
  ``recovery_generation_revives_nothing`` — partition deny-table + worst-credible
  union + non-revival (RCLP-EV-004/012).
* §4.4 : ``snapshot_admissible_for_restore`` — snapshot completeness (RCLP-INV-009).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` / ``tos.rcl`` only; no
``shared.*``, no ``tos.evidence`` / ``tos.capsule`` (RCL design §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.canonical import RecordPairKind, classify_record_pair
from tos.rcl.authority import GrantDecisionRef
from tos.rcl.records import (
    AuthoritativeSnapshot,
    LedgerCommandRecord,
    TransmissionCapability,
)
from tos.rcl.state import (
    AppliedCommand,
    ApplyOutcome,
    ClaimOutcome,
    ClaimRecord,
    CommittedReservation,
    CredibleHistory,
    FenceCoordinates,
    LedgerState,
    PartitionVerdict,
    WriterFenceState,
)
from tos.rcl.vector import (
    BenefitClaim,
    BenefitProof,
    CapacityComponent,
    CapacityVector,
    aggregate_usage,
)
from tos.rcl.vocabulary import (
    WEAK_CAUSES,
    ApplyReason,
    CapacityState,
    CommandType,
    TransitionCause,
)

# ===========================================================================
# §5.1 — conservative projection (missing-dim = restrictive; benefit gated)
# ===========================================================================


def within_limits(
    effect: CapacityVector,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> bool:
    """Whether ``effect`` is within ``limits`` on every applicable dimension (§5.1 r3).

    Fail-closed against the empty-set fail-open (ADR-002-002 §6.2 line 265 "accepted
    only if **every** applicable scope remains within its Effective Limit"):

    * ``applicable_dimensions`` empty => ``False`` (never a vacuous ``True``).
    * any applicable dimension whose magnitude is missing / ``None`` (UNKNOWN) on
      **either** side => ``False`` (a ``None`` dimension is NOT treated as ``0``;
      INV-006 — UNKNOWN consumes capacity, §5.3).
    * otherwise ``True`` iff ``effect[c] <= limits[c]`` for every applicable ``c``.

    Args:
        effect: The economic-effect / usage Capacity Vector.
        limits: The Effective Limit Capacity Vector.
        applicable_dimensions: The dimensions that must all hold (non-empty).

    Returns:
        ``True`` iff every applicable dimension is present and within its limit.
    """
    if not applicable_dimensions:
        return False
    for dimension_id in applicable_dimensions:
        effect_mag = effect.magnitude(dimension_id)
        limit_mag = limits.magnitude(dimension_id)
        if effect_mag is None or limit_mag is None:
            return False
        if effect_mag > limit_mag:
            return False
    return True


def apply_benefit(
    base_vector: CapacityVector,
    benefit_claim: BenefitClaim,
    proof: BenefitProof | None,
) -> CapacityVector:
    """Reduce ``base_vector`` by a claimed benefit **only when positively proven** (§5.1 r2).

    Netting / hedge / diversification / correlation benefit is ``0`` unless a
    positive proof token accompanies the claim (ADR-002-002 §6.5 line 316 "only when
    the Broker Capability Profile proves the enforcement scope and behavior"). With
    ``proof=None`` — or a proof that is not positive — the base vector is returned
    **unchanged** (the "no-benefit flag absent" case is NOT a proof; RCL design §5.1
    canary). A proven reduction lowers each declared, concrete dimension by the
    claimed amount (clamped at ``0``); an UNKNOWN (``None``) dimension stays UNKNOWN,
    and a dimension with no claimed reduction is unchanged. Never made negative.

    Args:
        base_vector: The adverse-increment / usage vector before any benefit.
        benefit_claim: The claimed per-dimension reduction.
        proof: The positive proof token, or ``None`` (no reduction).

    Returns:
        The (possibly reduced) Capacity Vector.
    """
    if proof is None or not proof.is_positive():
        return base_vector
    components: list[CapacityComponent] = []
    for component in base_vector.components:
        dimension_id = component.dimension_id
        base_magnitude = component.magnitude
        reduction = (
            benefit_claim.reduction.magnitude(dimension_id)
            if dimension_id is not None
            else None
        )
        if base_magnitude is None or reduction is None:
            new_magnitude = base_magnitude  # UNKNOWN or unclaimed => unchanged
        else:
            new_magnitude = base_magnitude - reduction
            if new_magnitude < 0:
                new_magnitude = Decimal(0)
        components.append(
            CapacityComponent(
                dimension_id=dimension_id,
                magnitude=new_magnitude,
                unit=component.unit,
                scale=component.scale,
                descriptor=component.descriptor,
            )
        )
    return CapacityVector(components=tuple(components))


# ===========================================================================
# §5.2 — deterministic reducer / no-double-spend (RCLP-EV-001 L1 slice)
# ===========================================================================

#: Reservation states in which committed capacity is still held (aggregate usage).
_LIVE_COMMITTED_STATES: frozenset[CapacityState] = frozenset(
    s for s in CapacityState if s is not CapacityState.RELEASED
)


def committed_usage(state: LedgerState) -> CapacityVector:
    """Aggregate committed usage over non-released reservations (INV-001).

    Derived **only** from committed reservations — never from a producer-local
    counter or scheduler priority (§11.2 step 10 line 594). Released reservations
    consume no capacity.
    """
    return aggregate_usage(
        [
            reservation.adverse_increment
            for reservation in state.committed
            if reservation.capacity_state in _LIVE_COMMITTED_STATES
        ]
    )


def available_headroom(
    state: LedgerState,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> CapacityVector | None:
    """Headroom = limit - committed usage per applicable dimension, or ``None`` (§5.2).

    Fail-closed: empty ``applicable_dimensions`` => ``None``; a committed-UNKNOWN
    usage or a missing limit on any applicable dimension => ``None`` (no headroom may
    be claimed, §5.3). Computed strictly from committed state, so injecting a
    producer-local counter into a command changes nothing (producer-optimism canary).

    Args:
        state: The committed ledger state.
        limits: The Effective Limit vector.
        applicable_dimensions: The dimensions to report headroom for (non-empty).

    Returns:
        The remaining-headroom Capacity Vector, or ``None`` if unprovable.
    """
    if not applicable_dimensions:
        return None
    usage = committed_usage(state)
    components: list[CapacityComponent] = []
    for dimension_id in applicable_dimensions:
        limit_mag = limits.magnitude(dimension_id)
        if limit_mag is None:
            return None
        if usage.declares(dimension_id):
            used = usage.magnitude(dimension_id)
            if used is None:
                return None  # committed UNKNOWN usage => fail-closed
        else:
            used = Decimal(0)  # no committed reservation uses this dimension
        components.append(
            CapacityComponent(dimension_id=dimension_id, magnitude=limit_mag - used)
        )
    return CapacityVector(components=tuple(components))


def _reject(
    state: LedgerState,
    command: LedgerCommandRecord,
    reason: ApplyReason,
) -> ApplyOutcome:
    """Record a committed rejection (no state change) for idempotent retry (§5.2)."""
    applied = AppliedCommand(
        command_identity=command.command_identity,
        canonical_command_digest=command.canonical_digest,
        admitted=False,
        resulting_revision=state.revision,
    )
    rejected_state = LedgerState(
        revision=state.revision,
        committed=state.committed,
        applied_commands=state.applied_commands + (applied,),
    )
    return ApplyOutcome(state=rejected_state, admitted=False, reason=reason)


def apply_committed(
    state: LedgerState,
    command: LedgerCommandRecord,
    *,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> ApplyOutcome:
    """Deterministic fold of one committed command onto ledger state (§5.2).

    The RCLP-EV-001 **L1 slice** — no-double-spend under the aggregate envelope
    (INV-001; AC-001) on a *given* committed order, plus command idempotency
    (RCLP-INV-006) and compare-and-set (§8.4). Deterministic: the result depends only
    on ``(state, command, limits, applicable_dimensions)`` — no wall clock, no
    randomness, no environment, no unordered-collection iteration. (That a *single*
    committed order is produced by quorum under concurrency / partition is EV-L3,
    §0.2.)

    Order of checks (fail-closed):

    1. **idempotency / conflict**: a command whose identity was already applied is
       classified by :func:`tos.canonical.classify_record_pair` over
       ``(command_identity, canonical_digest)``. Same identity + same bytes =>
       ``IDEMPOTENT_REPLAY`` returning the original result (no duplicate transition).
       Same identity + different bytes => ``REJECTED_CRITICAL_CONFLICT`` (contain,
       no last-write-wins; ADR-012 §9 line 270).
    2. **CAS**: a missing or stale ``fence.expected_revision`` => rejected (the
       second of two same-revision commits fails against the advanced revision,
       §8.4 — this is what admits exactly one).
    3. **CommitReservation**: the proposed adverse increment is admitted only if the
       prospective aggregate usage stays ``within_limits``; else limit-exceeded. A
       non-``CommitReservation`` committed command advances the revision without
       changing capacity (the Phase-1 reducer models the aggregate-envelope path;
       full per-command semantics are the transition-predicate / EV-L2+ layer).

    Args:
        state: The current committed ledger state.
        command: The committed command to fold.
        limits: The Effective Limit vector.
        applicable_dimensions: The dimensions the envelope must hold on.

    Returns:
        The :class:`~tos.rcl.state.ApplyOutcome` (new state + admitted + reason).
    """
    command_identity = command.command_identity
    canonical_digest = command.canonical_digest
    if command_identity is None or canonical_digest is None:
        # Not an issued ledger citizen (DRAFT / unidentified) => refuse, no ledger
        # effect (fail-closed — an unidentified command must not mutate capacity).
        return ApplyOutcome(
            state=state, admitted=False, reason=ApplyReason.REJECTED_UNIDENTIFIED
        )
    for prior in state.applied_commands:
        if prior.command_identity != command_identity:
            continue
        kind = classify_record_pair(
            command_identity,
            canonical_digest,
            prior.command_identity,
            prior.canonical_command_digest,
        )
        if kind is RecordPairKind.IDEMPOTENT_DUP:
            # RCLP-INV-006: one identity => one stable result, no new transition.
            return ApplyOutcome(
                state=state,
                admitted=prior.admitted,
                reason=ApplyReason.IDEMPOTENT_REPLAY,
            )
        # CRITICAL_CONFLICT (or NOT_COMPARABLE) => contain; no state change.
        return ApplyOutcome(
            state=state,
            admitted=False,
            reason=ApplyReason.REJECTED_CRITICAL_CONFLICT,
        )

    expected_revision = command.fence.expected_revision
    if expected_revision is None or expected_revision != state.revision:
        return _reject(state, command, ApplyReason.REJECTED_STALE_REVISION)

    if command.command_type is CommandType.COMMIT_RESERVATION:
        return _apply_commit_reservation(
            state, command, limits=limits, applicable_dimensions=applicable_dimensions
        )

    # A committed non-CommitReservation command advances the revision (a committed
    # transition) without changing aggregate capacity in the Phase-1 envelope model.
    new_revision = state.revision + 1
    applied = AppliedCommand(
        command_identity=command_identity,
        canonical_command_digest=canonical_digest,
        admitted=True,
        resulting_revision=new_revision,
    )
    advanced = LedgerState(
        revision=new_revision,
        committed=state.committed,
        applied_commands=state.applied_commands + (applied,),
    )
    return ApplyOutcome(state=advanced, admitted=True, reason=ApplyReason.ADMITTED)


def _apply_commit_reservation(
    state: LedgerState,
    command: LedgerCommandRecord,
    *,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> ApplyOutcome:
    """Admit a CommitReservation iff the prospective aggregate stays within limits."""
    prospective = aggregate_usage(
        [
            reservation.adverse_increment
            for reservation in state.committed
            if reservation.capacity_state in _LIVE_COMMITTED_STATES
        ]
        + [command.proposed_adverse_increment]
    )
    if not within_limits(prospective, limits, applicable_dimensions):
        return _reject(state, command, ApplyReason.REJECTED_LIMIT_EXCEEDED)
    new_revision = state.revision + 1
    reservation = CommittedReservation(
        reservation_id=command.proposed_reservation_id,
        current_reservation_revision=new_revision,
        canonical_record_digest=command.canonical_digest,
        adverse_increment=command.proposed_adverse_increment,
        capacity_state=command.proposed_capacity_state,
    )
    applied = AppliedCommand(
        command_identity=command.command_identity,
        canonical_command_digest=command.canonical_digest,
        admitted=True,
        resulting_revision=new_revision,
    )
    committed_state = LedgerState(
        revision=new_revision,
        committed=state.committed + (reservation,),
        applied_commands=state.applied_commands + (applied,),
    )
    return ApplyOutcome(
        state=committed_state, admitted=True, reason=ApplyReason.ADMITTED
    )


def fold_commands(
    initial_state: LedgerState,
    commands: Sequence[LedgerCommandRecord],
    *,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> LedgerState:
    """Fold an ordered command sequence to a final ledger state (§5.2 determinism).

    A pure left fold of :func:`apply_committed`. The result depends only on the
    ordered inputs — the RCLP-EV-001 determinism property.
    """
    state = initial_state
    for command in commands:
        state = apply_committed(
            state,
            command,
            limits=limits,
            applicable_dimensions=applicable_dimensions,
        ).state
    return state


# ===========================================================================
# §5.4 — capacity-state conservatism lattice
# ===========================================================================

#: Conservatism rank (higher = more conservative / more capacity-consuming). A
#: less-conservative move (lower rank) requires a strong (non-weak) cause; RELEASED
#: (lowest) additionally requires the final-quantity proof rule (INV-007).
_CONSERVATISM_RANK: dict[CapacityState, int] = {
    CapacityState.RELEASED: 0,
    CapacityState.COMMITTED_UNBOUND: 1,
    CapacityState.ATTEMPT_BOUND: 2,
    CapacityState.POTENTIALLY_LIVE: 3,
    CapacityState.PARTIALLY_CONSUMED: 4,
    CapacityState.POSITION_CONSUMED: 5,
    CapacityState.RELEASE_PENDING_PROOF: 6,
    CapacityState.TRAPPED_CONSUMED: 7,
    CapacityState.QUARANTINED_UNKNOWN: 8,
}


def transition_allowed(
    from_state: CapacityState,
    to_state: CapacityState,
    cause: TransitionCause,
) -> bool:
    """Whether a capacity-state transition is allowed under ``cause`` (§5.4; §10.2).

    Conservatism partial order (ADR-002-002 §10.2 line 564-574):

    * ``RELEASED`` is terminal for the reservation identity (§10.1 line 562) — no
      transition may leave it.
    * a transition **to** ``RELEASED`` is allowed only under
      ``FINAL_QUANTITY_PROOF`` (INV-007 — final cumulative filled quantity + zero
      remaining, or approved stronger proof).
    * an increase (or equal) in conservatism is allowed under any cause.
    * a **decrease** in conservatism (a less-conservative state) requires a strong
      cause; a weak cause (``TIMEOUT`` / ``ABSENCE`` / ``OPERATOR_ASSUMPTION``) may
      only increase conservatism (§10.2 line 574).

    Args:
        from_state: The current capacity state.
        to_state: The proposed next capacity state.
        cause: The cause driving the transition.

    Returns:
        ``True`` iff the transition is permitted.
    """
    if from_state is CapacityState.RELEASED:
        return False
    if to_state is CapacityState.RELEASED:
        return cause is TransitionCause.FINAL_QUANTITY_PROOF
    if _CONSERVATISM_RANK[to_state] >= _CONSERVATISM_RANK[from_state]:
        return True
    return cause not in WEAK_CAUSES


# ===========================================================================
# §6.1 — writer fencing (fail-closed)
# ===========================================================================


def writer_fenced(
    coords: FenceCoordinates,
    fence_state: WriterFenceState,
) -> bool:
    """Whether a command / capability is FENCED (rejected) (§6.1; RCLP-INV-004).

    ``True`` (FENCED) if **any** of (ADR-012 §13 state-machine fencing, §14, §5.7):

    * any command coordinate (``expected_writer_epoch`` / ``membership_generation``
      / ``restore_generation`` / ``expected_revision``) is ``None`` (UNKNOWN —
      currentness unprovable => fail-closed);
    * any injected floor is ``None`` (unprovable => fail-closed);
    * ``expected_writer_epoch < writer_epoch_floor`` (stale writer, §13 line 355);
    * ``membership_generation`` differs (removed / stale voter, §14 line 375);
    * ``restore_generation`` differs (crossing a restore, §5.7 line 139);
    * ``expected_revision`` differs from the current revision (stale CAS, §9 line
      259).

    Args:
        coords: The command / capability currentness coordinates.
        fence_state: The injected monotone floors + current revision.

    Returns:
        ``True`` iff FENCED (rejected).
    """
    if None in (
        coords.expected_writer_epoch,
        coords.membership_generation,
        coords.restore_generation,
        coords.expected_revision,
    ):
        return True
    if None in (
        fence_state.writer_epoch_floor,
        fence_state.membership_generation,
        fence_state.restore_generation,
        fence_state.revision,
    ):
        return True
    if coords.expected_writer_epoch < fence_state.writer_epoch_floor:  # type: ignore[operator]
        return True
    if coords.membership_generation != fence_state.membership_generation:
        return True
    if coords.restore_generation != fence_state.restore_generation:
        return True
    return coords.expected_revision != fence_state.revision


# ===========================================================================
# §4.1 — capacity != authority
# ===========================================================================


def grants_no_authority(authority_block: object) -> bool:
    """Whether an authority block grants nothing — every flag ``False`` (§4.1).

    Args:
        authority_block: Any block exposing only boolean authority flags.

    Returns:
        ``True`` iff no declared flag is ``True``.
    """
    return not any(
        getattr(authority_block, name) is True
        for name in type(authority_block).model_fields  # type: ignore[attr-defined]
    )


def grant_authorizes_exact_request(
    grant: GrantDecisionRef,
    committed_reservation: CommittedReservation,
    *,
    current_generation: int | None,
) -> bool:
    """Whether a grant authorizes exactly this committed reservation (§4.1 layer 3).

    A grant / decision is a non-authoritative input; it authorizes a request only
    when bound to the **exact** committed reservation revision + record (effect)
    digest + current generation (ADR-002-002 §11.1 step 6; ADR-012 §8.4 line 461-463
    "stale approval cannot be committed against changed Ledger state"). Any missing
    coordinate, or any mismatch, => ``False`` (fail-closed). Holding the grant never
    mutates capacity — only a committed transition does.

    Args:
        grant: The Aggregate Risk / Action Flow decision reference.
        committed_reservation: The committed reservation the grant must bind to.
        current_generation: The current generation the grant must match.

    Returns:
        ``True`` iff the grant is bound exactly and currently.
    """
    if (
        grant.bound_reservation_revision is None
        or committed_reservation.current_reservation_revision is None
        or grant.bound_reservation_revision
        != committed_reservation.current_reservation_revision
    ):
        return False
    if (
        grant.bound_reservation_digest is None
        or committed_reservation.canonical_record_digest is None
        or grant.bound_reservation_digest
        != committed_reservation.canonical_record_digest
    ):
        return False
    if grant.bound_generation is None or current_generation is None:
        return False
    return grant.bound_generation == current_generation


# ===========================================================================
# §6.4 — capacity -> capability binding + claim nonce-once (RCLP-EV-006 L1)
# ===========================================================================

#: Reservation states in which a capability may be authorized against an attempt.
_CAPABILITY_ACTIVE_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.COMMITTED_UNBOUND, CapacityState.ATTEMPT_BOUND}
)


def capability_authorization_valid(
    auth: TransmissionCapability,
    committed_reservation: CommittedReservation,
    fence_state: WriterFenceState,
    *,
    applicable_dimensions: Sequence[str],
) -> bool:
    """Whether a capability authorization is valid (§6.4; ADR-012 §11 line 317-329).

    Valid only when it references an **already committed** reservation revision, the
    reservation is active with an attempt bound + unused, the capacity vector covers
    the **exact** worst-case effect, all generations are current (not fenced), and no
    dominating restriction / UNKNOWN blocks it. Any mismatch or missing coordinate =>
    ``False`` — an uncommitted / minority-issued / stale-generation / capacity-unbound
    capability is invalid even if signed (§11 line 329). Send boundary / egress is
    deferred (§0.2).

    Args:
        auth: The Transmission Capability (bound revision, worst-case effect, fence).
        committed_reservation: The committed reservation it must bind to.
        fence_state: The current fence floors / generations.
        applicable_dimensions: The dimensions the effect coverage must hold on.

    Returns:
        ``True`` iff the authorization is valid.
    """
    if (
        auth.bound_reservation_revision is None
        or committed_reservation.current_reservation_revision is None
        or auth.bound_reservation_revision
        != committed_reservation.current_reservation_revision
    ):
        return False
    if committed_reservation.capacity_state not in _CAPABILITY_ACTIVE_STATES:
        return False
    if not (
        committed_reservation.attempt_bound and committed_reservation.attempt_unused
    ):
        return False
    if auth.dominating_restriction:
        return False
    if not within_limits(
        auth.worst_case_effect,
        committed_reservation.adverse_increment,
        applicable_dimensions,
    ):
        return False
    return not writer_fenced(auth.fence, fence_state)


def claim_capability(
    nonce: str | None,
    prior_claims: Sequence[ClaimRecord],
    *,
    result: str = "SEND_STARTED",
) -> ClaimOutcome:
    """Claim a capability, consuming its nonce **exactly once** (§6.4; ADR-012 §12).

    First claim of a ``nonce`` consumes it (``consumed_now=True``); every later
    duplicate claim of the same nonce returns the **original** committed result
    without creating another send authority (``replay=True``; §12 line 343). A
    ``None`` nonce cannot be claimed (fail-closed — no send authority).

    Args:
        nonce: The capability nonce being claimed.
        prior_claims: The already-recorded claims (append-only).
        result: The committed result recorded on first consumption.

    Returns:
        The :class:`~tos.rcl.state.ClaimOutcome`.
    """
    if nonce is None:
        return ClaimOutcome(consumed_now=False, replay=False, result=None)
    for prior in prior_claims:
        if prior.nonce == nonce:
            return ClaimOutcome(consumed_now=False, replay=True, result=prior.result)
    return ClaimOutcome(consumed_now=True, replay=False, result=result)


# ===========================================================================
# §6.5 — partition deny-table + worst-credible union + non-revival
# ===========================================================================


def partition_verdict(quorum_available: bool | None) -> PartitionVerdict:
    """The per-action verdict under (loss of) quorum (§6.5; ADR-012 §15 line 389-401).

    When quorum cannot be proven (``quorum_available`` is ``False`` **or** ``None``),
    every operational action is DENIED (fail-closed against the unknown case — a
    vacuous permit is forbidden). Automatic re-arm is DENIED **unconditionally**:
    quorum restoration SHALL NOT automatically re-arm (§1 line 37). Committed /
    potentially-live / UNKNOWN / trapped / protective usage is always PRESERVED
    (RCLP-INV-008) — quorum loss neither creates nor replenishes capacity.

    Args:
        quorum_available: Injected quorum flag (``None`` = unknown => fail-closed).

    Returns:
        The :class:`~tos.rcl.state.PartitionVerdict`.
    """
    denied = quorum_available is None or quorum_available is False
    return PartitionVerdict(
        new_mutation_denied=denied,
        capability_authorization_denied=denied,
        capability_claim_denied=denied,
        transmission_denied=denied,
        capacity_release_denied=denied,
        membership_change_denied=denied,
        automatic_rearm_denied=True,
    )


def credible_union_capacity(
    histories: Sequence[CredibleHistory],
) -> CapacityVector:
    """Worst credible union of reconstructable histories (§6.5; ADR-012 §18 line 472).

    Capacity SHALL cover the worst credible union of the reconstructable histories,
    without last-write-wins merge and without discarding a conflicting branch. A
    history **not** bounded by the Credible State Space (active Broker Capability
    Profile + approved Adverse Scenario Set) is treated conservatively as UNKNOWN and
    capacity-consuming, never dropped — so if any history is unbounded, every
    dimension of the union is UNKNOWN (``None``, fail-closed). When all histories are
    bounded, each dimension is the maximum across declaring histories (union, not a
    chosen branch); any contributing UNKNOWN keeps that dimension UNKNOWN.

    **Empty input is fail-closed**: an empty ``histories`` set is not "zero capacity
    to cover" — it is the absence of any reconstructable history, which must never be
    read optimistically. It raises :class:`ValueError` rather than returning an empty
    (zero-capacity) vector.

    Args:
        histories: The reconstructable histories (each with a ``bounded`` flag);
            must be non-empty.

    Returns:
        The worst-credible-union Capacity Vector.

    Raises:
        ValueError: If ``histories`` is empty (an empty union must not read as zero).
    """
    if not histories:
        raise ValueError(
            "credible_union_capacity requires at least one reconstructable history: "
            "an empty history set must not be read as zero capacity to cover "
            "(fail-closed; ADR-012 §18)"
        )
    dimensions: list[str] = []
    for history in histories:
        for dimension_id in history.capacity.dimension_ids():
            if dimension_id not in dimensions:
                dimensions.append(dimension_id)
    any_unbounded = any(not history.bounded for history in histories)
    components: list[CapacityComponent] = []
    for dimension_id in dimensions:
        magnitude: Decimal | None
        if any_unbounded:
            magnitude = None
        else:
            declared = [
                history.capacity.magnitude(dimension_id)
                for history in histories
                if history.capacity.declares(dimension_id)
            ]
            concrete = [m for m in declared if m is not None]
            # Any contributing UNKNOWN (a shorter concrete list) keeps this dim UNKNOWN.
            magnitude = (
                max(concrete) if len(concrete) == len(declared) and concrete else None
            )
        components.append(
            CapacityComponent(dimension_id=dimension_id, magnitude=magnitude)
        )
    return CapacityVector(components=tuple(components))


def recovery_generation_revives_nothing(
    *,
    invalidated_under_generation: int | None,
    new_generation: int | None,
) -> bool:
    """Whether a new generation revives an earlier invalidation — never (§6.5; INV-011).

    Unconditionally ``True``: a capability / lease / authority invalidated under
    generation N is **not** revived by generation N+1 or any later one (ADR-012
    §17.4 line 453/455 — restore requires explicit re-arm, out of scope). The model
    provides **no** operation mapping a generation increase to validity restoration;
    this predicate documents and fixes that absence (isomorphic to the Trustworthy
    Time ``recovery_generation_revives_nothing``).

    Args:
        invalidated_under_generation: The generation under which it was invalidated.
        new_generation: A later recovery / restore generation.

    Returns:
        ``True`` always (non-revival holds).
    """
    del invalidated_under_generation, new_generation  # no revival path exists
    return True


# ===========================================================================
# §4.4 — snapshot completeness (RCLP-INV-009)
# ===========================================================================


def snapshot_admissible_for_restore(snapshot: AuthoritativeSnapshot) -> bool:
    """Whether a snapshot is admissible for authoritative restore (§4.4; INV-009).

    Fail-closed: a snapshot missing **any** completeness element (non-terminal
    reservations, command-idempotency keys, generation fences, capability-use state,
    proof-gated release state, or the history / integrity commitment) is inadmissible
    (ADR-012 §21 line 528 "Snapshot missing idempotency or capability-use state =>
    reject snapshot for authoritative restore"). A restored older snapshot never
    becomes authoritative merely because it is the newest backup (§17.4 line 455).

    Args:
        snapshot: The authoritative snapshot.

    Returns:
        ``True`` iff every completeness element is present.
    """
    return not snapshot.completeness.missing_elements()
