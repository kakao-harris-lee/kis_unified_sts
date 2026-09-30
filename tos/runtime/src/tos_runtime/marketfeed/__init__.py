"""``tos_runtime.marketfeed`` — the Context Integrity Service runtime + the tick source
(plan ``docs/plans/2026-09-16-tos-tick-source-plan.md``).

Resolves ``compose/cli.py``'s blocker (c) — "No tick source. Nothing in ``tos_runtime`` produces a
``DECISION_TICK`` from a live market feed or a clock" — by supplying the producer side the kernel
deliberately does not own: observation intake, governed snapshot issuance, durable content-
addressed storage, Capsule issuance, the time-coordinate projection, and the scheduler that drives
:class:`~tos_runtime.engine.driver.EngineDriver`.

⚠ **It does not make the feed live by itself.** This wave ships one intake implementation — a
file-backed observation journal written by an upstream collector — so the honest description of
the result is "a tick source with a journal-backed feed", not "a live market feed". A real quote
transport is a named follow-up (plan §6 ①).

The kernel side is untouched: :class:`~tos.marketfeed.MarketFeedContextResolver` is injected as
shipped, and this package implements only its three ports.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``pyyaml`` + ``tos_runtime.*``. No ``shared.*``.
"""

from __future__ import annotations

from tos_runtime.marketfeed.ports import (
    DurableSnapshotStore,
    ObservationIntake,
    RawObservation,
    TickOutcome,
)

__all__ = [
    "DurableSnapshotStore",
    "ObservationIntake",
    "RawObservation",
    "TickOutcome",
]
