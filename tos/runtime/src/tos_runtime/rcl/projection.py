"""Read-only reservation projection over ``SqliteCommitLog`` (slice plan §1 item 7).

**Kernel port binding note (laneO port-fix round, design #40 runtime slice
#2 §5 disposition, 2026-09-08).** This module used to report a missing
kernel port: ``tos.engine.state.ProvisionalReservationLedger`` (the
engine's read projection of this log) is keyed by
:class:`~tos.engine.records.InstrumentKey` (``account``, ``instrument``),
but ``tos.rcl.commitlog.CapacityReservationTransition`` carried only a bare
``reservation_id: str | None`` with no binding to that scope — so this
module could only be read back keyed by the log's own native key,
``reservation_id``, never by ``InstrumentKey``.

The independent review's disposition closed that gap at the source: the
kernel record gained a ``scope: ReservationScope | None`` field
(``tos.rcl.commitlog`` — a structural mirror of ``InstrumentKey``, not an
import of it; see that module's own docstring for why an ``rcl -> engine``
import edge is the wrong fix), ``SqliteCommitLog`` now persists it durably
(``reservations.scope_account``/``scope_instrument``, ``schema.py``) and
folds it into the fault-⑤ replay digest (``log.py``/``gates.py``). This
projection now imports ``InstrumentKey`` **from the engine directly**
(``tos_runtime -> tos.engine`` is an ALLOWED edge under design #40 D1.1 —
runtime may depend on any kernel package; it is only the reverse,
``tos.rcl -> tos.engine``, that is forbidden) and offers a genuine
``InstrumentKey``-keyed read surface over the log's scope-tagged rows,
alongside the original ``reservation_id``-keyed surface (kept — some
consumers still address a reservation by its own log-native identity).

Firewall: stdlib + ``tos.rcl`` + ``tos.engine.records`` (``InstrumentKey``
only) + ``tos_runtime.rcl.log`` (R1 allowlist — ``tos.engine`` is part of
the kernel ``tos`` package, so this is the D1.1 ``tos_runtime -> tos`` edge,
not a new commons dependency).
"""

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
    """One reservation row of one ``(account, instrument)`` scope (#966).

    What :meth:`ReservationProjectionReader.scope_reservations` reports per row. A named record
    rather than a bare triple because three independent consumers now read these rows — step 8's
    admission table, the ARE usage aggregate, and the item-16 capacity owner — and each reads a
    different field.
    """

    reservation_id: str
    state: CapacityState
    last_seq: int

    @property
    def outstanding(self) -> bool:
        """Whether this row still consumes capacity.

        Every :class:`~tos.rcl.CapacityState` except the terminal ``RELEASED`` does — the same
        partition :data:`tos_runtime.rcl.obligation.CAPACITY_CONSUMING_STATE_VALUES` already
        draws off the enum, and NOT a conservatism-rank threshold (``POSITION_CONSUMED`` ranks
        MORE conservative than ``POTENTIALLY_LIVE``, so "still consuming" is not a rank prefix —
        see that constant's own comment for the commit that corrected this).
        """
        return self.state is not CapacityState.RELEASED


def outstanding_reservations(
    rows: Sequence[ScopeReservation],
) -> tuple[ScopeReservation, ...]:
    """The rows of ``rows`` that still consume capacity (:attr:`ScopeReservation.outstanding`).

    The ONE place the "which rows count" question is answered, so step 8, the ARE aggregate and
    the capacity owner cannot drift apart on it.
    """
    return tuple(row for row in rows if row.outstanding)


@runtime_checkable
class ReservationProjectionReader(Protocol):
    """The read-only reservation-projection seam a consumer (e.g. the engine) depends on.

    Two independent key surfaces over the same underlying rows: the RCL
    log's own native ``reservation_id`` (``reservation_state`` /
    ``reservation_last_seq`` / ``all_reservations`` /
    ``reservation_committed_vector``), and the engine's
    :class:`~tos.engine.records.InstrumentKey` scope (``scope_reservations``
    — see the module docstring's "kernel port binding note").
    """

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
        """EVERY reservation this log holds for ``key``'s (account, instrument) scope.

        Replaces the pre-#966 ``instrument_state``/``instrument_last_seq``/
        ``instrument_committed_vector`` trio, which returned the scope's FIRST row only. That
        was sound while a scope could hold at most one reservation; since #966 each attempt
        commits its own (:mod:`tos_runtime.rcl.reservation_identity`), so a scope legitimately
        holds two at once — a filled entry at ``POSITION_CONSUMED`` plus the exit closing it —
        and a first-row read would silently under-report both the occupancy count and the
        aggregate usage.
        """
        ...

    def reservation_committed_vector(
        self, reservation_id: str
    ) -> CapacityVector | None:
        """The committed :class:`~tos.rcl.CapacityVector` last written for
        ``reservation_id``, if any (kernel round #4 K-4)."""
        ...


class SqliteReservationProjectionReader:
    """A :class:`ReservationProjectionReader` backed directly by a live ``SqliteCommitLog``.

    A thin read adapter — every call re-reads :meth:`SqliteCommitLog.reservation_rows`
    (no caching, matching the log's own "no cache" discipline, design #40
    D2.1 line 61 "캐시 없음").
    """

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
