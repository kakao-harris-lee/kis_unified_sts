"""Linearizable RCL commit log — runtime implementation (design #40 D2, §5 order 3).

Implements the kernel's ``tos.rcl.commitlog.CommitLog`` Protocol
(:class:`~tos_runtime.rcl.log.SqliteCommitLog`) plus a read-only projection
adapter for the engine's reservation view
(:mod:`tos_runtime.rcl.projection`). See :mod:`tos_runtime.rcl.log`'s own
module docstring for the fault-contract table (①-⑦).

Public surface groups by module:

* :mod:`tos_runtime.rcl.log` — :class:`~tos_runtime.rcl.log.SqliteCommitLog`,
  its exceptions, and the reservation-lifecycle refusal vocabulary.
* :mod:`tos_runtime.rcl.projection` —
  :class:`~tos_runtime.rcl.projection.ReservationProjectionReader` Protocol +
  :class:`~tos_runtime.rcl.projection.SqliteReservationProjectionReader`.
"""

from __future__ import annotations

from tos_runtime.rcl.log import (
    CommitLogCorruption,
    ReservationRefusalReason,
    ReservationTransitionRefusal,
    SqliteCommitLog,
    StaleEpochRead,
)
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    SqliteReservationProjectionReader,
)

__all__ = [
    "CommitLogCorruption",
    "ReservationProjectionReader",
    "ReservationRefusalReason",
    "ReservationTransitionRefusal",
    "SqliteCommitLog",
    "SqliteReservationProjectionReader",
    "StaleEpochRead",
]
