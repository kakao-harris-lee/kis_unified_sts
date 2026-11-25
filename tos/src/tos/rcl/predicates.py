"""Pure RCL predicates (RCL design §4, §5, §6)."""

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


def within_limits(
    effect: CapacityVector,
    limits: CapacityVector,
    applicable_dimensions: Sequence[str],
) -> bool:
    """Whether ``effect`` is within ``limits`` on every applicable dimension (§5.1 r3)."""
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
    """Reduce ``base_vector`` by a claimed benefit **only when positively proven** (§5.1 r2)."""
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
            new_magnitude = base_magnitude
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


_LIVE_COMMITTED_STATES: frozenset[CapacityState] = frozenset(
    s for s in CapacityState if s is not CapacityState.RELEASED
)


def committed_usage(state: LedgerState) -> CapacityVector:
    """Aggregate committed usage over non-released reservations (INV-001)."""
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
    """Headroom = limit - committed usage per applicable dimension, or ``None`` (§5.2)."""
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
                return None
        else:
            used = Decimal(0)
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
    """Deterministic fold of one committed command onto ledger state (§5.2)."""
    command_identity = command.command_identity
    canonical_digest = command.canonical_digest
    if command_identity is None or canonical_digest is None:
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
            return ApplyOutcome(
                state=state,
                admitted=prior.admitted,
                reason=ApplyReason.IDEMPOTENT_REPLAY,
            )
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
    """Fold an ordered command sequence to a final ledger state (§5.2 determinism)."""
    state = initial_state
    for command in commands:
        state = apply_committed(
            state,
            command,
            limits=limits,
            applicable_dimensions=applicable_dimensions,
        ).state
    return state


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
    """Whether a capacity-state transition is allowed under ``cause`` (§5.4; §10.2)."""
    if from_state is CapacityState.RELEASED:
        return False
    if to_state is CapacityState.RELEASED:
        return cause is TransitionCause.FINAL_QUANTITY_PROOF
    if _CONSERVATISM_RANK[to_state] >= _CONSERVATISM_RANK[from_state]:
        return True
    return cause not in WEAK_CAUSES


def capacity_at_least_as_conservative(a: CapacityState, b: CapacityState) -> bool:
    """Whether capacity state ``a`` is at least as conservative as ``b`` (design #8 §3.4)."""
    return _CONSERVATISM_RANK[a] >= _CONSERVATISM_RANK[b]


def writer_fenced(
    coords: FenceCoordinates,
    fence_state: WriterFenceState,
) -> bool:
    """Whether a command / capability is FENCED (rejected) (§6.1; RCLP-INV-004)."""
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


def grants_no_authority(authority_block: object) -> bool:
    """Whether an authority block grants nothing — every flag ``False`` (§4.1)."""
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
    """Whether a grant authorizes exactly this committed reservation (§4.1 layer 3)."""
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
    """Whether a capability authorization is valid (§6.4; ADR-012 §11 line 317-329)."""
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
    """Claim a capability, consuming its nonce **exactly once** (§6.4; ADR-012 §12)."""
    if nonce is None:
        return ClaimOutcome(consumed_now=False, replay=False, result=None)
    for prior in prior_claims:
        if prior.nonce == nonce:
            return ClaimOutcome(consumed_now=False, replay=True, result=prior.result)
    return ClaimOutcome(consumed_now=True, replay=False, result=result)


def partition_verdict(quorum_available: bool | None) -> PartitionVerdict:
    """The per-action verdict under (loss of) quorum (§6.5; ADR-012 §15 line 389-401)."""
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
    """Worst credible union of reconstructable histories (§6.5; ADR-012 §18 line 472)."""
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
    """Whether a new generation revives an earlier invalidation — never (§6.5; INV-011)."""
    del invalidated_under_generation, new_generation
    return True


def snapshot_admissible_for_restore(snapshot: AuthoritativeSnapshot) -> bool:
    """Whether a snapshot is admissible for authoritative restore (§4.4; INV-009)."""
    return not snapshot.completeness.missing_elements()
