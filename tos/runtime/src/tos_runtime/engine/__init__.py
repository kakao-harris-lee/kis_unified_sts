"""``tos_runtime.engine`` — durable event admission, driving, and replay (TOS Phase 3 Wave 1
Lane A-R; plan ``docs/plans/2026-09-09-tos-phase3-event-core-plan.md`` §1.1).

Closes the survey gap the plan's own §0 recorded: before this package existed, no runtime code
ever called :meth:`~tos.engine.EngineCore.handle`/``run`` at all — every compose end-to-end test
built an :class:`~tos.engine.EngineEvent` directly and fed it straight to the core, and a send
boundary's re-injected results were never enqueued anywhere.

[A-R-1] :mod:`tos_runtime.engine.inbox` — :class:`~tos_runtime.engine.inbox.SqliteEventInbox`, a
durable, single-writer admission queue in its **own** sqlite file, separate from the Evidence
Store (D3 failure-domain separation — a queue's consumption marker is a mutable UPDATE; an
evidence entry is append-only forever, and the two must never share a fault domain).

[A-R-2] :mod:`tos_runtime.engine.driver` — :class:`~tos_runtime.engine.driver.EngineDriver`, the
single place that calls :meth:`~tos.engine.EngineCore.handle` in this whole runtime shell. It owns
the yield-order coordinate stamping (mirroring :class:`tos.backtest.driver.YieldOrderCounter`'s
documented reasoning, reimplemented locally rather than importing the backtest harness package
into production runtime code), the crash-window idempotency check, and the send-boundary result
re-injection loop. The replay module lands in [A-R-3].

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*``
only. No ``shared.*``, no ``tos.backtest`` (a harness package, not a production dependency).
"""

from __future__ import annotations

from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import InboxReceipt, SqliteEventInbox

__all__ = [
    "EngineDriver",
    "InboxReceipt",
    "SqliteEventInbox",
]
