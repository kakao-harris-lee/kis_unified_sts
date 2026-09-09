"""``replay_engine`` — independent re-derivation over a durable event inbox (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "재생 판정 replay digest 동일").

Rebuilds a FRESH :class:`~tos.engine.EngineCore` (via the injected ``build_core`` factory — never
constructed here) and re-consumes the inbox's own admitted events, in ``seq`` order, comparing each
one's ``EventResult.outcome_digest`` (Phase 3 A-K-3) against the digest this runtime already
durably recorded for it (:mod:`tos_runtime.engine.driver`'s ``EVENT_CONSUMED`` receipts) via
:func:`tos.engine.sink.replay_result_for` — the exact RFC-003 §10:345-348 reproducibility
question that function is built to answer. ``outcome_digest`` is honestly ``None`` for every
``EGRESS_RESULT`` event (a mutable, non-authoritative reservation-projection transition has no
outcome identity of its own), so a stream of only such events trivially compares ``None`` to
``None`` — the kernel's own scope choice, not a gap this module papers over.

**Side-effect scope, reported precisely (plan §1.1's own escape hatch: "if a fully
side-effect-free rebuild is impossible without kernel changes, report precisely").** This module
performs no I/O of its own beyond reading the ``inbox``/``evidence_store`` it is handed, and it
never mutates either. It does NOT, however, make the ``build_core`` factory's own core
side-effect-free — that responsibility belongs to the CALLER's factory. A ``core`` wired with
``transmit=None`` re-derives every event's decision/flow outcome up to (and halting at) step 14
with zero external I/O — this is what :func:`compose_replay_core_from_wiring` (this repo's own
compose wiring) and this module's own hermetic tests use, and it is a genuine, useful replay check:
it re-proves that the SAME strategy, config, and Capsule stream deterministically reach the SAME
decision every time, independent of anything the send boundary did. Re-deriving all the way through
a REAL send boundary's own idempotent replay (so that a fresh core wired with a working transmit
reproduces byte-identical ``POTENTIALLY_LIVE``/fill outcomes without re-sending) needs the send
boundary to expose a recording/replaying transport of its own — the design plan's own §4 rejected
"an async replay loop" but did not yet ratify a synchronous replay transport for the gateway, so
that half is out of this module's scope and is reported here rather than silently assumed away.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.engine import EngineCore
from tos.engine.records import event_identity
from tos.engine.sink import replay_result_for
from tos.evidence import ReplayResultState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["ReplayVerdict", "replay_engine"]

_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"
_REPLAY_DIVERGED_RECORD_CLASS = "REPLAY_DIVERGED"


@dataclass(frozen=True)
class ReplayVerdict:
    """The outcome of one :func:`replay_engine` run.

    ``ok`` is ``True`` iff every compared event's replay state is
    :attr:`~tos.evidence.ReplayResultState.MATCH`. ``diverged`` names the event ids that were not
    — each already durably recorded as a ``REPLAY_DIVERGED`` halt (via
    :func:`~tos_runtime.evidence.emergency.record_halt`) by the time this is returned.
    """

    total_compared: int
    diverged: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Whether every compared event's replay state was ``MATCH``."""
        return len(self.diverged) == 0


def _recorded_outcome_digests(
    evidence_store: SqliteEvidenceStore,
) -> dict[str, str | None]:
    """Read every ``EVENT_CONSUMED`` receipt's recorded ``outcome_digest``, keyed by event id."""
    recorded: dict[str, str | None] = {}
    cur = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (_EVENT_CONSUMED_KIND,),
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json).get("payload", {})
        event_id = payload.get("event_id")
        if event_id is not None:
            recorded[event_id] = payload.get("outcome_digest")
    return recorded


