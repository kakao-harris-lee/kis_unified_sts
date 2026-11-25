"""Record and verify preserved capacity for ``SEND_REFUSED`` obligations."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tos.cur import obligation_preserved
from tos.egressgw.records import GatewayEvidenceRecord
from tos.rcl import CapacityState

from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import ReservationProjectionReader

__all__ = ["CapacityObligationRecorder", "CAPACITY_CONSUMING_STATE_VALUES"]

_EVIDENCE_KIND = "CAPACITY_OBLIGATION_PRESERVED"

_HALT_KIND = "CAPACITY_OBLIGATION_VIOLATION_ALERT"

CAPACITY_CONSUMING_STATE_VALUES: frozenset[str] = frozenset(
    state.value for state in CapacityState if state is not CapacityState.RELEASED
)


class CapacityObligationRecorder:
    """Records + verifies a ``SEND_REFUSED`` record's preserved-capacity"""

    def __init__(
        self,
        *,
        store: SqliteEvidenceStore,
        emergency_log: EmergencyAppendLog,
        projection: ReservationProjectionReader,
        reservation_id_resolver: Callable[[str], str | None],
        capacity_consuming_states: frozenset[str] = CAPACITY_CONSUMING_STATE_VALUES,
    ) -> None:
        """Bind this recorder to its durable paths + the live rcl projection."""
        self._store = store
        self._emergency_log = emergency_log
        self._projection = projection
        self._reservation_id_resolver = reservation_id_resolver
        self._capacity_consuming_states = capacity_consuming_states

    def __call__(self, record: GatewayEvidenceRecord) -> None:
        """Verify + evidence one ``SEND_REFUSED`` record's preserved obligation."""
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
