"""Provisional, **non-authoritative** reservation projection (design #31 §2.4 / §4.4).

⚠ **NON-AUTHORITATIVE PROVISIONAL.** This module is not the Risk Capacity Ledger. The real RCL is
a single-writer, fencing-epoch, CAS-linearizable ledger (ADR-002-002 §8.1:403 / §8.3:434 /
§8.4:449) and is the **sole** serialization and mutation authority (RFC-002 §9.1:557). What lives
here is an in-memory *projection* of the ADR-002-002 §10.1 capacity-state vocabulary onto one
(account, instrument) scope, held so the single event core can observe an outstanding exposure. It
asserts no linearizability, no fencing epoch, no crash recovery, and no atomicity, and it closes
**no** capacity or approval EV (design #31 §1.1/§4.4).

Two structural properties carry the design's weight:

* **At-most-one exposure retention (design #31 §4.4, MAJOR-1).** An unresolved outstanding
  reservation for a scope makes the *next* overlapping economic-effect request for that scope
  deny at the capacity stage. That closes the re-entrancy window a synchronous core still has
  **between events**: a second ``DECISION_TICK`` arriving between the send hand-off and the
  ``EGRESS_RESULT`` cannot create an overlapping exposure (§2.1(iv); the provisional mirror of
  SAFE-021 At-Most-One Exposure Effect, RFC-005 §11:319-343 / §12 item 7 :364-365; ADR-002-002
  INV-006:174). The bound is the **injected** ``MAX_unresolved_send_per_scope`` (register §3:90),
  never a literal.

* **No release path at all.** There is deliberately no ``release`` / ``free`` / ``clear`` method.
  Releasing capacity is an RCL act (ADR-002-002 §10.1 / RFC-002 §9.1:557), and a producer-local
  counter "SHALL NOT create headroom" (RFC-002 §9.1:558). So no egress result — not an
  acknowledgement, not a full fill, not a rejection — ever frees a scope here. The projection only
  advances forward along a conservatism-ordered rank; an ``UNKNOWN`` / timeout keeps the capacity
  projection at ``POTENTIALLY_LIVE`` and re-submits nothing (design #31 §4.2 rule 3; ADR-002-002
  INV-005:168 — a crash after ``SEND_STARTED`` must not release capacity). The honest consequence
  is that a slice-1 scope stays occupied for the lifetime of the projection; real release is
  deferred with the RCL runtime (design #31 §9-2).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from decimal import Decimal

from tos.engine._base import ArtifactIntegrityError
from tos.engine.records import (
    EgressResultPayload,
    InstrumentKey,
    ProvisionalReservation,
)
from tos.engine.vocabulary import EgressKnowledge, EgressResultKind
from tos.rcl import CapacityState

__all__ = [
    "PROJECTION_ORDER",
    "PROJECTION_RANK",
    "ProvisionalReservationLedger",
    "knowledge_for_result",
]


#: The conservatism-forward order of the capacity states this projection uses (design #31 §2.4),
#: least-settled first. A transition may only move to an equal-or-later position — non-revival, the
#: series discipline. ``RELEASE_PENDING_PROOF`` sits last because a proven rejection still awaits
#: the RCL-owned release proof; ``RELEASED`` is **absent**, because this projection cannot release.
PROJECTION_ORDER: tuple[CapacityState, ...] = (
    CapacityState.COMMITTED_UNBOUND,
    CapacityState.ATTEMPT_BOUND,
    CapacityState.POTENTIALLY_LIVE,
    CapacityState.PARTIALLY_CONSUMED,
    CapacityState.POSITION_CONSUMED,
    CapacityState.RELEASE_PENDING_PROOF,
)

#: The rank, derived structurally from :data:`PROJECTION_ORDER` so the two can never drift.
PROJECTION_RANK: dict[CapacityState, int] = {
    state: rank for rank, state in enumerate(PROJECTION_ORDER)
}

#: How an egress result maps onto the two orthogonal axes (RFC-002 §12 Orthogonal Trading State).
#: The capacity projection is the *conservative* axis: only a definite settlement advances it, and
#: ``UNKNOWN`` / ``TIMEOUT`` leave it exactly where it was — ``POTENTIALLY_LIVE`` (design #31
#: §4.2 rule 3; ADR-002-002 INV-005:168 / INV-006:174).
_RESULT_TRANSITIONS: dict[EgressResultKind, tuple[EgressKnowledge, CapacityState | None]] = {
    EgressResultKind.ACK: (EgressKnowledge.ACKNOWLEDGED, None),
    EgressResultKind.FULL_FILL: (EgressKnowledge.FILLED, CapacityState.POSITION_CONSUMED),
    EgressResultKind.PARTIAL_FILL: (
        EgressKnowledge.PARTIALLY_FILLED,
        CapacityState.PARTIALLY_CONSUMED,
    ),
    EgressResultKind.REJECT: (EgressKnowledge.REJECTED, CapacityState.RELEASE_PENDING_PROOF),
    EgressResultKind.UNKNOWN: (EgressKnowledge.UNKNOWN, None),
    EgressResultKind.TIMEOUT: (EgressKnowledge.UNKNOWN, None),
}


def knowledge_for_result(kind: EgressResultKind) -> EgressKnowledge:
    """The knowledge axis an egress result establishes (design #31 §2.4).

    Args:
        kind: The re-injected egress result kind.

    Returns:
        The :class:`~tos.engine.vocabulary.EgressKnowledge` member. ``UNKNOWN`` and ``TIMEOUT``
        both map to the explicit ``UNKNOWN`` member — never to a missing value, and never to
        ``REJECTED`` (RFC-005 §11:325-327 "UNKNOWN is not a rejection").

    Raises:
        ArtifactIntegrityError: If the kind is outside the closed mapping (fail-closed).
    """
    mapped = _RESULT_TRANSITIONS.get(kind)
    if mapped is None:
        raise ArtifactIntegrityError(
            f"no closed transition is declared for egress result kind {kind!r} (fail-closed)"
        )
    return mapped[0]


class ProvisionalReservationLedger:
    """The engine's in-memory, non-authoritative reservation projection (design #31 §4.4).

    ⚠ **NON-AUTHORITATIVE PROVISIONAL** — see the module docstring. It exposes no release method,
    no capacity arithmetic, and no capability issuance; it can only observe restrictively.
    """

    def __init__(self, *, max_unresolved_send_per_scope: int) -> None:
        """Create an empty projection.

        Args:
            max_unresolved_send_per_scope: The injected ``MAX_unresolved_send_per_scope`` bound
                (register §3:90; design #31 §8). Never defaulted here — an unbounded projection
                would be a producer-local headroom source, which RFC-002 §9.1:558 forbids.

        Raises:
            ArtifactIntegrityError: If the injected bound is negative.
        """
        if max_unresolved_send_per_scope < 0:
            raise ArtifactIntegrityError(
                "max_unresolved_send_per_scope must be non-negative — a negative bound is not a "
                f"bound (got {max_unresolved_send_per_scope})"
            )
        self._max_unresolved = max_unresolved_send_per_scope
        self._reservations: dict[tuple[str, str], ProvisionalReservation] = {}

    @staticmethod
    def _key_tuple(key: InstrumentKey) -> tuple[str, str]:
        """The hashable form of an :class:`~tos.engine.records.InstrumentKey`."""
        return (key.account, key.instrument)

    # -- observation ---------------------------------------------------------

    def outstanding(self, key: InstrumentKey) -> ProvisionalReservation | None:
        """The unresolved reservation projected for ``key``, if any."""
        return self._reservations.get(self._key_tuple(key))

    def outstanding_count(self, key: InstrumentKey) -> int:
        """How many unresolved reservations the projection holds for ``key``.

        Slice #1 projects at most one per scope, so this is 0 or 1; it is expressed as a count so
        the comparison against the injected ``MAX_unresolved_send_per_scope`` bound stays explicit
        rather than hidden in a boolean.
        """
        return len(
            [
                reservation
                for reservation in (self.outstanding(key),)
                if reservation is not None
            ]
        )

    def outstanding_consumed_magnitude(self, key: InstrumentKey) -> Decimal | None:
        """The already-recorded consumed magnitude of ``key``'s outstanding reservation (§35 §5.2).

        A **read**, and nothing else. It returns the ``filled_quantity`` a re-injected egress
        result already wrote onto the projection, so a position-closing derivation can be sized
        from the position that actually exists instead of from a risk budget. Reading is neither
        serialization nor mutation, so RFC-002 §9.1:557 (the RCL is the sole such authority) is
        untouched, and it creates no headroom for anyone (§9.1:558) — the at-most-one retention is
        computed exactly as before and still denies an overlapping effect at the capacity stage.

        Deliberately **not** named ``release`` / ``free`` / ``clear`` / ``reset``: those paths do
        not exist here and this is not one of them (design #35 §5.2 / §5.3).

        ⚠ The honest scope is one entry. What is returned is the outstanding reservation's
        capacity-consumed magnitude, which coincides with the held position only while a scope
        holds at most one attempt. A full net-position ledger — multi-leg, averaged — is **not**
        this: the engine is a capacity / commitment machine, not a position ledger, and that
        generalization is deferred (design #35 §5.3).

        Args:
            key: The (account, instrument) scope.

        Returns:
            The recorded ``filled_quantity``, or ``None`` when no reservation is outstanding for
            the scope or none has been filled — an absent observation, never a zero standing in
            for one (∅ both ways).
        """
        outstanding = self.outstanding(key)
        return None if outstanding is None else outstanding.filled_quantity

    def admits_new_exposure(self, key: InstrumentKey) -> bool:
        """Whether a **new** overlapping economic effect may be requested for ``key``.

        The at-most-one retention observation (design #31 §4.4). ``True`` only when the projected
        unresolved count is strictly below the injected bound. This is a *restrictive-only*
        observation of the projection — it creates no headroom for anyone (RFC-002 §9.1:558) and
        it grants nothing; only the real RCL commits capacity.

        Args:
            key: The (account, instrument) scope.

        Returns:
            ``True`` iff the scope has room under the injected bound.
        """
        return self.outstanding_count(key) < self._max_unresolved

    # -- projection advance (no release path exists) -------------------------

    def _store(self, reservation: ProvisionalReservation) -> ProvisionalReservation:
        """Store a reservation projection, enforcing forward-only (non-revival) advance."""
        key_tuple = self._key_tuple(reservation.instrument_key)
        current = self._reservations.get(key_tuple)
        if current is not None:
            current_rank = PROJECTION_RANK[current.capacity_state]
            next_rank = PROJECTION_RANK[reservation.capacity_state]
            if next_rank < current_rank:
                raise ArtifactIntegrityError(
                    "provisional capacity projection may not revive to a less-consumed state "
                    f"({current.capacity_state} -> {reservation.capacity_state}) — non-revival "
                    "(ADR-002-002 §10.1; design #31 §2.4)"
                )
        self._reservations[key_tuple] = reservation
        return reservation

    def commit_unbound(
        self, key: InstrumentKey, *, proposal_id: str | None
    ) -> ProvisionalReservation:
        """Project the ADR-002-002 §11 step-9 atomic commit as ``COMMITTED_UNBOUND``.

        ⚠ This is a projection, not a commit: no ledger row is written, no epoch is fenced, and no
        competing actor is actually excluded (design #31 §4.4).

        Args:
            key: The (account, instrument) scope.
            proposal_id: The proposal identity the projection is bound to.

        Returns:
            The stored projection.

        Raises:
            ArtifactIntegrityError: If the scope already holds an unresolved reservation — the
                at-most-one retention (design #31 §4.4).
        """
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

    def bind_attempt(self, key: InstrumentKey, *, attempt_id: str) -> ProvisionalReservation:
        """Project ADR-002-002 §11 step 14 as ``ATTEMPT_BOUND`` (issuing no capability).

        Args:
            key: The (account, instrument) scope.
            attempt_id: The content-addressed attempt identity.

        Returns:
            The stored projection.

        Raises:
            ArtifactIntegrityError: If no reservation is projected for the scope.
        """
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
        """Conservatively project ``POTENTIALLY_LIVE`` **before** the attempt leaves the core.

        ADR-002-002 §11.4 step 16 durably records ``SEND_STARTED`` *before* the external call, and
        INV-005:168 forbids releasing capacity after it; the local write and the broker call cannot
        be globally atomic (§11 closing note). So the projection advances first and stays advanced
        even if the injected transmit raises — the engine never infers "not sent" from a failure to
        hand off (design #31 §4.2 rule 3; RFC-002 §10.7:722).

        Args:
            key: The (account, instrument) scope.

        Returns:
            The stored projection.

        Raises:
            ArtifactIntegrityError: If no reservation is projected for the scope.
        """
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

    def apply_egress_result(
        self, payload: EgressResultPayload
    ) -> ProvisionalReservation:
        """Transition the projection on a re-injected egress result (design #31 §2.2/§4.2 rule 3).

        The result is applied **only** to the exact attempt it names (positive identity), so a
        late, duplicated, or reordered result can never transition another attempt's reservation.
        ``UNKNOWN`` / ``TIMEOUT`` update only the knowledge axis and leave the capacity projection
        at ``POTENTIALLY_LIVE``: not a rejection, not safe-to-retry, capacity not released
        (RFC-005 §11:325-327; ADR-002-002 INV-005:168 / INV-006:174).

        Args:
            payload: The egress result payload.

        Returns:
            The stored projection.

        Raises:
            ArtifactIntegrityError: If no reservation is projected for the scope, or if the
                payload's ``attempt_id`` does not match the projected attempt identity.
        """
        key = payload.instrument_key
        current = self.outstanding(key)
        if current is None:
            raise ArtifactIntegrityError(
                f"no projected reservation for scope {self._key_tuple(key)} — an egress result is "
                "not a licence to create one (fail-closed; design #31 §2.2)"
            )
        if current.attempt_id is None or current.attempt_id != payload.attempt_id:
            raise ArtifactIntegrityError(
                f"egress result names attempt {payload.attempt_id!r} but the projected reservation "
                f"is bound to {current.attempt_id!r} — a result applies only to its exact attempt "
                "(positive identity; design #31 §2.1(ii))"
            )
        knowledge, capacity_state = _RESULT_TRANSITIONS[payload.kind]
        update: dict[str, object] = {"knowledge": knowledge}
        if capacity_state is not None:
            update["capacity_state"] = capacity_state
        if payload.kind in (EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL):
            update["filled_quantity"] = payload.filled_quantity
            update["remaining_quantity"] = payload.remaining_quantity
        return self._store(current.model_copy(update=update))