def replay_engine(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    build_core: Callable[[], EngineCore],
    *,
    scheme: CanonicalizationScheme,
    window_events: int | None,
) -> ReplayVerdict:
    """Independently re-derive the inbox's admitted events and compare outcomes.

    Args:
        inbox: The durable event admission queue whose ``replay()`` yields every admitted event
            (consumed or not), in ``seq`` order.
        evidence_store: The durable evidence store this runtime already recorded
            ``EVENT_CONSUMED`` receipts into — the comparison baseline.
        emergency_log: Passed straight through to :func:`~tos_runtime.evidence.emergency.record_halt`
            on a divergence — the same dual-path durability every other boot-time halt uses.
        build_core: A zero-argument factory returning a FRESH :class:`~tos.engine.EngineCore` —
            never constructed here (see module docstring for what "fresh" does and does not
            guarantee about side effects).
        scheme: The canonicalization scheme for the outcome-digest comparison (must be the SAME
            scheme the original run used, or every comparison is vacuously a divergence).
        window_events: Replay only the LAST ``window_events`` admitted events (boot-time cost
            bound); ``None`` replays the whole inbox. Refused if negative or zero — a window that
            replays nothing is not a window, it is disabled, and disabling replay is a decision an
            explicit ``None`` should make, not a ``0``.

            ⚠ **Path-dependency caveat, measured directly (2026-09-09).** A fresh core's
            ``ProvisionalReservationLedger`` starts EMPTY. When an earlier, windowed-out event
            left a reservation outstanding (e.g. ``COMMITTED_UNBOUND``/``ATTEMPT_BOUND`` under
            ``max_unresolved_send_per_scope``'s at-most-one retention, design #31 §4.4), a later
            event's ORIGINAL outcome depended on that outstanding state — replaying only the
            later event in isolation reaches a genuinely DIFFERENT outcome (e.g.
            ``AT_MOST_ONE_EXPOSURE_HELD`` originally vs. an unconstrained admit on replay), which
            this function reports as a divergence even though nothing is actually wrong. A
            windowed replay is therefore sound ONLY when the windowed-out prefix carries no
            ledger state into the window (e.g. every tick outside it was a defined no-action, or
            resolved its reservation before the window starts) — ``window_events=None`` (replay
            the whole inbox, rebuilding the ledger from scratch) is the only generally correct
            choice for a ledger-carrying stream.

    Returns:
        The :class:`ReplayVerdict`.

    Raises:
        ValueError: If ``window_events`` is not ``None`` and not a positive int.
    """
    if window_events is not None and window_events <= 0:
        raise ValueError(
            f"replay_engine window_events must be a positive int or None (got {window_events!r}) "
            "— a zero/negative window is not a smaller replay, it is a silently-disabled one"
        )

    recorded = _recorded_outcome_digests(evidence_store)
    admitted = list(inbox.replay())
    if window_events is not None:
        admitted = admitted[-window_events:]

    core = build_core()
    diverged: list[str] = []
    compared = 0
    for _seq, event in admitted:
        event_id = event_identity(event, scheme=scheme)
        if event_id not in recorded:
            # Nothing to compare against (e.g. outside the replay window's own history, or a row
            # admitted but not yet consumed) — not a divergence, just not yet a baseline.
            continue
        result = core.handle(event)
        actual_digest = result.outcome_digest
        state = replay_result_for(
            expected_outcome_digest=recorded[event_id],
            actual_outcome_digest=actual_digest,
            baseline_supported=True,
            input_complete=True,
        )
        compared += 1
        if state is not ReplayResultState.MATCH:
            diverged.append(event_id)
            record_halt(
                evidence_store,
                emergency_log,
                payload={
                    "event_id": event_id,
                    "expected_outcome_digest": recorded[event_id],
                    "actual_outcome_digest": actual_digest,
                    "replay_result_state": state.value,
                },
                kind=_REPLAY_DIVERGED_KIND,
                record_class=_REPLAY_DIVERGED_RECORD_CLASS,
            )
    return ReplayVerdict(total_compared=compared, diverged=tuple(diverged))
