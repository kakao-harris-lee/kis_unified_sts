"""RCL predicate-input / output state models (ADR-002-012 §5, §9, §13, §15, §17).

Plain frozen models that carry the *injected* state the pure predicates fold over
(RCL design §0.2: everything is a pure function over injected state — no consensus,
persistence, or egress). None derives an id; none mutates in place (append-only,
§4.2).

Pure module: ``pydantic`` + stdlib + ``tos.rcl`` only; no ``shared.*`` (§0.3).
"""

from __future__ import annotations

from tos.rcl._base import FrozenModel
from tos.rcl.vector import CapacityVector
from tos.rcl.vocabulary import ApplyReason, CapacityState


class FenceCoordinates(FrozenModel):
    """The currentness coordinates a command / capability binds (ADR-012 §9 line 259).

    ``expected Writer Epoch, membership generation, and Restore Generation`` plus the
    ``expected revision`` (§9 line 260). Any ``None`` coordinate is UNKNOWN — the
    fence predicate cannot prove currentness and therefore FENCES (fail-closed,
    §6.1).
    """

    expected_writer_epoch: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    expected_revision: int | None = None


class WriterFenceState(FrozenModel):
    """The monotone floors + current revision an injected fence state carries (§6.2).

    ``writer_epoch_floor`` / ``membership_generation`` / ``restore_generation`` never
    regress (ADR-012 §5.5 line 129, §5.7 line 139, §13 line 353); ``revision`` is the
    current committed Log Revision (§5.6 line 135) used for CAS. A ``None`` floor is
    UNKNOWN — currentness is unprovable, so the fence predicate FENCES (§6.1).
    """

    writer_epoch_floor: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    revision: int | None = None


class CommittedReservation(FrozenModel):
    """A reservation as it exists in committed ledger state (reducer element).

    Carries only what the aggregate-envelope reducer and the capacity->capability
    binding predicate need: the independent ``reservation_id``, its committed
    ``current_reservation_revision`` and ``canonical_record_digest`` (the exact
    coordinates a grant / capability binds to, §4.1 layer 3 / §6.4), the committed
    ``adverse_increment`` Capacity Vector it consumes, whether an attempt is bound
    and unused, and the current ``capacity_state``. Released reservations consume no
    capacity (aggregate skips ``RELEASED``).
    """

    reservation_id: str | None = None
    current_reservation_revision: int | None = None
    canonical_record_digest: str | None = None
    adverse_increment: CapacityVector = CapacityVector()
    capacity_state: CapacityState = CapacityState.COMMITTED_UNBOUND
    attempt_bound: bool = False
    attempt_unused: bool = True


class AppliedCommand(FrozenModel):
    """A record of a command already folded into ledger state (idempotency key).

    ``command_identity`` + ``canonical_command_digest`` are the idempotency key
    (RCLP-INV-006 line 169-171): a replay with the same identity + same digest
    returns the same ``admitted`` result without a duplicate transition; the same
    identity + different digest is a Critical conflict (ADR-012 §9 line 270).
    ``resulting_revision`` is the committed revision after this command.
    """

    command_identity: str | None = None
    canonical_command_digest: str | None = None
    admitted: bool = False
    resulting_revision: int | None = None


class LedgerState(FrozenModel):
    """The committed capacity state the deterministic reducer folds over (§5.2).

    A pure fold accumulator: ``revision`` is the current CAS token (advances only on
    an admitted mutation — a rejection changes no state); ``committed`` is the tuple
    of committed reservations (aggregate usage is derived from it, never from a
    producer-local counter — §11.2 step 10 line 594); ``applied_commands`` is the
    append-only idempotency ledger. Frozen + append-only: the reducer returns a new
    state, never mutates one (§4.2).
    """

    revision: int = 0
    committed: tuple[CommittedReservation, ...] = ()
    applied_commands: tuple[AppliedCommand, ...] = ()


class ApplyOutcome(FrozenModel):
    """The result of applying one command to ledger state (reducer output, §5.2)."""

    state: LedgerState
    admitted: bool
    reason: ApplyReason


class PartitionVerdict(FrozenModel):
    """Per-action allow/preserve verdict under (loss of) quorum (ADR-012 §15).

    ``*_denied`` flags are the §15 line 390-396 DENIED set; ``*_preserved`` flags are
    the line 399-401 PRESERVED set (always ``True`` — committed effects never
    vanish, and quorum loss neither creates nor replenishes capacity, RCLP-INV-008).
    Under loss of quorum every ``*_denied`` flag is ``True`` (fail-closed).
    """

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
    """A recorded capability claim (nonce consumed once; ADR-012 §12 line 340-343).

    The nonce is consumed exactly once; every later duplicate claim returns this
    original committed ``result`` without creating another send authority (§12 line
    343).
    """

    nonce: str | None = None
    capability_id: str | None = None
    result: str | None = None


class ClaimOutcome(FrozenModel):
    """The result of a capability claim (ADR-012 §12).

    ``consumed_now`` is ``True`` only on the first claim of a nonce; a later claim is
    a ``replay`` returning the original ``result`` (no new send authority).
    """

    consumed_now: bool
    replay: bool
    result: str | None = None


class CredibleHistory(FrozenModel):
    """One reconstructable history in a disaster-recovery union (ADR-012 §18 line 472).

    ``capacity`` is the history's Capacity Vector; ``bounded`` is whether the history
    state is admitted by the active Broker Capability Profile + approved Adverse
    Scenario Set (the Credible State Space). A history **not** bounded is treated
    conservatively as UNKNOWN and capacity-consuming, never dropped (§18 line 472).
    """

    history_id: str | None = None
    capacity: CapacityVector = CapacityVector()
    bounded: bool = False
