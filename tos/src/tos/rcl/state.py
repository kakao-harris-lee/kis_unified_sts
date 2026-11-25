"""RCL predicate-input / output state models (ADR-002-012 §5, §9, §13, §15, §17)."""

from __future__ import annotations

from tos.rcl._base import FrozenModel
from tos.rcl.vector import CapacityVector
from tos.rcl.vocabulary import ApplyReason, CapacityState


class FenceCoordinates(FrozenModel):
    """The currentness coordinates a command / capability binds (ADR-012 §9 line 259)."""

    expected_writer_epoch: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    expected_revision: int | None = None


class WriterFenceState(FrozenModel):
    """The monotone floors + current revision an injected fence state carries (§6.2)."""

    writer_epoch_floor: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    revision: int | None = None


class CommittedReservation(FrozenModel):
    """A reservation as it exists in committed ledger state (reducer element)."""

    reservation_id: str | None = None
    current_reservation_revision: int | None = None
    canonical_record_digest: str | None = None
    adverse_increment: CapacityVector = CapacityVector()
    capacity_state: CapacityState = CapacityState.COMMITTED_UNBOUND
    attempt_bound: bool = False
    attempt_unused: bool = True


class AppliedCommand(FrozenModel):
    """A record of a command already folded into ledger state (idempotency key)."""

    command_identity: str | None = None
    canonical_command_digest: str | None = None
    admitted: bool = False
    resulting_revision: int | None = None


class LedgerState(FrozenModel):
    """The committed capacity state the deterministic reducer folds over (§5.2)."""

    revision: int = 0
    committed: tuple[CommittedReservation, ...] = ()
    applied_commands: tuple[AppliedCommand, ...] = ()


class ApplyOutcome(FrozenModel):
    """The result of applying one command to ledger state (reducer output, §5.2)."""

    state: LedgerState
    admitted: bool
    reason: ApplyReason


class PartitionVerdict(FrozenModel):
    """Per-action allow/preserve verdict under (loss of) quorum (ADR-012 §15)."""

    new_mutation_denied: bool
    capability_authorization_denied: bool
    capability_claim_denied: bool
    transmission_denied: bool
    capacity_release_denied: bool
    membership_change_denied: bool
    automatic_rearm_denied: bool
    committed_effects_preserved: bool = True
    potentially_live_preserved: bool = True
    unknown_preserved: bool = True
    trapped_preserved: bool = True
    protective_preserved: bool = True


class ClaimRecord(FrozenModel):
    """A recorded capability claim (nonce consumed once; ADR-012 §12 line 340-343)."""

    nonce: str | None = None
    capability_id: str | None = None
    result: str | None = None


class ClaimOutcome(FrozenModel):
    """The result of a capability claim (ADR-012 §12)."""

    consumed_now: bool
    replay: bool
    result: str | None = None


class CredibleHistory(FrozenModel):
    """One reconstructable history in a disaster-recovery union (ADR-012 §18 line 472)."""

    history_id: str | None = None
    capacity: CapacityVector = CapacityVector()
    bounded: bool = False
