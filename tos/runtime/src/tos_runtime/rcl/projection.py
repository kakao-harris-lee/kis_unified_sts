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

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState

from tos_runtime.rcl.log import SqliteCommitLog

__all__ = ["ReservationProjectionReader", "SqliteReservationProjectionReader"]


@runtime_checkable
class ReservationProjectionReader(Protocol):
    """The read-only reservation-projection seam a consumer (e.g. the engine) depends on.

    Two independent key surfaces over the same underlying rows: the RCL
    log's own native ``reservation_id`` (``reservation_state`` /
    ``reservation_last_seq`` / ``all_reservations``), and the engine's
    :class:`~tos.engine.records.InstrumentKey` scope (``instrument_state`` /
    ``instrument_last_seq`` — see the module docstring's "kernel port
    binding note").
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

    def instrument_state(self, key: InstrumentKey) -> CapacityState | None:
        """The projected state of the reservation bound to ``key``'s (account,
        instrument) scope, if any (slice #1 projects at most one per scope)."""
        ...

    def instrument_last_seq(self, key: InstrumentKey) -> int | None:
        """The ``seq`` of the last committed transition for the reservation bound to
        ``key``'s scope, if any."""
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

    def instrument_state(self, key: InstrumentKey) -> CapacityState | None:
        for _reservation_id, state, _last_seq, scope in self._log.reservation_rows():
            if scope.account == key.account and scope.instrument == key.instrument:
                return state
        return None

    def instrument_last_seq(self, key: InstrumentKey) -> int | None:
        for _reservation_id, _state, last_seq, scope in self._log.reservation_rows():
            if scope.account == key.account and scope.instrument == key.instrument:
                return last_seq
        return None
