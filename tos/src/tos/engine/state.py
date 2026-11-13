"""Provisional, **non-authoritative** reservation projection (design #31 §2.4 / §4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tos.engine._base import ArtifactIntegrityError, FrozenModel
from tos.engine.records import (
    EgressResultPayload,
    InstrumentKey,
    ProvisionalReservation,
    UnsentDiscardRef,
)
from tos.engine.vocabulary import (
    TERMINAL_RESULT_KINDS,
    EgressKnowledge,
    EgressResultKind,
    ResultDisposition,
)
from tos.rcl import CapacityState

__all__ = [
    "PROJECTION_ORDER",
    "PROJECTION_RANK",
    "QUARANTINE_RESOLUTION_EDGES",
    "FinalityProofRef",
    "ProvisionalReservationLedger",
    "ResultApplication",
    "knowledge_for_result",
]


PROJECTION_ORDER: tuple[CapacityState, ...] = (
    CapacityState.COMMITTED_UNBOUND,
    CapacityState.ATTEMPT_BOUND,
    CapacityState.POTENTIALLY_LIVE,
    CapacityState.PARTIALLY_CONSUMED,
    CapacityState.POSITION_CONSUMED,
    CapacityState.RELEASE_PENDING_PROOF,
    CapacityState.QUARANTINED_UNKNOWN,
    CapacityState.RELEASED,
)

PROJECTION_RANK: dict[CapacityState, int] = {
    state: rank for rank, state in enumerate(PROJECTION_ORDER)
}

_RESULT_TRANSITIONS: dict[
    EgressResultKind, tuple[EgressKnowledge, CapacityState | None]
] = {
    EgressResultKind.ACK: (EgressKnowledge.ACKNOWLEDGED, None),
    EgressResultKind.FULL_FILL: (
        EgressKnowledge.FILLED,
        CapacityState.POSITION_CONSUMED,
    ),
    EgressResultKind.PARTIAL_FILL: (
        EgressKnowledge.PARTIALLY_FILLED,
        CapacityState.PARTIALLY_CONSUMED,
    ),
    EgressResultKind.REJECT: (
        EgressKnowledge.REJECTED,
        CapacityState.RELEASE_PENDING_PROOF,
    ),
    EgressResultKind.UNKNOWN: (
        EgressKnowledge.UNKNOWN,
        CapacityState.QUARANTINED_UNKNOWN,
    ),
    EgressResultKind.TIMEOUT: (
        EgressKnowledge.UNKNOWN,
        CapacityState.QUARANTINED_UNKNOWN,
    ),
    EgressResultKind.CANCEL_ACK: (
        EgressKnowledge.CANCEL_ACKNOWLEDGED,
        CapacityState.RELEASE_PENDING_PROOF,
    ),
    EgressResultKind.EXPIRED: (
        EgressKnowledge.EXPIRED,
        CapacityState.RELEASE_PENDING_PROOF,
    ),
}

QUARANTINE_RESOLUTION_EDGES: dict[EgressResultKind, CapacityState] = {
    EgressResultKind.ACK: CapacityState.POTENTIALLY_LIVE,
    EgressResultKind.PARTIAL_FILL: CapacityState.PARTIALLY_CONSUMED,
    EgressResultKind.FULL_FILL: CapacityState.POSITION_CONSUMED,
    EgressResultKind.REJECT: CapacityState.RELEASE_PENDING_PROOF,
    EgressResultKind.CANCEL_ACK: CapacityState.RELEASE_PENDING_PROOF,
    EgressResultKind.EXPIRED: CapacityState.RELEASE_PENDING_PROOF,
}


_RELEASABLE_KNOWLEDGE: frozenset[EgressKnowledge] = frozenset(
    _RESULT_TRANSITIONS[kind][0] for kind in TERMINAL_RESULT_KINDS
)


class FinalityProofRef(FrozenModel):
    """The finality-proof token gating :meth:`ProvisionalReservationLedger.release` (kernel round"""

    attempt_id: str
    proof_digest: str
    evidence_seq: int
    resolution_generation: int


_DISCARDABLE_CAPACITY: frozenset[CapacityState] = frozenset(
    {CapacityState.COMMITTED_UNBOUND, CapacityState.ATTEMPT_BOUND}
)


def knowledge_for_result(kind: EgressResultKind) -> EgressKnowledge:
    """The knowledge axis an egress result establishes (design #31 §2.4)."""
    mapped = _RESULT_TRANSITIONS.get(kind)
    if mapped is None:
        raise ArtifactIntegrityError(
            f"no closed transition is declared for egress result kind {kind!r} (fail-closed)"
        )
    return mapped[0]


@dataclass(frozen=True)
class ResultApplication:
    """The recorded, conservative outcome of one ``apply_egress_result`` call (Phase 3 A-K-2)."""

    applied: bool
    disposition: ResultDisposition
    projection: ProvisionalReservation | None


class ProvisionalReservationLedger:
    """The engine's in-memory, non-authoritative reservation projection (design #31 §4.4)."""

    def __init__(self, *, max_unresolved_send_per_scope: int) -> None:
        """Create an empty projection."""
        if max_unresolved_send_per_scope < 0:
            raise ArtifactIntegrityError(
                "max_unresolved_send_per_scope must be non-negative — a negative bound is not a "
                f"bound (got {max_unresolved_send_per_scope})"
            )
        self._max_unresolved = max_unresolved_send_per_scope
        self._reservations: dict[tuple[str, str], ProvisionalReservation] = {}
        self._applied_result_signatures: dict[
            tuple[str, str], tuple[tuple[object, ...], ...]
        ] = {}
        self._released_attempt_ids: dict[tuple[str, str], set[str]] = {}

    @staticmethod
    def _key_tuple(key: InstrumentKey) -> tuple[str, str]:
        """The hashable form of an :class:`~tos.engine.records.InstrumentKey`."""
        return (key.account, key.instrument)

    def outstanding(self, key: InstrumentKey) -> ProvisionalReservation | None:
        """The unresolved reservation projected for ``key``, if any."""
        reservation = self._reservations.get(self._key_tuple(key))
        if (
            reservation is not None
            and reservation.capacity_state is CapacityState.RELEASED
        ):
            return None
        return reservation

    def outstanding_count(self, key: InstrumentKey) -> int:
        """How many unresolved (never ``RELEASED``) reservations the projection holds for ``key``."""
        return len(
            [
                reservation
                for reservation in (self.outstanding(key),)
                if reservation is not None
            ]
        )

    def outstanding_consumed_magnitude(self, key: InstrumentKey) -> Decimal | None:
        """The already-recorded consumed magnitude of ``key``'s outstanding reservation (§35 §5.2)."""
        outstanding = self.outstanding(key)
        return None if outstanding is None else outstanding.filled_quantity

    def admits_new_exposure(self, key: InstrumentKey) -> bool:
        """Whether a **new** overlapping economic effect may be requested for ``key``."""
        return self.outstanding_count(key) < self._max_unresolved

    def release(self, ref: FinalityProofRef) -> bool:
        """Release the reservation ``ref.attempt_id`` names — the **only** release path (kernel"""
        if not isinstance(ref, FinalityProofRef):
            raise TypeError(
                "ProvisionalReservationLedger.release requires a FinalityProofRef — got "
                f"{type(ref).__name__} (kernel round #3 §2 decision 5: release is a finality-"
                "proof-token gate only, never a response kind or a bare string)"
            )
        for reservation in self._reservations.values():
            if reservation.attempt_id != ref.attempt_id:
                continue
            if reservation.capacity_state is CapacityState.RELEASED:
                return False
            if reservation.knowledge not in _RELEASABLE_KNOWLEDGE:
                return False
            self._store(
                reservation.model_copy(
                    update={"capacity_state": CapacityState.RELEASED}
                )
            )
            self._released_attempt_ids.setdefault(
                self._key_tuple(reservation.instrument_key), set()
            ).add(ref.attempt_id)
            return True
        return False

    def discard_unsent(self, ref: UnsentDiscardRef) -> bool:
        """Drop a reservation that was committed but **never sent** (plan §3.2; issue #974)."""
        if not isinstance(ref, UnsentDiscardRef):
            raise TypeError(
                "ProvisionalReservationLedger.discard_unsent requires an UnsentDiscardRef — got "
                f"{type(ref).__name__} (the discard is a typed-token gate only, never a bare "
                "proposal id and never the FinalityProofRef that gates release)"
            )
        for key_tuple, reservation in tuple(self._reservations.items()):
            if reservation.proposal_id != ref.proposal_id:
                continue
            if reservation.knowledge is not EgressKnowledge.NOT_SENT:
                return False
            if reservation.capacity_state not in _DISCARDABLE_CAPACITY:
                return False
            if reservation.attempt_id is not None and any(
                signature[0] == reservation.attempt_id
                for signature in self._applied_result_signatures.get(key_tuple, ())
            ):
                return False
            del self._reservations[key_tuple]
            return True
        return False

    def _store(
        self,
        reservation: ProvisionalReservation,
        *,
        allow_quarantine_resolution: bool = False,
    ) -> ProvisionalReservation:
        """Store a reservation projection, enforcing forward-only (non-revival) advance."""
        key_tuple = self._key_tuple(reservation.instrument_key)
        if (
            reservation.attempt_id is not None
            and reservation.attempt_id in self._released_attempt_ids.get(key_tuple, ())
        ):
            raise ArtifactIntegrityError(
                f"attempt_id {reservation.attempt_id!r} has already reached RELEASED for scope "
                f"{key_tuple} — a released attempt may never transition again, even after the "
                "scope has since reopened for a new attempt (non-revival; kernel round #3 §2 "
                "decision 5b)"
            )
        current = self._reservations.get(key_tuple)
        if current is not None:
            reopening_a_released_scope = (
                current.capacity_state is CapacityState.RELEASED
            )
            if not reopening_a_released_scope:
                current_rank = PROJECTION_RANK[current.capacity_state]
                next_rank = PROJECTION_RANK[reservation.capacity_state]
                resolving_quarantine = (
                    allow_quarantine_resolution
                    and current.capacity_state is CapacityState.QUARANTINED_UNKNOWN
                )
                if next_rank < current_rank and not resolving_quarantine:
                    raise ArtifactIntegrityError(
                        "provisional capacity projection may not revive to a less-consumed state "
                        f"({current.capacity_state} -> {reservation.capacity_state}) — "
                        "non-revival (ADR-002-002 §10.1; design #31 §2.4)"
                    )
        self._reservations[key_tuple] = reservation
        return reservation

    def commit_unbound(
        self, key: InstrumentKey, *, proposal_id: str | None
    ) -> ProvisionalReservation:
        """Project the ADR-002-002 §11 step-9 atomic commit as ``COMMITTED_UNBOUND``."""
        if not self.admits_new_exposure(key):
            raise ArtifactIntegrityError(
                f"scope {self._key_tuple(key)} already holds an unresolved reservation — the "
                "at-most-one exposure retention denies an overlapping economic effect "
                "(SAFE-021 provisional mirror; design #31 §4.4)"
            )
        return self._store(
            ProvisionalReservation(
                instrument_key=key,
                capacity_state=CapacityState.COMMITTED_UNBOUND,
                knowledge=EgressKnowledge.NOT_SENT,
                proposal_id=proposal_id,
            )
        )

    def bind_attempt(
        self, key: InstrumentKey, *, attempt_id: str
    ) -> ProvisionalReservation:
        """Project ADR-002-002 §11 step 14 as ``ATTEMPT_BOUND`` (issuing no capability)."""
        current = self.outstanding(key)
        if current is None:
            raise ArtifactIntegrityError(
                f"no projected reservation for scope {self._key_tuple(key)} — an attempt cannot "
                "bind to nothing (fail-closed)"
            )
        return self._store(
            current.model_copy(
                update={
                    "capacity_state": CapacityState.ATTEMPT_BOUND,
                    "attempt_id": attempt_id,
                }
            )
        )

    def mark_potentially_live(self, key: InstrumentKey) -> ProvisionalReservation:
        """Conservatively project ``POTENTIALLY_LIVE`` **before** the attempt leaves the core."""
        current = self.outstanding(key)
        if current is None:
            raise ArtifactIntegrityError(
                f"no projected reservation for scope {self._key_tuple(key)} — nothing to mark "
                "potentially live (fail-closed)"
            )
        return self._store(
            current.model_copy(
                update={
                    "capacity_state": CapacityState.POTENTIALLY_LIVE,
                    "knowledge": EgressKnowledge.SENT_UNCONFIRMED,
                }
            )
        )

    @staticmethod
    def _quantity_regressed(
        current: ProvisionalReservation, payload: EgressResultPayload
    ) -> bool:
        """Whether ``payload`` would regress the quantity axis of ``current`` (§35 K2-p3-#5 / N2;"""
        if payload.kind not in (
            EgressResultKind.FULL_FILL,
            EgressResultKind.PARTIAL_FILL,
        ):
            return False
        if current.filled_quantity is None or current.remaining_quantity is None:
            return False
        assert payload.filled_quantity is not None
        assert payload.remaining_quantity is not None
        if payload.filled_quantity < current.filled_quantity:
            return True
        if payload.remaining_quantity > current.remaining_quantity:
            return True
        authorized_total = current.filled_quantity + current.remaining_quantity
        return payload.filled_quantity + payload.remaining_quantity != authorized_total

    @staticmethod
    def _resolve_capacity_target(
        current: ProvisionalReservation, payload: EgressResultPayload
    ) -> tuple[CapacityState | None, bool] | ResultDisposition:
        """The capacity target for ``payload`` against ``current``, or the rank-guard refusal."""
        _, capacity_state = _RESULT_TRANSITIONS[payload.kind]
        resolving_quarantine = (
            current.capacity_state is CapacityState.QUARANTINED_UNKNOWN
            and payload.kind in QUARANTINE_RESOLUTION_EDGES
        )
        if resolving_quarantine:
            table_target = QUARANTINE_RESOLUTION_EDGES[payload.kind]
            floor = current.pre_quarantine_capacity
            if (
                floor is not None
                and PROJECTION_RANK[floor] > PROJECTION_RANK[table_target]
            ):
                return floor, True
            return table_target, True
        if capacity_state is not None:
            current_rank = PROJECTION_RANK[current.capacity_state]
            next_rank = PROJECTION_RANK[capacity_state]
            if next_rank < current_rank:
                return ResultDisposition.NON_MONOTONIC_PROJECTION
        return capacity_state, False

    @staticmethod
    def _pre_quarantine_floor_update(
        current: ProvisionalReservation,
        capacity_state: CapacityState,
        resolving_quarantine: bool,
    ) -> CapacityState | None:
        """The next ``pre_quarantine_capacity`` value to store (Phase 3 wave 2 KW2c-R2)."""
        if capacity_state is CapacityState.QUARANTINED_UNKNOWN:
            if current.capacity_state is CapacityState.QUARANTINED_UNKNOWN:
                return current.pre_quarantine_capacity
            return current.capacity_state
        if resolving_quarantine:
            return None
        return current.pre_quarantine_capacity

    def apply_egress_result(self, payload: EgressResultPayload) -> ResultApplication:
        """Apply — or conservatively record — a re-injected egress result (Phase 3 A-K-2)."""
        key = payload.instrument_key
        key_tuple = self._key_tuple(key)
        current = self.outstanding(key)
        if current is None:
            return ResultApplication(
                applied=False,
                disposition=ResultDisposition.ORPHAN_NO_RESERVATION,
                projection=None,
            )
        if current.attempt_id is None or current.attempt_id != payload.attempt_id:
            return ResultApplication(
                applied=False,
                disposition=ResultDisposition.MISMATCHED_ATTEMPT,
                projection=current,
            )
        signature = (
            payload.attempt_id,
            payload.kind,
            payload.filled_quantity,
            payload.remaining_quantity,
            payload.broker_execution_id,
            payload.resolution_generation,
        )
        applied_signatures = self._applied_result_signatures.get(key_tuple, ())
        if signature in applied_signatures:
            return ResultApplication(
                applied=False,
                disposition=ResultDisposition.DUPLICATE,
                projection=current,
            )
        knowledge, _ = _RESULT_TRANSITIONS[payload.kind]
        target = self._resolve_capacity_target(current, payload)
        if isinstance(target, ResultDisposition):
            return ResultApplication(
                applied=False,
                disposition=target,
                projection=current,
            )
        capacity_state, resolving_quarantine = target
        if self._quantity_regressed(current, payload):
            return ResultApplication(
                applied=False,
                disposition=ResultDisposition.QUANTITY_REGRESSION,
                projection=current,
            )
        update: dict[str, object] = {"knowledge": knowledge}
        if capacity_state is not None:
            update["capacity_state"] = capacity_state
            update["pre_quarantine_capacity"] = self._pre_quarantine_floor_update(
                current, capacity_state, resolving_quarantine
            )
        if payload.kind in (EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL):
            update["filled_quantity"] = payload.filled_quantity
            update["remaining_quantity"] = payload.remaining_quantity
        stored = self._store(
            current.model_copy(update=update),
            allow_quarantine_resolution=resolving_quarantine,
        )
        self._applied_result_signatures[key_tuple] = applied_signatures + (signature,)
        return ResultApplication(
            applied=True, disposition=ResultDisposition.APPLIED, projection=stored
        )
