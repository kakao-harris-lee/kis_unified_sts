"""KST-native trading calendar (Phase 5 W5 plan §2 decisions 1-2).

This package supplies session-phase and futures-maturity facts as pure
functions over a loaded :class:`~tos_runtime.calendar.config.CalendarConfig`,
plus the wall-clock reference ports a later lane's ``SessionFactsOwner``
composes with. It never judges admissibility itself (the kernel does that);
it never reads a real wall clock in production (G-1 gate,
:mod:`tos_runtime.calendar.ports`).
"""

from __future__ import annotations

from tos_runtime.calendar.config import (
    CalendarConfig,
    CalendarConfigError,
    ExpiryRule,
    SessionWindow,
    calendar_bind_digest,
    load_calendar_config,
)
from tos_runtime.calendar.model import MaturityFact, PhaseFact, WallClockReading
from tos_runtime.calendar.ports import (
    AbsentWallClockReference,
    FixedWallClockReference,
    LocalWallClockReference,
    WallClockReference,
)

__all__ = [
    "CalendarConfig",
    "CalendarConfigError",
    "ExpiryRule",
    "SessionWindow",
    "calendar_bind_digest",
    "load_calendar_config",
    "MaturityFact",
    "PhaseFact",
    "WallClockReading",
    "AbsentWallClockReference",
    "FixedWallClockReference",
    "LocalWallClockReference",
    "WallClockReference",
]
