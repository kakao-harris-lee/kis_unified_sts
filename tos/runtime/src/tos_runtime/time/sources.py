"""Injectable monotonic + reference-clock source ports (slice plan §1 item 1)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "MonotonicSource",
    "ProcessMonotonicSource",
    "ReferenceObservation",
    "ReferenceSourceReader",
    "LocalSystemClockReader",
]


@runtime_checkable
class MonotonicSource(Protocol):
    """A source of monotonic-clock readings, in whole milliseconds."""

    def now_ms(self) -> int:
        """Return the current monotonic reading, in whole milliseconds."""
        ...


class ProcessMonotonicSource:
    """Wraps ``time.monotonic_ns()`` — the kernel-forbidden clock read, made"""

    def now_ms(self) -> int:
        """Return ``time.monotonic_ns() // 1_000_000`` (truncated to whole ms)."""
        return time.monotonic_ns() // 1_000_000


@dataclass(frozen=True)
class ReferenceObservation:
    """One reference-source read (the runtime-side counterpart of"""

    reachable: bool
    healthy: bool
    quality: str | None = None
    common_mode_group: str | None = None
    offset_bound_ms: int | None = None
    drift_bound_ppm: int | None = None
    uncertainty_bound_ms: int | None = None
    wall_clock_unix_ms: int | None = None


@runtime_checkable
class ReferenceSourceReader(Protocol):
    """A corroborating reference-time source, read on demand."""

    def read(self) -> ReferenceObservation:
        """Return this cycle's observation. MUST NOT raise — see"""
        ...


_LOCAL_SYSTEM_CLOCK_GROUP = "LOCAL_SYSTEM_CLOCK"


class LocalSystemClockReader:
    """Phase 2's only implemented reference source: the local system wall clock."""

    def read(self) -> ReferenceObservation:
        """Read the local wall clock: a reachability probe, AND (G-1, runtime"""
        now_ns = time.time_ns()
        return ReferenceObservation(
            reachable=True,
            healthy=True,
            quality="LOCAL_SYSTEM_CLOCK",
            common_mode_group=_LOCAL_SYSTEM_CLOCK_GROUP,
            wall_clock_unix_ms=now_ns // 1_000_000,
        )
