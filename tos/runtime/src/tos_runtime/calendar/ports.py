"""Wall-clock reference ports for the KST calendar owner (Phase 5 W5 plan §2
decision 2, ``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``; G-1
wiring, ``docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md`` §2
decision 1).

The W5 survey (`scratchpad/w5-survey-runtime.md` §3) established two facts
this module originally had to respect, both since resolved by G-1:

* :class:`~tos_runtime.time.service.TrustworthyTimeService` now DOES surface
  a wall-clock value, through its ``wall_clock_now()`` method — but only
  once the service itself has reached ``HealthState.TRUSTED`` (G-1's own
  gate; see that method's docstring). Before this wave, no such surface
  existed at all.
* A production composition root now wires :class:`TrustedWallClockReference`
  by default (``tos_runtime.compose._session_wiring.build_session_facts_owner``)
  — the honest, fail-closed answer while ``TrustworthyTimeService`` has not
  yet reached TRUSTED is still "no wall-clock reading available", never a
  silently invented one; it is just no longer PERMANENTLY absent.

This module defines the port (:class:`WallClockReference`) and four
implementations. :class:`AbsentWallClockReference` and
:class:`LocalWallClockReference` are retained for the reasons their own
docstrings below give (test-only reproduction of the pre-G-1 state, and
unwired measurement scripts, respectively) — neither is the production
default any longer.
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
    "TrustedWallClockReference",
]


@runtime_checkable
class _WallClockNowSource(Protocol):
    """Structural shape :class:`TrustedWallClockReference` needs from a time
    service — matches
    :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now`
    without importing ``tos_runtime.time.service`` (keeps this module's own
    import surface minimal; no cycle exists either way, but a Protocol here
    documents the ACTUAL dependency: one method, not the whole service)."""

    def wall_clock_now(self) -> int | None: ...


@runtime_checkable
class WallClockReference(Protocol):
    """A source of the current wall-clock instant, read on demand."""

    def read(self) -> WallClockReading | None:
        """Return the current reading, or ``None`` if no wall-clock instant
        is available (e.g. :class:`AbsentWallClockReference`, or a G-1-gated
        production default). MUST NOT raise."""
        ...


class AbsentWallClockReference:
    """**Pre-G-1 state, test-only.** Was the honest production default before
    G-1 landed (``docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md``
    §2 decision 1); a composition root no longer constructs this by default
    (:class:`TrustedWallClockReference` is the default now). Kept so a test
    can still exercise/reproduce the pre-G-1 "no wall-clock reference wired
    at all" shape explicitly.

    A caller that needs to explain WHY (e.g. for a boot-time evidence entry)
    can call :meth:`describe`.
    """

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
    """Reads the real local system wall clock (``time.time()``) directly,
    UNGATED by ``TrustworthyTimeService``'s health state.

    **Superseded by** :class:`TrustedWallClockReference` **as the production
    default** (G-1, runtime operations wiring plan §2 decision 1) — that
    class reads the SAME kind of value but only once the time service itself
    has reached ``HealthState.TRUSTED``, which this class never checks.
    Still unwired anywhere in compose; kept for standalone measurement
    scripts that want a bare wall-clock read with no gate at all.
    """

    def read(self) -> WallClockReading | None:
        return WallClockReading(
            unix_ms=int(time.time() * 1000),
            source_label="local-system-clock",
        )


class TrustedWallClockReference:
    """The production default wall-clock reference (G-1, runtime operations
    wiring plan §2 decision 1): reads
    :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now`,
    which itself returns ``None`` unless the service's ``health_state`` is
    ``HealthState.TRUSTED`` — so this reference is honestly absent
    (``read() -> None``) during ``SYNCHRONIZING``/``DEGRADED_HOLDOVER``/
    ``UNTRUSTED``, never fabricating a reading from an unproven time base.

    Args:
        time_service: Anything shaped like
            :class:`~tos_runtime.time.service.TrustworthyTimeService` (see
            :class:`_WallClockNowSource`) — typically the SAME instance a
            composition root's boot sequence already built and ran
            ``start()``/``evaluate()`` on.
    """

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
