"""Pure data records for the KST trading calendar (Phase 5 W5 plan §2 decision"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

__all__ = [
    "PhaseFact",
    "MaturityFact",
    "WallClockReading",
]


@dataclass(frozen=True)
class PhaseFact:
    """The session-phase token observed for one instrument class at one"""

    phase: str | None
    is_open: bool | None
    boundary_unix_ms: int | None
    source: str
    calendar_version: str


@dataclass(frozen=True)
class MaturityFact:
    """The futures-expiry state for one instrument class at one instant, per"""

    expiry_date: datetime.date | None
    expired: bool | None
    rule_present: bool


@dataclass(frozen=True)
class WallClockReading:
    """One wall-clock observation, per :mod:`tos_runtime.calendar.ports`."""

    unix_ms: int
    source_label: str
