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
  advances forward along a conservatism-ordered rank; an ``UNKNOWN`` / timeout forces the capacity
  projection into ``QUARANTINED_UNKNOWN`` (Phase 3 wave 2 KW2b-#2; ADR-002-005 §7 "``UNKNOWN`` here
  forces ``QUARANTINED_UNKNOWN`` in the Capacity dimension until resolved") and re-submits nothing
  (design #31 §4.2 rule 3; ADR-002-002 INV-005:168 — a crash after ``SEND_STARTED`` must not
  release capacity). Escaping the quarantine happens only through the closed
  :data:`QUARANTINE_RESOLUTION_EDGES` table — positive broker evidence for the exact attempt, never
  a bare repeated ``UNKNOWN`` / ``TIMEOUT`` (ADR-002-002 §18.6 "escaping quarantine requires
  evidence, never assertion"). The honest consequence is that a slice-1 scope stays occupied for
  the lifetime of the projection; real release is deferred with the RCL runtime (design #31 §9-2).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tos.engine._base import ArtifactIntegrityError
from tos.engine.records import (
    EgressResultPayload,
    InstrumentKey,
    ProvisionalReservation,
)
from tos.engine.vocabulary import EgressKnowledge, EgressResultKind, ResultDisposition
from tos.rcl import CapacityState

__all__ = [
    "PROJECTION_ORDER",
    "PROJECTION_RANK",
    "QUARANTINE_RESOLUTION_EDGES",
    "ProvisionalReservationLedger",
    "ResultApplication",
    "knowledge_for_result",
]


#: The conservatism-forward order of the capacity states this projection uses (design #31 §2.4),
#: least-settled first. A transition may only move to an equal-or-later position — non-revival, the
#: series discipline. ``RELEASE_PENDING_PROOF`` sits before ``QUARANTINED_UNKNOWN`` because a
#: proven rejection still awaits the RCL-owned release proof, which is a *lesser* claim than "the
#: broker state cannot currently be determined at all"; ``QUARANTINED_UNKNOWN`` sits last —
#: strictly the most conservative member this projection ever reaches (Phase 3 wave 2 KW2b-#2) —
#: mirroring its position as the single highest entry of ``tos.rcl.predicates._CONSERVATISM_RANK``
#: (rank 8 of 9, RELEASED lowest at 0; report to the reviewer: this projection's own local rank has
#: no ``TRAPPED_CONSUMED`` member to sit below, so relative to every member it does carry,
#: ``QUARANTINED_UNKNOWN`` is placed strictly above ``RELEASE_PENDING_PROOF`` exactly as the RCL's
#: full order has it). ``RELEASED`` is **absent**, because this projection cannot release.
PROJECTION_ORDER: tuple[CapacityState, ...] = (
    CapacityState.COMMITTED_UNBOUND,
    CapacityState.ATTEMPT_BOUND,
    CapacityState.POTENTIALLY_LIVE,
    CapacityState.PARTIALLY_CONSUMED,
    CapacityState.POSITION_CONSUMED,
    CapacityState.RELEASE_PENDING_PROOF,
    CapacityState.QUARANTINED_UNKNOWN,
)

#: The rank, derived structurally from :data:`PROJECTION_ORDER` so the two can never drift.
PROJECTION_RANK: dict[CapacityState, int] = {
    state: rank for rank, state in enumerate(PROJECTION_ORDER)
}

#: How an egress result maps onto the two orthogonal axes (RFC-002 §12 Orthogonal Trading State).
#: The capacity projection is the *conservative* axis: only a definite settlement advances it in
#: the ordinary case, and ``UNKNOWN`` / ``TIMEOUT`` force it into quarantine — ``QUARANTINED_UNKNOWN``
#: — rather than leaving it at the last-observed rank (Phase 3 wave 2 KW2b-#2; design #31 §4.2
#: rule 3; ADR-002-002 INV-005:168 / INV-006:174; ADR-002-005 §7/§9). Before this fix both mapped
#: to ``None`` ("leave capacity untouched"), which under-claimed: a broker state that "cannot
#: currently be determined" (§7) is a materially different, *more* conservative fact than "still
#: whatever it last was", and CPL-5 (ADR-002-005 §10) requires the exact value.
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
    # ★ [KW2-C1] CANCEL_ACK / EXPIRED (Phase 3 wave 2 §2.2): both are broker-observed, but
    # neither is a release. ADR-002-002 §16.2 "Cancel Acknowledgement moves the reservation to
    # RELEASE_PENDING_PROOF unless the broker capability profile proves ... Final Quantity
    # Proof" and CPL-4 "cancel is not release" (ADR-002-005 §10) apply identically to EXPIRED
    # per the plan's explicit instruction — the projection may advance only as far as
    # ``RELEASE_PENDING_PROOF``, never to a released state (which this projection cannot reach
    # at all — see the module docstring "no release path"). A late/duplicate/reordered
    # cancel-or-expiry is handled by the same rank/quantity non-revival machinery below as
    # every other result kind — no special-casing required here.
    EgressResultKind.CANCEL_ACK: (
        EgressKnowledge.CANCEL_ACKNOWLEDGED,
        CapacityState.RELEASE_PENDING_PROOF,
    ),
    EgressResultKind.EXPIRED: (
        EgressKnowledge.EXPIRED,
        CapacityState.RELEASE_PENDING_PROOF,
    ),
}

#: The closed, frozen set of egress results whose positive broker evidence may pull the
#: projection back **out** of ``QUARANTINED_UNKNOWN`` (Phase 3 wave 2 KW2b-#2). Consulted in
#: :meth:`ProvisionalReservationLedger.apply_egress_result` *before* the generic rank-regression
#: guard — resolution is deliberately the one exception to "a transition may only move to an
#: equal-or-later position", because ``QUARANTINED_UNKNOWN`` is the single most-conservative
#: member of :data:`PROJECTION_ORDER`: left to the generic guard alone, quarantine would be
#: terminal and nothing could ever exit it.
#:
#: ADR-002-002 §18.6 "escaping quarantine requires evidence, never assertion" is why ``UNKNOWN``
#: and ``TIMEOUT`` are deliberately **absent** here: neither carries positive evidence about the
#: attempt, so a repeat of either while already quarantined is handled by the ordinary rank check
#: below (equal rank, ``QUARANTINED_UNKNOWN`` -> ``QUARANTINED_UNKNOWN``) and the duplicate-
#: signature machinery — never this table. Every other member of the closed
#: :class:`~tos.engine.vocabulary.EgressResultKind` vocabulary *is* positive evidence about this
#: exact attempt (a broker acknowledgement, a fill, a proven rejection, a cancel/expiry
#: acknowledgement) and each maps to exactly the capacity target :data:`_RESULT_TRANSITIONS`
#: already assigns it in the non-quarantined case — except ``ACK``, whose ordinary mapping is
#: ``None`` ("leave capacity where it is") because it never needs to *move* capacity when nothing
#: was quarantined; resolving out of quarantine does need an explicit target, hence the separate
#: table rather than reusing ``_RESULT_TRANSITIONS`` directly.
#:
#: ⚠ Still the provisional, non-authoritative projection (module docstring). The real resolution
#: of a Risk Capacity Ledger quarantine is an RCL act gated on Final Quantity Proof (ADR-002-002
#: §15.2 / §18.6) — a runtime capability this slice does not have (deferred to Phase 5). This
#: table only stops the **local mirror** from over-reporting a definite settlement as an
#: unresolved unknown once positive evidence for that exact attempt actually arrives; it asserts
#: no RCL-authoritative release and creates no headroom (RFC-002 §9.1:558).
QUARANTINE_RESOLUTION_EDGES: dict[EgressResultKind, CapacityState] = {
    EgressResultKind.ACK: CapacityState.POTENTIALLY_LIVE,
    EgressResultKind.PARTIAL_FILL: CapacityState.PARTIALLY_CONSUMED,
    EgressResultKind.FULL_FILL: CapacityState.POSITION_CONSUMED,
    EgressResultKind.REJECT: CapacityState.RELEASE_PENDING_PROOF,
    EgressResultKind.CANCEL_ACK: CapacityState.RELEASE_PENDING_PROOF,
    EgressResultKind.EXPIRED: CapacityState.RELEASE_PENDING_PROOF,
}


def knowledge_for_result(kind: EgressResultKind) -> EgressKnowledge:
    """The knowledge axis an egress result establishes (design #31 §2.4).

    Args:
        kind: The re-injected egress result kind.

    Returns:
        The :class:`~tos.engine.vocabulary.EgressKnowledge` member. ``UNKNOWN`` and ``TIMEOUT``
        both map to the explicit ``UNKNOWN`` member — never to a missing value, and never to
        ``REJECTED`` (RFC-005 §11:325-327 "UNKNOWN is not a rejection"). ``CANCEL_ACK`` /
        ``EXPIRED`` each map to their own dedicated member (Phase 3 KW2-C1) — neither collapses
        into ``REJECTED``, which would misrepresent a cancel/expiry as a broker rejection.

    Raises:
        ArtifactIntegrityError: If the kind is outside the closed mapping (fail-closed).
    """
    mapped = _RESULT_TRANSITIONS.get(kind)
    if mapped is None:
        raise ArtifactIntegrityError(
            f"no closed transition is declared for egress result kind {kind!r} (fail-closed)"
        )
    return mapped[0]


@dataclass(frozen=True)
class ResultApplication:
    """The recorded, conservative outcome of one ``apply_egress_result`` call (Phase 3 A-K-2).

    A late, orphaned, duplicated, or attempt-mismatched egress result is not a crash: the design
    plan (2026-09-09 §1.1 "크래시는 이벤트가 아니다") requires the engine to hand the caller a
    **recorded conservative outcome** instead of raising. ``applied`` is ``True`` **iff**
    ``disposition is ResultDisposition.APPLIED``; the two are kept as separate fields (rather than
    deriving one from the other at every call site) so a caller can gate on the boolean without
    importing the enum, while the enum still carries which of the three non-APPLIED reasons held.

    ``projection`` is:

    * the *newly stored* projection when ``disposition is APPLIED``;
    * the *unchanged* outstanding projection when ``disposition`` is ``MISMATCHED_ATTEMPT`` or
      ``DUPLICATE`` (a reservation exists, but this result did not move it);
    * ``None`` when ``disposition is ORPHAN_NO_RESERVATION`` (no reservation exists to report).
    """

    applied: bool
    disposition: ResultDisposition
    projection: ProvisionalReservation | None


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
        #: Per-scope signatures of every egress result already applied (Phase 3 A-K-2 DUPLICATE
        #: detection, keying tightened in K2-p3-#6): ``(attempt_id, kind, filled_quantity,
        #: remaining_quantity, broker_execution_id)`` — **not** ``reference``, which the driver
        #: re-stamps on every re-enqueue and so can never identify a genuine broker resend
        #: (ADR-002-002 §15.3:725). With ``broker_execution_id is None`` (a result that never
        #: reached a broker, e.g. a synthetic ``TIMEOUT``) this is a runtime-local replay guard
        #: against re-processing a byte-identical resend, not §15.3 broker idempotency. A
        #: scope goes through at most one reservation lifecycle here (no release path exists — see
        #: the module docstring), so this never needs resetting across attempts within a scope.
        self._applied_result_signatures: dict[
            tuple[str, str], tuple[tuple[object, ...], ...]
        ] = {}

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

    def _store(
        self,
        reservation: ProvisionalReservation,
        *,
        allow_quarantine_resolution: bool = False,
    ) -> ProvisionalReservation:
        """Store a reservation projection, enforcing forward-only (non-revival) advance.

        Args:
            reservation: The reservation to store.
            allow_quarantine_resolution: ``True`` only when the caller
                (:meth:`apply_egress_result`) has already independently verified this exact rank
                decrease is a licensed :data:`QUARANTINE_RESOLUTION_EDGES` exit from
                ``QUARANTINED_UNKNOWN`` (Phase 3 wave 2 KW2b-#2; ADR-002-002 §18.6). Every other
                call site (``commit_unbound`` / ``bind_attempt`` / ``mark_potentially_live``) never
                passes this, so the non-revival guard stays absolute for them — none of the three
                is ever legitimately reachable while quarantined in the first place (the at-most-
                one exposure retention denies a new attempt for an occupied, quarantined scope).
        """
        key_tuple = self._key_tuple(reservation.instrument_key)
        current = self._reservations.get(key_tuple)
        if current is not None:
            current_rank = PROJECTION_RANK[current.capacity_state]
            next_rank = PROJECTION_RANK[reservation.capacity_state]
            resolving_quarantine = (
                allow_quarantine_resolution
                and current.capacity_state is CapacityState.QUARANTINED_UNKNOWN
            )
            if next_rank < current_rank and not resolving_quarantine:
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

    def bind_attempt(
        self, key: InstrumentKey, *, attempt_id: str
    ) -> ProvisionalReservation:
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

    @staticmethod
    def _quantity_regressed(
        current: ProvisionalReservation, payload: EgressResultPayload
    ) -> bool:
        """Whether ``payload`` would regress the quantity axis of ``current`` (§35 K2-p3-#5 / N2;
        Phase 3 wave 2 review finding #10 / kernel disposition KW2b-#10).

        Factored out of :meth:`apply_egress_result` (size-budget discipline). Four independent,
        non-revival directions are checked, all folded into the same
        :class:`~tos.engine.vocabulary.ResultDisposition.QUANTITY_REGRESSION` disposition (see
        that member's own docstring for why a fourth is not a separate disposition):

        1. ``filled_quantity`` strictly below the already-recorded value (ADR-002-002
           §15.1:710 "reduced by no more than the amount proven filled");
        2. ``remaining_quantity`` growing at all versus the already-recorded value (implies the
           authorized quantity itself grew — unrepresentable for one attempt);
        3. ``remaining_quantity`` shrinking by more than ``filled_quantity`` grew (quantity
           vanishing unaccounted — CPL-2/CPL-4 forbid an evidence-free implicit release);
        4. [KW2b-#10] the *mirror* of (3): ``filled_quantity`` growing by more than
           ``remaining_quantity`` shrank, which inflates rather than shrinks the attempt's
           authorized total (``filled_quantity + remaining_quantity``) — e.g. ``4/6`` ->
           ``6/5`` (total ``10`` -> ``11``). Directions 1-3 alone did not catch this: they admit
           any ``filled`` growth and only refuse a ``remaining`` shrink that *exceeds* it, never
           one that falls short of it. The first fill-bearing result for an attempt fixes
           ``authorized_total``; every later one must keep that exact sum, not merely avoid
           exceeding it — an attempt's authorized quantity can no more grow after the fact than
           it can shrink without proof.

        Only ``FULL_FILL`` / ``PARTIAL_FILL`` carry magnitudes at all; every other kind returns
        ``False`` immediately (nothing to regress). ``EgressResultPayload``'s own shape validator
        guarantees both magnitudes are present (non-``None``) for those two kinds, so once
        ``current`` also carries an established baseline, every comparison below is over concrete
        values — never a silent ``None`` short-circuit.

        Args:
            current: The outstanding projection before this result.
            payload: The re-injected egress result payload.

        Returns:
            ``True`` iff any of the four directions above regressed.
        """
        if payload.kind not in (
            EgressResultKind.FULL_FILL,
            EgressResultKind.PARTIAL_FILL,
        ):
            return False
        if current.filled_quantity is None or current.remaining_quantity is None:
            # No fill-bearing result has landed for this attempt yet — there is no established
            # authorized-total baseline to regress against. The first one sets it.
            return False
        assert (
            payload.filled_quantity is not None
        )  # validator-guaranteed for fill kinds
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
        """The capacity target for ``payload`` against ``current``, or the rank-guard refusal.

        Factored out of :meth:`apply_egress_result` (size-budget discipline). Returns either:

        * ``(capacity_state, resolving_quarantine)`` — the target to store (``None`` means "no
          explicit target, leave unchanged") and whether this is a licensed
          :data:`QUARANTINE_RESOLUTION_EDGES` exit from ``QUARANTINED_UNKNOWN`` (Phase 3 wave 2
          KW2b-#2; ADR-002-002 §18.6 "escaping quarantine requires evidence, never assertion" —
          the one deliberate exception to the rank-regression guard, checked first: left to that
          guard alone, quarantine would be terminal, since ``QUARANTINED_UNKNOWN`` is the single
          highest rank in :data:`PROJECTION_ORDER` and nothing could ever rank above it to exit);
        * ``ResultDisposition.NON_MONOTONIC_PROJECTION`` when the target would otherwise regress
          the rank and is *not* a licensed resolution (Phase 3 K2-p3-#4) — refused before
          :meth:`_store` is ever reached, so its own non-revival guard never has to fire on this
          path; a late/reordered result is a recorded conservative outcome, not a crash (design
          plan 2026-09-09 §1.1).
        """
        _, capacity_state = _RESULT_TRANSITIONS[payload.kind]
        resolving_quarantine = (
            current.capacity_state is CapacityState.QUARANTINED_UNKNOWN
            and payload.kind in QUARANTINE_RESOLUTION_EDGES
        )
        if resolving_quarantine:
            return QUARANTINE_RESOLUTION_EDGES[payload.kind], True
        if capacity_state is not None:
            current_rank = PROJECTION_RANK[current.capacity_state]
            next_rank = PROJECTION_RANK[capacity_state]
            if next_rank < current_rank:
                return ResultDisposition.NON_MONOTONIC_PROJECTION
        return capacity_state, False

    def apply_egress_result(self, payload: EgressResultPayload) -> ResultApplication:
        """Apply — or conservatively record — a re-injected egress result (Phase 3 A-K-2).

        A late, orphaned, duplicated, attempt-mismatched, rank-regressing, or quantity-regressing
        result is **not** raised as a crash: it is returned as a :class:`ResultApplication` naming
        the exact :class:`~tos.engine.vocabulary.ResultDisposition`, leaving the projection
        untouched on every non-``APPLIED`` outcome. See :class:`~tos.engine.vocabulary.
        ResultDisposition` for what each of the six members means and the spec citation behind it
        — this method is the single place all six are decided, in the order the class's own
        docstring lists them, so that is the canonical reference rather than a second copy here.
        Only ``APPLIED`` transitions the reservation (design #31 §2.2/§4.2 rule 3). The two
        regressing dispositions (``NON_MONOTONIC_PROJECTION``, ``QUANTITY_REGRESSION``) exist
        because letting :meth:`_store`'s non-revival guard raise straight out of this method was
        itself the crash Phase 3 review finding #4 named — this method must never let it fire.

        Args:
            payload: The egress result payload.

        Returns:
            The :class:`ResultApplication` naming the disposition and the resulting (or unchanged)
            projection.
        """
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
        # ★ [K2-p3-#5 / Phase 3 wave 2 N2] The quantity axis has its own, independent
        # non-revival rule (ADR-002-002 §15.1:710), covering both ``filled_quantity`` shrinking
        # and ``remaining_quantity`` growing or shrinking unmatched by a filled increase (wave 1
        # review finding N2). See :meth:`_quantity_regressed` for the full citation of each of
        # the three directions checked.
        if self._quantity_regressed(current, payload):
            return ResultApplication(
                applied=False,
                disposition=ResultDisposition.QUANTITY_REGRESSION,
                projection=current,
            )
        update: dict[str, object] = {"knowledge": knowledge}
        if capacity_state is not None:
            update["capacity_state"] = capacity_state
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
