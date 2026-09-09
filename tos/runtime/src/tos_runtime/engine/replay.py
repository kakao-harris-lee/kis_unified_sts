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
all) in the one honest EGRESS_RESULT case — recorded digest ``None`` AND replayed digest
``None``, "no outcome identity to compare" — counting it in :attr:`ReplayVerdict.uncompared`
rather than :attr:`ReplayVerdict.total_compared`. Every OTHER combination still goes through the
normal comparison and is treated as a divergence exactly as before: a ``None``-recorded /
non-``None``-replayed pair (or the reverse) still reaches
:func:`~tos.evidence.compute_replay_result` and comes back ``INCONCLUSIVE`` (non-``MATCH``), and
two present-but-different digests still come back ``DIVERGED`` — this fix narrows the skip to
exactly the ``None``/``None`` pair; it does not widen it. (Wave 2's own finding #1 below widens
the skip once more, to a DIFFERENT, narrowly-identified case — a recorded halt — never to a bare
``None``/non-``None`` asymmetry with no halt reason attached.)

**Independent review finding #1, wave 2 (2026-09-09), corrected here — a SEPARATE half of
finding #1 from the EGRESS_RESULT case above.** A ``DECISION_TICK`` refused by the kernel's own
RFC-002 §10.7 Coordinator gate (``tos.engine.core.EngineCore._coordinator_precondition_refusal``
— ``HaltReason.AUTHORITY_NOT_CURRENT`` / ``LIVE_SCOPE_NOT_AUTHORIZED``, or any other halt
reached before the decision pipeline ever ran) ALSO records ``outcome_digest=None`` on its
``EVENT_CONSUMED`` receipt — but WITH a ``halt_reason``, unlike the honest EGRESS_RESULT case
above. The boot-time replay core's own ``CoordinatorPreconditions`` stand-in
(:class:`tos_runtime.compose._preconditions._ReplayPreconditions`) is unconditionally
``True``/``True`` — by design, per its own docstring, because "a tick the gate refused at the
time never produced pipeline evidence to replay in the first place". That premise is exactly
what this receipt disproves: refused ticks DO get an ``EVENT_CONSUMED`` receipt (``outcome_
digest=None``, real ``halt_reason``). So without this fix, replay would run the FULL pipeline
for a historically-refused tick, manufacture a real, non-``None`` digest, and reach the exact
``None``-recorded/non-``None``-replayed asymmetry the paragraph above already treats as a
divergence — a single Coordinator-gate refusal (reachable via nothing more than a transient
``sqlite3.Error`` on the authority-epoch log) permanently bricking every later boot. The fix:
:func:`_recorded_receipts` now reads ``halt_reason`` alongside ``outcome_digest``, and
:func:`replay_engine` counts a receipt as :attr:`ReplayVerdict.uncompared` (the reason preserved
in :attr:`ReplayVerdict.uncompared_halt_reasons`) when ``outcome_digest`` is ``None`` AND
``halt_reason`` is one of :data:`_PRE_PIPELINE_HALT_REASONS` — the CLOSED set of halt reasons
that are STRUCTURALLY reached before ``EventResult.pipeline`` is ever populated (see that
constant's own docstring for why this must be a closed set, not "any halt_reason": several other
halt reasons, e.g. ``TRANSMIT_UNAVAILABLE``, are reached AFTER a real proposal already gave the
receipt a real, non-``None`` digest, and must still be compared — an earlier draft of this fix
treated any halt as uncompared and silently broke exactly that case, caught by this module's own
``test_mutated_recorded_outcome_digest_is_detected_as_a_divergence``). For a genuine pre-pipeline
halt, ``core.handle`` is never even called for it (unlike the EGRESS_RESULT case, which still
re-derives to advance ledger state honestly; here the live run's own ``HaltReason`` accounting
already establishes "nothing is consumed", so skipping the call reproduces the live run's ledger
state exactly, rather than manufacturing a divergent one). A ``None``/non-``None`` asymmetry with
no recorded ``halt_reason``, or with a halt reason outside the closed set, still reaches the
normal comparison and is still reported as a divergence; this fix does not touch that path.

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
from tos.engine.vocabulary import HaltReason
from tos.evidence import ReplayResultState

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["ReplayVerdict", "replay_engine"]

_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"
_REPLAY_DIVERGED_RECORD_CLASS = "REPLAY_DIVERGED"

