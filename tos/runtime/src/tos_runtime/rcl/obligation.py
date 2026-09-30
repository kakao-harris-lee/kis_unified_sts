"""Record and verify preserved capacity for ``SEND_REFUSED`` obligations.

A concrete worst-credible-capacity obligation is checked against the current
reservation projection before its evidence is recorded. A missing obligation
is a no-op only when no unknown magnitude was asserted; an unknown magnitude
is restrictive and must fail closed through the kernel predicate.

The default attempt-to-reservation resolver uses the compose root's
``(account, instrument)`` identity and is intentionally scope-level. It is
safe only while that scope has at most one live reservation for the process
lifetime; concurrent or multi-reservation callers MUST inject a real
attempt-to-reservation lookup. The capacity-consuming state set is derived
from the public ``CapacityState`` enum so it follows the kernel vocabulary
without importing a private predicate constant.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.cur import obligation_preserved
from tos.egressgw.records import GatewayEvidenceRecord
from tos.rcl import CapacityState

from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import ReservationProjectionReader

__all__ = ["CapacityObligationRecorder", "CAPACITY_CONSUMING_STATE_VALUES"]

#: One evidence row per SEND_REFUSED whose item-16 verdict carried a
#: preserved worst-credible-capacity obligation.
_EVIDENCE_KIND = "CAPACITY_OBLIGATION_PRESERVED"

#: The dual-path emergency HALT kind raised when the obligation is NOT
#: preserved (an authority-projection mismatch: the send was refused to
#: protect capacity that the live reservation state no longer actually
#: holds — the same class of concern ``verify_rcl_log_or_halt`` raises for
#: a corrupt replay, module docstring's "reported deviation").
_HALT_KIND = "CAPACITY_OBLIGATION_VIOLATION_ALERT"

#: Mirrors rcl's own private ``_LIVE_COMMITTED_STATES``
#: (``tos/src/tos/rcl/predicates.py:172-174`` — not re-exported by
#: ``tos.rcl.__init__``, an underscore-prefixed module symbol). Every
#: :class:`~tos.rcl.CapacityState` member except ``RELEASED`` still consumes
#: capacity; ``RELEASED`` is the sole terminal, non-consuming state (rcl's
#: ``_CONSERVATISM_RANK`` places ``POSITION_CONSUMED`` MORE conservative than
#: ``POTENTIALLY_LIVE``, not less, so "still consuming" is not a contiguous
#: rank prefix and must be read off enum membership, not a rank threshold —
#: see ``cba1972c``'s own commit message for this exact correction against
#: an earlier, wrong plan example).
CAPACITY_CONSUMING_STATE_VALUES: frozenset[str] = frozenset(
    state.value for state in CapacityState if state is not CapacityState.RELEASED
)


class CapacityObligationRecorder:
    """Records + verifies a ``SEND_REFUSED`` record's preserved-capacity
    obligation against the bound reservation's live rcl capacity state.

    Intended as the ``on_refusal`` observer for
    :class:`~tos_runtime.evidence.sinks.GatewayEvidenceSinkAdapter` — called
    AFTER the ``SEND_REFUSED`` record is already durably appended (this
    class never itself decides whether the refusal happened; it only
    verifies the obligation a refusal already on record asserted).
    """

    def __init__(
        self,
        *,
        store: SqliteEvidenceStore,
        emergency_log: EmergencyAppendLog,
        projection: ReservationProjectionReader,
        reservation_id_resolver: Callable[[str], str | None],
        capacity_consuming_states: frozenset[str] = CAPACITY_CONSUMING_STATE_VALUES,
    ) -> None:
        """Bind this recorder to its durable paths + the live rcl projection.

        Args:
            store: The durable sqlite evidence store every
                ``CAPACITY_OBLIGATION_PRESERVED`` row is appended into (the
                SAME store the gateway's own ``SEND_REFUSED`` record just
                landed in).
            emergency_log: The sqlite-independent emergency path
                :func:`~tos_runtime.evidence.emergency.record_halt` also
                writes to when the obligation is NOT preserved.
            projection: The read-only rcl reservation-state projection
                (module docstring's live capacity-state read).
            reservation_id_resolver: Maps a ``GatewayEvidenceRecord.attempt_id``
                to the rcl reservation id bound to it, or ``None`` when that
                attempt cannot be resolved to a reservation (module
                docstring's "reported seam" — never ``None`` in this compose
                root's own wiring, but see the module docstring's "not
                attempt-scoped" caveat: every attempt on this account +
                instrument resolves to the SAME id, so the state read back
                for it is the shared reservation's CURRENT state, not the
                state as of that attempt's own refusal).
            capacity_consuming_states: Injected into every
                :func:`tos.cur.obligation_preserved` call (module docstring's
                "reported deviation"); defaults to the full mirror of rcl's
                own committed-state partition.
        """
        self._store = store
        self._emergency_log = emergency_log
        self._projection = projection
        self._reservation_id_resolver = reservation_id_resolver
        self._capacity_consuming_states = capacity_consuming_states

    def __call__(self, record: GatewayEvidenceRecord) -> None:
        """Verify + evidence one ``SEND_REFUSED`` record's preserved obligation.

        No-op ONLY when ``preserved_worst_credible_capacity is None`` AND
        ``preserved_obligation_magnitude_unknown`` is ``False`` — module
        docstring's "Magnitude-unknown obligations" section enumerates the
        four ``None``-and-no-magnitude-flag cases (review finding #9) that
        legitimately reach this no-op, and the fifth case (review finding
        #4) that must NOT: a magnitude-unknown obligation is the single most
        dangerous input this recorder can see and must never collapse into
        "nothing to verify". Both a concrete obligation and a
        magnitude-unknown one share the SAME path below: resolve the bound
        reservation, ask the kernel predicate (``magnitude_unknown=True``
        forces its answer to ``False`` unconditionally — CUR-INV-011:183),
        durably evidence the verdict, and — fail-closed polarity,
        ``is not True`` — HALT when it does not hold.

        Raises:
            Exception: Whatever :meth:`SqliteEvidenceStore.append` or
                :func:`~tos_runtime.evidence.emergency.record_halt` raises,
                propagated unchanged (an evidence/halt failure here is never
                swallowed — mirrors every other evidence-sink adapter in
                this compose root).
        """
        obligation = record.preserved_worst_credible_capacity
        magnitude_unknown = record.preserved_obligation_magnitude_unknown
        if obligation is None and not magnitude_unknown:
            return

        reservation_id: str | None = None
        if record.attempt_id is not None:
            reservation_id = self._reservation_id_resolver(record.attempt_id)

        state: CapacityState | None = None
        if reservation_id is not None:
            state = self._projection.reservation_state(reservation_id)
        state_value: str | None = None if state is None else state.value

        verdict = obligation_preserved(
            obligation,
            state_value,
            capacity_consuming_states=self._capacity_consuming_states,
            magnitude_unknown=magnitude_unknown,
        )

        payload: Mapping[str, object] = {
            "attempt_id": record.attempt_id,
            "reservation_id": reservation_id,
            "obligation": obligation,
            "reservation_state": state_value,
            "verdict": verdict,
            "magnitude_unknown": magnitude_unknown,
        }
        self._store.append(
            payload,
            kind=_EVIDENCE_KIND,
            record_class=_EVIDENCE_KIND,
        )

        if verdict is not True:
            record_halt(
                self._store,
                self._emergency_log,
                payload=dict(payload),
                kind=_HALT_KIND,
                record_class=_HALT_KIND,
            )
