"""Possibly-live attempt reconstruction (TOS Phase 5 W1; plan §2 decision 2; Phase 3 carryover
ⓗ — design #31 §9-7 "크래시 후 possibly-live attempt 의 인메모리 원장 보수 재구성").

**What "possibly live" means here, precisely.** Independent review finding #3
(:mod:`tos_runtime.engine.driver`'s own module docstring, "the WIDEST of the three crash
windows") already identifies the exact durable shape: an inbox row whose
``EVENT_HANDLING_STARTED`` write-ahead marker is durably recorded
(:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.handling_started_receipt`) but which has
**no** ``EVENT_CONSUMED`` receipt at all (:meth:`~tos_runtime.engine.inbox.SqliteEventInbox
.is_consumed` is ``False``). That is the crash window in which the interrupted flow may already
have reached the send boundary before the process died — the broker-side fate is genuinely
unknown until reconciled.

**Why this module exists separately from the driver's own crash-window recovery.** The driver's
:meth:`~tos_runtime.engine.driver.EngineDriver._process_next` ALREADY drains this exact window —
but only **lazily**, the first time a caller drives an event through the driver
(``run_once``/``enqueue_and_run``). This module reconstructs the SAME set independently, using
only the inbox's already-public surface (``replay()``, ``is_consumed()``,
``handling_started_receipt()`` — never a private driver method), so
:mod:`tos_runtime.recovery.barrier` can see the possibly-live set and hold the barrier BEFORE the
driver ever gets a chance to run at all (the whole point of a boot-time barrier: the driver's own
auto-drain durably "consumes" the row with a ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` halt
reason, but that accounting is not the same thing as broker-side reconciliation — a possibly-live
attempt must not silently unblock new-risk authority just because the driver's bookkeeping caught
up).

**Conservative by construction (design #17 §4.1's "no assume-complete" discipline, applied at the
runtime layer).** Any row with a handling-started marker and no consumed receipt is INCLUDED,
unconditionally — there is no partial-evidence branch that excludes one. An under-count here
would be the fail-open this whole barrier exists to prevent (mirrors the sbr
``_reachability_closure``'s own "an uncertain edge is expanded, never dropped" discipline,
``tos/src/tos/sbr/predicates.py``).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.engine.records import event_identity

from tos_runtime.engine.inbox import SqliteEventInbox

__all__ = ["PossiblyLiveAttempt", "reconstruct_possibly_live_attempts"]


@dataclass(frozen=True)
class PossiblyLiveAttempt:
    """One inbox row caught in the finding-#3 crash window (module docstring).

    Attributes:
        event_id: The content-addressed event identity
            (:func:`tos.engine.records.event_identity`) of the interrupted admitted event.
        inbox_seq: The inbox's own ``seq`` for this row — the handle a caller (e.g. a future
            :class:`~tos_runtime.recon.service.ReconciliationService` consumer) uses to address
            it durably.
        handling_started_evidence_seq: The durable ``EVENT_HANDLING_STARTED`` receipt's own
            evidence ``seq`` — proof the interrupted flow reached the send boundary before the
            crash (independent review finding #3).
        handling_started_generation: The evidence store's signing-key generation at the time of
            that receipt.
    """

    event_id: str
    inbox_seq: int
    handling_started_evidence_seq: int
    handling_started_generation: int


def reconstruct_possibly_live_attempts(
    inbox: SqliteEventInbox, *, scheme: CanonicalizationScheme
) -> tuple[PossiblyLiveAttempt, ...]:
    """Reconstruct every possibly-live attempt from the durable inbox alone (module docstring).

    Iterates every admitted row (:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.replay`, in
    ``seq`` order) and keeps exactly the rows that are NOT consumed
    (:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.is_consumed`) but DO carry a durable
    ``EVENT_HANDLING_STARTED`` marker
    (:meth:`~tos_runtime.engine.inbox.SqliteEventInbox.handling_started_receipt`). A row that was
    never started at all (no marker) is ordinary "pending, never touched" — not possibly-live,
    and not returned here (see :mod:`tos_runtime.recovery.inputs`' own ``inbox_unconsumed_count``
    for that broader count).

    Args:
        inbox: The durable event admission queue to inspect — read-only, never mutated.
        scheme: The canonicalization scheme used to derive each event's content-addressed
            ``event_id`` (must be the SAME scheme the runtime composed this inbox with).

    Returns:
        Every possibly-live attempt, in inbox ``seq`` order. Empty when none exist.
    """
    attempts: list[PossiblyLiveAttempt] = []
    for seq, event in inbox.replay():
        if inbox.is_consumed(seq):
            continue
        started = inbox.handling_started_receipt(seq)
        if started is None:
            continue  # never started -- ordinary pending, not possibly-live
        evidence_seq, generation = started
        attempts.append(
            PossiblyLiveAttempt(
                event_id=event_identity(event, scheme=scheme),
                inbox_seq=seq,
                handling_started_evidence_seq=evidence_seq,
                handling_started_generation=generation,
            )
        )
    return tuple(attempts)
