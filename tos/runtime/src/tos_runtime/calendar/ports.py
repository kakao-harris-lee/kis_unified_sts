"""Wall-clock reference ports for the KST calendar owner (Phase 5 W5 plan §2"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from tos_runtime.calendar.model import WallClockReading

__all__ = [
    "WallClockReference",
    "AbsentWallClockReference",
    "FixedWallClockReference",
    "LocalWallClockReference",
    "TrustedWallClockReference",
]


@runtime_checkable
class _WallClockNowSource(Protocol):
    """Structural shape :class:`TrustedWallClockReference` needs from a time"""

    def wall_clock_now(self) -> int | None: ...


@runtime_checkable
class WallClockReference(Protocol):
    """A source of the current wall-clock instant, read on demand."""

    def read(self) -> WallClockReading | None:
        """Return the current reading, or ``None`` if no wall-clock instant"""
        ...


class AbsentWallClockReference:
    """**Pre-G-1 state, test-only.** Was the honest production default before"""

    def describe(self) -> str:
        """Return a short, human-readable reason this reference is absent."""
        return (
            "no wall-clock reference wired: explicit AbsentWallClockReference "
            "injection (pre-G-1 state) — plan "
            "docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md §2 "
            "decision 1"
        )

    def read(self) -> WallClockReading | None:
        return None


class FixedWallClockReference:
    """Test-only: reports a fixed instant, injected at construction."""

    def __init__(self, unix_ms: int, source_label: str = "fixed-test") -> None:
        self._unix_ms = unix_ms
        self._source_label = source_label

    def read(self) -> WallClockReading | None:
        return WallClockReading(unix_ms=self._unix_ms, source_label=self._source_label)


class LocalWallClockReference:
    """Reads the real local system wall clock (``time.time()``) directly,"""

    def read(self) -> WallClockReading | None:
        return WallClockReading(
            unix_ms=int(time.time() * 1000),
            source_label="local-system-clock",
        )


class TrustedWallClockReference:
    """The production default wall-clock reference (G-1, runtime operations"""

    def __init__(self, time_service: _WallClockNowSource) -> None:
        self._time_service = time_service

    def describe(self) -> str:
        """Return a short, human-readable description of this gate."""
        return (
            "trusted-time-service wall-clock reference: reads "
            "TrustworthyTimeService.wall_clock_now(), gated on "
            "HealthState.TRUSTED (G-1, plan "
            "docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md §2 "
            "decision 1)"
        )

    def read(self) -> WallClockReading | None:
        unix_ms = self._time_service.wall_clock_now()
        if unix_ms is None:
            return None
        return WallClockReading(unix_ms=unix_ms, source_label="trusted-time-service")


class _FreshWallClockNowSource(Protocol):
    """The slice of :class:`~tos_runtime.time.service.TrustworthyTimeService` that"""

    def wall_clock_now_if_fresh(self, max_age_ms: int) -> int | None: ...


class FreshTrustedWallClockReference:
    """A :class:`TrustedWallClockReference` that is also bounded in AGE: a reading only while the"""

    def __init__(self, time_service: _FreshWallClockNowSource, max_age_ms: int) -> None:
        self._time_service = time_service
        self._max_age_ms = max_age_ms

    def describe(self) -> str:
        """Return a short, human-readable description of this gate."""
        return (
            "fresh trusted-time wall-clock reference: TrustworthyTimeService."
            f"wall_clock_now_if_fresh(max_age_ms={self._max_age_ms})"
        )

    def read(self) -> WallClockReading | None:
        unix_ms = self._time_service.wall_clock_now_if_fresh(self._max_age_ms)
        if unix_ms is None:
            return None
        return WallClockReading(
            unix_ms=unix_ms, source_label="fresh-trusted-time-service"
        )
