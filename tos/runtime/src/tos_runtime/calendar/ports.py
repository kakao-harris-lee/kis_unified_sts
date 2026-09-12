"""Wall-clock reference ports for the KST calendar owner (Phase 5 W5 plan §2
decision 2, ``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``).

The W5 survey (`scratchpad/w5-survey-runtime.md` §3) established two facts
this module must respect:

* :class:`~tos_runtime.time.service.TrustworthyTimeService` never surfaces a
  wall-clock VALUE — only a reachability probe
  (:mod:`tos_runtime.time.sources`'s ``LocalSystemClockReader``, whose own
  docstring calls this the "wall-clock value non-exposure" decision). A
  session/calendar owner therefore cannot derive "what KST time is it now"
  from ``TrustworthyTimeService`` as currently wired.
* Wiring a real wall clock into production composition is gated on operator
  decision **G-1** (plan §6 ①) — until that decision lands, the honest,
  fail-closed answer is "no wall-clock reading available", not a silently
  invented one.

So this module defines the port (:class:`WallClockReference`) and THREE
implementations, but **no code in this package wires
:class:`LocalWallClockReference` into compose** — that one-line wiring change
is explicitly reserved for after the G-1 decision (plan §6 ①). The
production default a composition root should use today is
:class:`AbsentWallClockReference`.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from tos_runtime.calendar.model import WallClockReading

__all__ = [
    "WallClockReference",
    "AbsentWallClockReference",
    "FixedWallClockReference",
    "LocalWallClockReference",
]


@runtime_checkable
class WallClockReference(Protocol):
    """A source of the current wall-clock instant, read on demand."""

    def read(self) -> WallClockReading | None:
        """Return the current reading, or ``None`` if no wall-clock instant
        is available (e.g. :class:`AbsentWallClockReference`, or a G-1-gated
        production default). MUST NOT raise."""
        ...


class AbsentWallClockReference:
    """The honest production default (G-1 pending, module docstring): always
    reports no wall-clock reading is available.

    A caller that needs to explain WHY (e.g. for a boot-time evidence entry)
    can call :meth:`describe`.
    """

    def describe(self) -> str:
        """Return a short, human-readable reason this reference is absent."""
        return (
            "no wall-clock reference wired: G-1 (production wall-clock "
            "exposure) is pending operator decision — plan "
            "docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md §6 ①"
        )

    def read(self) -> WallClockReading | None:
        return None


class FixedWallClockReference:
    """Test-only: reports a fixed instant, injected at construction.

    Never used in production composition — this is the deterministic clock a
    test drives to exercise :mod:`tos_runtime.calendar.phase` at chosen
    instants without depending on the real wall clock.
    """

    def __init__(self, unix_ms: int, source_label: str = "fixed-test") -> None:
        self._unix_ms = unix_ms
        self._source_label = source_label

    def read(self) -> WallClockReading | None:
        return WallClockReading(unix_ms=self._unix_ms, source_label=self._source_label)


class LocalWallClockReference:
    """Reads the real local system wall clock (``time.time()``).

    **Not wired anywhere in compose** (module docstring — the G-1 gate). This
    class exists so the G-1 decision, once made, is a one-line wiring change
    rather than new code; until then, no CLI flag or compose path constructs
    it in this codebase.
    """

    def read(self) -> WallClockReading | None:
        return WallClockReading(
            unix_ms=int(time.time() * 1000),
            source_label="local-system-clock",
        )
