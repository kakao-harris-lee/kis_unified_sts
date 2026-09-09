"""``replay_engine`` — independent re-derivation over a durable event inbox (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "재생 판정 replay digest 동일").

Rebuilds a FRESH :class:`~tos.engine.EngineCore` (via the injected ``build_core`` factory — never
constructed here) and re-consumes the inbox's own admitted events, in ``seq`` order, comparing each
one's ``EventResult.outcome_digest`` (Phase 3 A-K-3) against the digest this runtime already
durably recorded for it (:mod:`tos_runtime.engine.driver`'s ``EVENT_CONSUMED`` receipts) via
:func:`tos.engine.sink.replay_result_for` — the exact RFC-003 §10:345-348 reproducibility
question that function is built to answer. ``outcome_digest`` is honestly ``None`` for every
``EGRESS_RESULT`` event (a mutable, non-authoritative reservation-projection transition has no
outcome identity of its own) — the kernel's own scope choice, not a gap this module papers over.

**Independent review finding #1/#11 (2026-09-09), corrected here.** A prior revision of this
docstring claimed a stream of only ``EGRESS_RESULT`` events "trivially compares ``None`` to
``None``" — the opposite is true: feeding ``None``/``None`` into
:func:`~tos.evidence.compute_replay_result` (via :func:`~tos.engine.sink.replay_result_for`)
returns ``ReplayResultState.INCONCLUSIVE``, not ``MATCH`` (that function's own "expected/actual
digest is present and equal" rule for ``MATCH``), and this module used to treat any non-``MATCH``
state as a divergence — reporting a permanent, un-recoverable boot-time
:class:`~tos_runtime.compose._boot_integrity.EngineReplayDiverged` for every event whose recorded
baseline digest is ``None``, i.e. every event AFTER the first real send hand-off, forever. This
function now SKIPS the comparison (never calls :func:`~tos.engine.sink.replay_result_for` at
all) ONLY in the one honest case — recorded digest ``None`` AND replayed digest ``None``, "no
outcome identity to compare" — counting it in :attr:`ReplayVerdict.uncompared` rather than
:attr:`ReplayVerdict.total_compared`. Every OTHER combination still goes through the normal
comparison and is treated as a divergence exactly as before: a ``None``-recorded /
non-``None``-replayed pair (or the reverse) still reaches
:func:`~tos.evidence.compute_replay_result` and comes back ``INCONCLUSIVE`` (non-``MATCH``), and
two present-but-different digests still come back ``DIVERGED`` — this fix narrows the skip to
exactly the ``None``/``None`` pair; it does not widen it.

**Side-effect scope, reported precisely (plan §1.1's own escape hatch: "if a fully
side-effect-free rebuild is impossible without kernel changes, report precisely").** This module
performs no I/O of its own beyond reading the ``inbox``/``evidence_store`` it is handed, and it
never mutates either. It does NOT, however, make the ``build_core`` factory's own core
side-effect-free — that responsibility belongs to the CALLER's factory; this module only compares
whatever ``EventResult.outcome_digest`` that factory's core produces. **Independent review
finding #2 (2026-09-09), corrected here**: this repo's own compose wiring
(:func:`tos_runtime.compose._engine_wiring.verify_replay_or_halt`) now builds its replay core
with ``transmit=None`` AND a genuinely side-effect-free stand-in
(:class:`tos_runtime.compose._engine_wiring._ReplayStage`) for every injected commitment-flow
stage — not the real stages, which each carry their OWN evidence sink bound to the real durable
store, independent of whatever sink the replay ``EngineCore`` itself is given. Since
``EventResult.outcome_digest`` is always the DECISION PIPELINE's own digest, computed strictly
BEFORE the 19-step commitment flow starts (``tos/src/tos/engine/core.py``'s
``EngineCore._run_entries``), a stand-in that halts the flow at the very first injected step
cannot affect the comparison this module performs — see :class:`_ReplayStage`'s own docstring for
the full measurement. Re-deriving all the way through a REAL send boundary's own idempotent
replay (so that a fresh core wired with a WORKING transmit reproduces byte-identical
``POTENTIALLY_LIVE``/fill outcomes without re-sending) needs the send boundary to expose a
recording/replaying transport of its own — the design plan's own §4 rejected "an async replay
loop" but did not yet ratify a synchronous replay transport for the gateway, so that half is out
of this module's scope and is reported here rather than silently assumed away.

**``window_events`` path-dependency caveat, measured directly (2026-09-09).** A fresh core's
``ProvisionalReservationLedger`` starts EMPTY. When an earlier, windowed-out event left a
reservation outstanding (e.g. ``COMMITTED_UNBOUND``/``ATTEMPT_BOUND`` under
``max_unresolved_send_per_scope``'s at-most-one retention, design #31 §4.4), a later event's
ORIGINAL outcome depended on that outstanding state — replaying only the later event in isolation
reaches a genuinely DIFFERENT outcome (e.g. ``AT_MOST_ONE_EXPOSURE_HELD`` originally vs. an
unconstrained admit on replay), which :func:`replay_engine` reports as a divergence even though
nothing is actually wrong. A windowed replay is therefore sound ONLY when the windowed-out prefix
carries no ledger state into the window (e.g. every tick outside it was a defined no-action, or
resolved its reservation before the window starts) — ``window_events=None`` (replay the whole
inbox, rebuilding the ledger from scratch) is the only generally correct choice for a
ledger-carrying stream.
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

    ``uncompared`` (independent review finding #1, 2026-09-09) counts events for which the
    RECORDED baseline digest AND the REPLAYED digest were both ``None`` — "no outcome identity to
    compare" (every ``EGRESS_RESULT`` event is honestly like this; see the module docstring). This
    is deliberately NOT part of ``total_compared``: it was never a comparison at all, and it is
    NOT a divergence either — ``ok`` does not consult it. An asymmetric ``None``/non-``None`` pair
    is a genuine divergence and is counted in ``total_compared``/``diverged`` as before, never
    here.
    """

    total_compared: int
    diverged: tuple[str, ...]
    uncompared: int = 0

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
            explicit ``None`` should make, not a ``0``. ⚠ See the module docstring's own
            "``window_events`` path-dependency caveat" for why ``None`` is the only generally
            correct choice for a ledger-carrying stream.

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
    uncompared = 0
    for _seq, event in admitted:
        event_id = event_identity(event, scheme=scheme)
        if event_id not in recorded:
            # Nothing to compare against (e.g. outside the replay window's own history, or a row
            # admitted but not yet consumed) — not a divergence, just not yet a baseline.
            continue
        expected_digest = recorded[event_id]
        # Always re-derive the event's outcome (this advances the SAME core's ledger state for
        # every subsequent event in the stream) even when the comparison below is skipped.
        result = core.handle(event)
        actual_digest = result.outcome_digest
        if expected_digest is None and actual_digest is None:
            # Independent review finding #1: neither side has an outcome identity to compare
            # (e.g. an EGRESS_RESULT event — tos.engine.core.EventResult.outcome_digest is
            # honestly None for every one of them). This is "no outcome identity", not a
            # divergence — see the module docstring and ReplayVerdict.uncompared.
            uncompared += 1
            continue
        state = replay_result_for(
            expected_outcome_digest=expected_digest,
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
                    "expected_outcome_digest": expected_digest,
                    "actual_outcome_digest": actual_digest,
                    "replay_result_state": state.value,
                },
                kind=_REPLAY_DIVERGED_KIND,
                record_class=_REPLAY_DIVERGED_RECORD_CLASS,
            )
    return ReplayVerdict(
        total_compared=compared, diverged=tuple(diverged), uncompared=uncompared
    )
