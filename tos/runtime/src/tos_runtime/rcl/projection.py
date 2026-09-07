"""Read-only reservation projection over ``SqliteCommitLog`` (slice plan §1 item 7).

**Missing kernel port, reported per the slice plan's own instruction** ("Protocol
은 커널 ``engine/state.py`` 의 ``ProvisionalReservationLedger`` 가 요구하는 최소
인터페이스를 읽어서 맞춘다 — 커널 편집 없이 어댑터 가능하면 그렇게, 불가능하면
필요한 커널 포트를 보고만"):

``tos.engine.state.ProvisionalReservationLedger`` is keyed by
``InstrumentKey`` (``account``, ``instrument``) — every one of its read
methods (``outstanding``, ``outstanding_count``,
``outstanding_consumed_magnitude``, ``admits_new_exposure``) takes an
``InstrumentKey``. The kernel RCL commit-log port
(``tos.rcl.commitlog.CapacityReservationTransition``) carries only a bare
``reservation_id: str | None`` — there is **no kernel record anywhere**
binding a ``reservation_id`` to the ``(account, instrument)`` pair that
identifies a scope. Consequently this module CANNOT structurally satisfy
``ProvisionalReservationLedger``'s own interface without inventing that
mapping out of nothing (which would be a runtime-local fabrication of kernel
identity, not an adapter). What IS derivable from the log without any
invention is a projection keyed by the log's own native key,
``reservation_id`` — that is what :class:`ReservationProjectionReader`
below offers.

**The missing kernel port, precisely**: either (a) ``CapacityReservationTransition``
(and, upstream, the ``ReservationRecord``/command records that produce it)
gains an ``instrument_key: InstrumentKey | None`` field the RCL log could
persist and this projection could then group by, or (b) a separate kernel-
or runtime-owned registry maps ``reservation_id -> InstrumentKey`` at
reservation-creation time and is injected into this projection. Neither
exists today; this module implements only the ``reservation_id``-keyed
surface and reports this gap rather than closing it by force.

Firewall: stdlib + ``tos.rcl`` + ``tos_runtime.rcl.log`` only (R1 allowlist).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from tos.rcl import CapacityState

from tos_runtime.rcl.log import SqliteCommitLog

__all__ = ["ReservationProjectionReader", "SqliteReservationProjectionReader"]


@runtime_checkable
class ReservationProjectionReader(Protocol):
    """The read-only reservation-projection seam a consumer (e.g. the engine) depends on.

    Keyed by the RCL log's own native ``reservation_id`` — see the module
    docstring's "missing kernel port" note for why this is NOT the same
    shape as ``tos.engine.state.ProvisionalReservationLedger``'s
    ``InstrumentKey``-keyed interface.
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


class SqliteReservationProjectionReader:
    """A :class:`ReservationProjectionReader` backed directly by a live ``SqliteCommitLog``.

    A thin read adapter — every call re-reads :meth:`SqliteCommitLog.reservation_rows`
    (no caching, matching the log's own "no cache" discipline, design #40
    D2.1 line 61 "캐시 없음").
    """

    def __init__(self, log: SqliteCommitLog) -> None:
        self._log = log

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        for row_reservation_id, state, _last_seq in self._log.reservation_rows():
            if row_reservation_id == reservation_id:
                return state
        return None

    def reservation_last_seq(self, reservation_id: str) -> int | None:
        for row_reservation_id, _state, last_seq in self._log.reservation_rows():
            if row_reservation_id == reservation_id:
                return last_seq
        return None

    def all_reservations(self) -> Mapping[str, CapacityState]:
        return {
            reservation_id: state
            for reservation_id, state, _last_seq in self._log.reservation_rows()
        }
