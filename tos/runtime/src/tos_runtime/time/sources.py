"""Injectable monotonic + reference-clock source ports (slice plan §1 item 1).

This module is the first place in either distribution that reads a real clock:
the ``tos.time`` kernel package is clock-free by design (time design §0.3 — it
only ever sees opaque injected coordinates), and design #40 D1 assigns exactly
this responsibility to the runtime shell. Both ports are injected into
:class:`~tos_runtime.time.service.TrustworthyTimeService` so tests can supply a
fake source without touching a real clock (D1.4 hermetic discipline — a real
clock read is not itself a network/filesystem access, but a test asserting
FSM/fault-contract behavior needs a *controllable* clock, not a wall one).

Unit convention: every value this module produces is **whole milliseconds**,
matching the VER-002 profile keys' ``_ms`` naming (``MAX_time_source_precision_ms``
etc., :mod:`tos_runtime.time.config`) so the service never mixes nanosecond and
millisecond magnitudes when it feeds a bound into a kernel predicate.
``ProcessMonotonicSource`` truncates ``time.monotonic_ns()`` to whole
milliseconds; sub-millisecond precision is not needed at this slice's
evaluation cadence (a periodic health check, not a hot trading path).
"""

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
        """Return the current monotonic reading, in whole milliseconds.

        The returned value is only meaningful relative to another reading from
        the SAME source instance within the SAME process lifetime (time design
        §3/§4.1 "never compared across process or host identities") — never
        persisted or compared across a restart.
        """
        ...


class ProcessMonotonicSource:
    """Wraps ``time.monotonic_ns()`` — the kernel-forbidden clock read, made
    real exactly once, here, in the runtime shell (design #40 D1)."""

    def now_ms(self) -> int:
        """Return ``time.monotonic_ns() // 1_000_000`` (truncated to whole ms)."""
        return time.monotonic_ns() // 1_000_000


@dataclass(frozen=True)
class ReferenceObservation:
    """One reference-source read (the runtime-side counterpart of
    ``tos.time.ReferenceSource``, before the kernel record is constructed).

    ``reachable``/``healthy`` are the fail-closed gate: a reader that could not
    reach or validate its source reports ``reachable=False``/``healthy=False``
    rather than raising, so :class:`~tos_runtime.time.service.TrustworthyTimeService`
    can treat "source unavailable" (fault contract ⑦) as an ordinary observation
    fed to the kernel's ``freshness_verdict``/``independent_reference_count``,
    not as an exception path the service must separately catch.
    """

    reachable: bool
    healthy: bool
    quality: str | None = None
    common_mode_group: str | None = None
    offset_bound_ms: int | None = None
    drift_bound_ppm: int | None = None
    uncertainty_bound_ms: int | None = None


@runtime_checkable
class ReferenceSourceReader(Protocol):
    """A corroborating reference-time source, read on demand."""

    def read(self) -> ReferenceObservation:
        """Return this cycle's observation. MUST NOT raise — see
        :class:`ReferenceObservation`'s docstring on the fail-closed
        ``reachable``/``healthy`` flags."""
        ...


class LocalSystemClockReader:
    """Phase 2's only implemented reference source: the local system wall clock.

    Named explicitly as a single-source residual (ADR-002-008 :184; slice plan
    §1 item 1): NTP and any broker-time reference are NOT implemented here. A
    verification profile requiring more than one independent reference
    (``MIN_time_independent_reference_count`` > 1,
    :mod:`tos_runtime.time.config`) can therefore never be satisfied by this
    reader alone — a conservative, honestly-reported outcome
    (``tos.time.independent_reference_count`` reports exactly ``1``), not a gap
    this reader tries to paper over. No ``common_mode_group`` is declared
    (``None``): with only one physical source in this process, no shared-clock
    membership is known or claimed.
    """

    def read(self) -> ReferenceObservation:
        """Read the local wall clock once, as a reachability probe.

        The wall-clock VALUE itself is never surfaced beyond this reachability
        check — no predicate in ``tos.time`` reads ``LOCAL_WALL`` as a
        freshness/ordering basis (time design §4.2), so this reader's only
        job is to prove the local clock subsystem answers at all.
        """
        time.time_ns()
        return ReferenceObservation(
            reachable=True,
            healthy=True,
            quality="LOCAL_SYSTEM_CLOCK",
            common_mode_group=None,
        )
