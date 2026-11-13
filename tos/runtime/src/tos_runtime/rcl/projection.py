"""Read-only reservation projection over ``SqliteCommitLog`` (slice plan §1 item 7)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState, CapacityVector

from tos_runtime.rcl.log import SqliteCommitLog

__all__ = [
    "ReservationProjectionReader",
    "ScopeReservation",
    "SqliteReservationProjectionReader",
    "outstanding_reservations",
]


@dataclass(frozen=True)
class ScopeReservation:
    """One reservation row of one ``(account, instrument)`` scope (#966)."""

    reservation_id: str
    state: CapacityState
    last_seq: int

    @property
    def outstanding(self) -> bool:
        """Whether this row still consumes capacity."""
        return self.state is not CapacityState.RELEASED


def outstanding_reservations(
    rows: Sequence[ScopeReservation],
) -> tuple[ScopeReservation, ...]:
    """The rows of ``rows`` that still consume capacity (:attr:`ScopeReservation.outstanding`)."""
    return tuple(row for row in rows if row.outstanding)


@runtime_checkable
class ReservationProjectionReader(Protocol):
    """The read-only reservation-projection seam a consumer (e.g. the engine) depends on."""

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        """The current projected :class:`~tos.rcl.CapacityState` of ``reservation_id``, if any."""
        ...

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        """The ``seq`` of the last committed transition for ``reservation_id``, if any."""
        ...

    def all_reservations(self) -> Mapping[str, CapacityState]:
        """A snapshot of every held reservation's current state, keyed by ``reservation_id``."""
        ...

    def scope_reservations(self, key: InstrumentKey) -> tuple[ScopeReservation, ...]:
        """EVERY reservation this log holds for ``key``'s (account, instrument) scope."""
        ...

    def reservation_committed_vector(
        self, reservation_id: str
    ) -> CapacityVector | None:
        """The committed :class:`~tos.rcl.CapacityVector` last written for"""
        ...


class SqliteReservationProjectionReader:
    """A :class:`ReservationProjectionReader` backed directly by a live ``SqliteCommitLog``."""

    def __init__(self, log: SqliteCommitLog) -> None:
        self._log = log

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        for (
            row_reservation_id,
            state,
            _last_seq,
            _scope,
        ) in self._log.reservation_rows():
            if row_reservation_id == reservation_id:
                return state
        return None

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        for (
            row_reservation_id,
            _state,
            last_seq,
            _scope,
        ) in self._log.reservation_rows():
            if row_reservation_id == reservation_id:
                return last_seq
        return None

    def all_reservations(self) -> Mapping[str, CapacityState]:
        return {
            reservation_id: state
            for reservation_id, state, _last_seq, _scope in self._log.reservation_rows()
        }

    def scope_reservations(self, key: InstrumentKey) -> tuple[ScopeReservation, ...]:
        return tuple(
            ScopeReservation(
                reservation_id=reservation_id, state=state, last_seq=last_seq
            )
            for reservation_id, state, last_seq, scope in self._log.reservation_rows()
            if scope.account == key.account and scope.instrument == key.instrument
        )

    def reservation_committed_vector(
        self, reservation_id: str
    ) -> CapacityVector | None:
        return self._log.reservation_committed_vector(reservation_id)