#: ``HaltReason`` members that are STRUCTURALLY reached BEFORE any decision pipeline runs
#: (``tos.engine.core.EngineCore.handle`` / ``_handle_decision_tick`` /
#: ``_coordinator_precondition_refusal``) — for every one of these, ``EventResult.pipeline`` is
#: unconditionally ``None`` (never populated: each is returned directly, with no ``pipeline=``
#: argument), so ``outcome_digest`` is unconditionally ``None`` too, in EVERY run, structurally —
#: not merely as an artifact of what happened to occur this particular time. This is the ONLY
#: set of halt reasons :func:`replay_engine` treats as "never ran the pipeline" (independent
#: review finding #1, wave 2, 2026-09-09). Every OTHER halt reason (e.g. ``TRANSMIT_UNAVAILABLE``,
#: ``STAGE_DENIED``, ``NO_ACTION_OUTCOME`` when reached WITH a proposal already produced, ...) is
#: reached from inside ``_run_entries`` AFTER a real proposal already gave ``EventResult.pipeline``
#: a real, non-``None`` ``outcome_digest`` — a receipt carrying one of THOSE halt reasons must
#: still go through the normal digest comparison; treating ANY ``halt_reason`` as "uncompared"
#: would silently swallow a genuine divergence for one of those (measured directly against this
#: module's own test suite: ``test_mutated_recorded_outcome_digest_is_detected_as_a_divergence``
#: halts at ``TRANSMIT_UNAVAILABLE`` with a REAL recorded digest and must still be compared and
#: caught as a divergence when that digest is tampered with).
_PRE_PIPELINE_HALT_REASONS: frozenset[str] = frozenset(
    {
        HaltReason.AUTHORITY_NOT_CURRENT.value,
        HaltReason.LIVE_SCOPE_NOT_AUTHORIZED.value,
        HaltReason.EVENT_ORDER_REVERSED.value,
        HaltReason.REGISTRY_MISSING.value,
        HaltReason.REGISTRY_EXPLICIT_EMPTY.value,
    }
)


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
    #: Independent review finding #1, wave 2 (2026-09-09, lane C-R2): ``(event_id, halt_reason)``
    #: pairs for receipts counted in ``uncompared`` specifically because the LIVE run's own
    #: receipt already carried a ``halt_reason`` (a Coordinator-gate refusal —
    #: ``AUTHORITY_NOT_CURRENT`` / ``LIVE_SCOPE_NOT_AUTHORIZED`` — or any other halt that never
    #: reached the pipeline) — never populated for the wave-1 EGRESS_RESULT
    #: None-recorded/None-replayed case (that one carries no reason to report; see
    #: :func:`replay_engine`'s own docstring for why the two cases are distinguished).
    uncompared_halt_reasons: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        """Whether every compared event's replay state was ``MATCH``."""
        return len(self.diverged) == 0


@dataclass(frozen=True)
class _RecordedReceipt:
    """One durable ``EVENT_CONSUMED`` receipt's comparison-relevant fields."""

    outcome_digest: str | None
    halt_reason: str | None


def _recorded_receipts(
    evidence_store: SqliteEvidenceStore,
) -> dict[str, _RecordedReceipt]:
    """Read every ``EVENT_CONSUMED`` receipt's recorded ``outcome_digest``/``halt_reason``, keyed
    by event id (independent review finding #1, wave 2, 2026-09-09: ``halt_reason`` is now read
    too, alongside ``outcome_digest``, so :func:`replay_engine` can tell a genuinely-halted
    receipt apart from an honest EGRESS_RESULT ``None`` — see :class:`ReplayVerdict`'s own
    ``uncompared_halt_reasons`` docstring)."""
    recorded: dict[str, _RecordedReceipt] = {}
    cur = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (_EVENT_CONSUMED_KIND,),
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json).get("payload", {})
        event_id = payload.get("event_id")
        if event_id is not None:
            recorded[event_id] = _RecordedReceipt(
                outcome_digest=payload.get("outcome_digest"),
                halt_reason=payload.get("halt_reason"),
            )
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

    recorded = _recorded_receipts(evidence_store)
    admitted = list(inbox.replay())
    if window_events is not None:
        admitted = admitted[-window_events:]

    core = build_core()
    diverged: list[str] = []
    compared = 0
    uncompared = 0
    uncompared_halt_reasons: list[tuple[str, str]] = []
    for _seq, event in admitted:
        event_id = event_identity(event, scheme=scheme)
        if event_id not in recorded:
            # Nothing to compare against (e.g. outside the replay window's own history, or a row
            # admitted but not yet consumed) — not a divergence, just not yet a baseline.
            continue
        receipt = recorded[event_id]
        expected_digest = receipt.outcome_digest
        if (
            expected_digest is None
            and receipt.halt_reason in _PRE_PIPELINE_HALT_REASONS
        ):
            # Independent review finding #1, wave 2 (2026-09-09): the LIVE run's own receipt is
            # itself a halt (e.g. a Coordinator-gate refusal — AUTHORITY_NOT_CURRENT /
            # LIVE_SCOPE_NOT_AUTHORIZED — or any other halt reached before the decision
            # pipeline ran; tos.engine.core.EventResult.outcome_digest is None whenever no
            # pipeline ran). The boot-time replay core's own CoordinatorPreconditions stand-in
            # (tos_runtime.compose._preconditions._ReplayPreconditions) is unconditionally
            # True/True — it cannot reproduce a HISTORICAL refusal — so re-deriving this event
            # here would run the pipeline for real and manufacture a digest with nothing honest
            # to compare it against (an asymmetric None-recorded/non-None-replayed pair the old
            # code treated as a divergence — a single gate refusal permanently bricked every
            # later boot). Never call core.handle for this event at all: the live run's own
            # HaltReason accounting ("nothing is consumed") means skipping it here reproduces
            # the live run's ledger state exactly, not merely avoids a false comparison.
            uncompared += 1
            uncompared_halt_reasons.append((event_id, receipt.halt_reason))
            continue
        # Always re-derive the event's outcome (this advances the SAME core's ledger state for
        # every subsequent event in the stream) even when the comparison below is skipped.
        result = core.handle(event)
        actual_digest = result.outcome_digest
        if expected_digest is None and actual_digest is None:
            # Independent review finding #1 (wave 1): neither side has an outcome identity to
            # compare (e.g. an EGRESS_RESULT event — tos.engine.core.EventResult.outcome_digest
            # is honestly None for every one of them, with no halt_reason at all). This is "no
            # outcome identity", not a divergence — see the module docstring and
            # ReplayVerdict.uncompared. Distinguished from the halt-reason case above: this one
            # carries no reason to report (uncompared_halt_reasons stays empty for it).
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
        total_compared=compared,
        diverged=tuple(diverged),
        uncompared=uncompared,
        uncompared_halt_reasons=tuple(uncompared_halt_reasons),
    )
