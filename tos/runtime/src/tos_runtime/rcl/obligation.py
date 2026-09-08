"""``CapacityObligationRecorder`` — SEND_REFUSED preserved-capacity obligation
recorder/verifier (design #40 kernel round #1 §3; commandtype/expiry/
obligation plan §3).

Kernel round #1 §1.3 (``1e06f0b8``/``cba1972c``) typed item 16's (CURRENTNESS)
worst-credible-capacity obligation onto ``VerifyItemVerdict``/
``GatewayEvidenceRecord.preserved_worst_credible_capacity`` and added the
kernel predicate ``tos.cur.obligation_preserved(obligation, reservation_state,
*, capacity_consuming_states)``. Blocking a not-yet-provably-safe release was
already structurally closed before this lane started (§0 survey: rcl's own
``commitlog.release_admissible`` admits only on a positive finality witness) —
what was missing was **recording and verifying** whether the obligation an
UNKNOWN/DENIED currentness outcome asserted is actually still honored by the
bound reservation's live rcl capacity state. This module is that recorder.

**Reservation-id resolution (reported seam).** Neither ``GatewayEvidenceRecord``
nor ``SendBoundaryContext`` carries a reservation identity (only
``reservation_attempt_id`` — the attempt, not the reservation). Rather than
add a kernel field for this (out of lane B's write surface — kernel edits are
lane K's alone this round), the caller injects a
``reservation_id_resolver: Callable[[str], str | None]`` that maps an
attempt id to the rcl reservation id bound to it. Every wiring site already
in this compose root (``_wiring.py``'s ``AtomicCommitStage`` reservation-id
provider, ``TransmissionCapabilityStage``'s context reader, and
``ComposeContextResolver._reconstruct_transmission_capability``) derives that
identity the SAME way: ``f"resv-{account}-{instrument}"`` off the compose
root's own single, fixed :class:`~tos.engine.records.InstrumentKey` — this
compose root handles exactly one instrument per process, so that formula is
EXACT here, not an approximation. A resolver is injected rather than that
formula being hardcoded in this module so a future multi-instrument compose
root can supply a real attempt -> reservation lookup without touching this
recorder.

**Capacity-consuming state set (reported deviation).** ``obligation_preserved``
takes an injected ``capacity_consuming_states: frozenset[str]`` because
``cur`` cannot import ``tos.rcl`` (sibling-edge-0 import closure —
``obligation_preserved``'s own docstring). The kernel's own reference set,
``tos.rcl.predicates._LIVE_COMMITTED_STATES``, is **not** re-exported by
``tos.rcl.__init__`` (an underscore-prefixed module-private symbol, absent
from that module's ``__all__``) — importing it directly would be reaching
into a private implementation detail across a package boundary. This module
therefore re-derives the same set from the PUBLIC :class:`~tos.rcl.CapacityState`
enum: every member except ``RELEASED`` (rcl/predicates.py:172-174's own
definition, mirrored here member-for-member so a future ``CapacityState``
addition is picked up automatically rather than silently excluded by a
hand-typed literal set).

Firewall: stdlib + ``tos.cur``/``tos.rcl``/``tos.egressgw.records`` +
``tos_runtime.evidence``/``tos_runtime.rcl`` only (this lane's scoped
firewall for this module — no ``tos.workload``/``tos.engine``, so this
recorder is never told a ``RuntimeIdentity`` and never stamps one onto the
evidence it appends; ``runtime_identity`` defaults to ``None`` the same way
an omitted keyword to :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append`
would).
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
                docstring's "reported seam" — never ``None`` in this
                compose root's own single-instrument wiring).
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

        A no-op when the record carries no obligation
        (``preserved_worst_credible_capacity is None`` — either the halt was
        not item 16, or item 16 itself had nothing to preserve). Otherwise:
        resolve the bound reservation's current state, ask the kernel
        predicate whether the obligation still holds, durably evidence the
        verdict, and — fail-closed polarity, ``is not True`` — HALT when it
        does not.

        Raises:
            Exception: Whatever :meth:`SqliteEvidenceStore.append` or
                :func:`~tos_runtime.evidence.emergency.record_halt` raises,
                propagated unchanged (an evidence/halt failure here is never
                swallowed — mirrors every other evidence-sink adapter in
                this compose root).
        """
        obligation = record.preserved_worst_credible_capacity
        if obligation is None:
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
        )

        payload: Mapping[str, object] = {
            "attempt_id": record.attempt_id,
            "reservation_id": reservation_id,
            "obligation": obligation,
            "reservation_state": state_value,
            "verdict": verdict,
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
