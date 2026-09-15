"""Pure data records for the KST trading calendar (Phase 5 W5 plan §2 decision
1 — see :mod:`tos_runtime.calendar.config`/:mod:`tos_runtime.calendar.phase`).

None of these types carry any behavior; they are the frozen record shapes
:mod:`tos_runtime.calendar.phase` produces and :mod:`tos_runtime.calendar.ports`
(and, in a later lane, ``tos_runtime.calendar.owner``) consume.
"""

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
    """The session-phase token observed for one instrument class at one
    instant, per :func:`tos_runtime.calendar.phase.session_phase_at` (or its
    maturity-aware counterpart, :func:`~tos_runtime.calendar.phase.effective_phase_at`).

    ``phase`` is an opaque string token defined entirely by the calendar
    config (never a runtime enum — the kernel's own ``SessionPhase`` is
    deliberately not an enum either, per the W5 survey). ``phase``/``is_open``/
    ``boundary_unix_ms`` are all ``None`` together exactly when the
    instrument class is not known to the calendar config at all — a fact this
    module refuses to guess (never invented as a default).
    """

    phase: str | None
    is_open: bool | None
    boundary_unix_ms: int | None
    source: str
    calendar_version: str


@dataclass(frozen=True)
class MaturityFact:
    """The futures-expiry state for one instrument class at one instant, per
    :func:`tos_runtime.calendar.phase.maturity_at`.

    ``rule_present=False`` (with ``expiry_date``/``expired`` both ``None``)
    means the calendar config carries no ``futures_expiry`` rule for this
    instrument class — this is not the same as ``expired=False``, which means
    a rule exists and the instant is before its expiry.
    """

    expiry_date: datetime.date | None
    expired: bool | None
    rule_present: bool


@dataclass(frozen=True)
class WallClockReading:
    """One wall-clock observation, per :mod:`tos_runtime.calendar.ports`.

    ``source_label`` names which :class:`~tos_runtime.calendar.ports.WallClockReference`
    implementation produced the reading (e.g. ``"fixed-test"``,
    ``"local-system-clock"``) — never inferred, always the label the port
    itself declares.
    """

    unix_ms: int
    source_label: str
