"""``replay_engine`` — independent re-derivation over a durable event inbox (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "재생 판정 replay digest 동일").

Rebuilds a FRESH core (via the injected ``build_core`` factory — never constructed here; typed
:class:`ReplayableCore`, not :class:`~tos.engine.EngineCore`, since the factory may hand back a
wrapper — see that Protocol's own docstring) and re-consumes the inbox's own admitted events, in
``seq`` order.

**The comparison surface, precisely (wave-3 review finding #1, 2026-09-09 — this paragraph
replaces an earlier, narrower claim; see findings #1 and #2 below for the full history).** Two
DIFFERENT things are compared, one per event kind:

- **``EGRESS_RESULT``**: ``EventResult.outcome_digest`` alone —
  :func:`~tos.engine.records.egress_result_outcome_digest` (kernel lane KW3-RD, ``783fadf0``),
  which since that commit is a REAL digest over the applied disposition/capacity/knowledge/
  quantities, never honestly ``None`` for an event that reached the pipeline (see finding #2).
- **``DECISION_TICK``**: ``EventResult.outcome_digest`` (the decision pipeline's own Proposal
  digest, fixed strictly BEFORE the 19-step commitment flow starts) TOGETHER WITH a
  :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` (finding #1(b), 2026-09-09) —
  ``handed_off``/``halt_step``/``halt_reason``/``attempt_id`` off the flow's own
  :class:`~tos.engine.sequencer.FlowResult`. The Proposal digest alone is STRUCTURALLY blind to
  everything the commitment flow does (see finding #1's own probes P5/P6): it cannot detect a
  flow that halted early, never handed off, or bound the wrong attempt, because none of that
  feeds the digest at all. The fingerprint is the SEPARATE, independent thing that does.

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

**Wave-3 review finding #2 (2026-09-09) — the paragraph above describes wave-1 history, not
today's invariant.** Kernel lane KW3-RD (``783fadf0``) gave ``EGRESS_RESULT`` events a real,
non-``None`` ``outcome_digest`` (:func:`~tos.engine.records.egress_result_outcome_digest`, over
the applied disposition/capacity/knowledge/quantities). The "honest ``None``/``None``" case this
paragraph describes is therefore, since that commit, reachable ONLY by a ``DECISION_TICK``
refused before the pipeline ever ran with NO recorded ``halt_reason`` at all — a shape that should
not occur in practice (every such refusal this runtime knows about DOES record a ``halt_reason``;
see wave-2 finding #1 and re-review finding R1 below) — never by an ``EGRESS_RESULT`` receipt.
:func:`replay_engine` asserts this narrowed invariant directly at the branch itself, rather than
leaving it as prose a future edit could silently invalidate by widening the skip.

**Wave-3 review finding #1(b) (2026-09-09) — the FLOW FINGERPRINT.** The digest comparison above,
even corrected for KW3-RD, answers only "does this event's own outcome identity match" — for a
``DECISION_TICK`` that identity is the Proposal digest, fixed BEFORE the commitment flow runs, so
it is STRUCTURALLY blind to everything steps 2-19 do. Measured directly (review probes P5/P6): an
inbox holding only a ``DECISION_TICK`` (no ``EGRESS_RESULT`` re-injected afterward) whose durable
``FLOW_STEP_ADMITTED`` rows (or ``SEND_HANDED_OFF``) are deleted still replays ``ok=True`` — a
flow that diverged from ``STAGE_UNKNOWN``-halted-at-step-2 (or ``TRANSMIT_UNAVAILABLE``) all the
way to "handed off" produces the IDENTICAL Proposal digest either way. :func:`replay_engine` now
ALSO compares a :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` for every
``DECISION_TICK`` — ``handed_off``/``halt_step``/``halt_reason``/``attempt_id``, the exact fields
:mod:`tos.tests.engine.test_sequencer_mutation_matrix`'s own ``_fingerprint`` already established
as load-bearing for this class of check. A mismatch is a divergence, naming the FIRST field that
differs (:func:`~tos_runtime.engine.flow_fingerprint.first_mismatched_field`) in the durably
recorded ``REPLAY_DIVERGED`` detail. A receipt with NO recorded fingerprint at all (a pre-this-fix
row) is never silently treated as a pass: it is counted in :attr:`ReplayVerdict.uncompared` with
reason ``"RECEIPT_FINGERPRINT_MISSING"`` — fail-closed disclosure that this tick's flow was never
actually verified, rather than a quiet, structurally-blind "ok".

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
``halt_reason`` is one of :data:`_PIPELINE_NEVER_RAN_HALT_REASONS` — the CLOSED set of halt reasons
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

**Re-review finding R1 (2026-09-09), corrected here — the wave-2 fix above re-opened itself.**
:data:`_PIPELINE_NEVER_RAN_HALT_REASONS` (renamed from ``_PRE_PIPELINE_HALT_REASONS`` — see that
constant's own docstring) held only the five kernel ``HaltReason`` members reachable before
``_handle_decision_tick`` runs the pipeline. It did NOT hold
:data:`~tos_runtime.engine.orthostate_projection.NEW_RISK_HALTED_BY_COUPLING_VIOLATION` — the
independent review finding #3 new-risk latch's own reason string, which :meth:`~tos_runtime.engine
.driver.EngineDriver._new_risk_halted_result` records on a refused ``DECISION_TICK`` WITHOUT ever
calling ``core.handle`` (``tos_runtime.engine.driver`` module, the latch-check branch) — exactly
the same "``outcome_digest`` is ``None`` because the pipeline never ran" shape the kernel reasons
already cover, just from a RUNTIME-level refusal instead of a kernel one. Before this fix, a
latched tick's receipt reached the normal comparison, replay ran the pipeline for it (the latch
is a runtime concept the replay core's own ``EngineCore`` has no knowledge of), and the resulting
``None``-recorded / non-``None``-replayed asymmetry reproduced finding #1's exact boot-brick —
reachable through finding #8's own cancel-crossing-fill correction, which is DESIGNED to trip
this latch on a scenario ADR-002-005 §7 calls routine. The fix is one addition to the closed set;
see that constant's own updated docstring for why the set's THEME changed from "kernel
``HaltReason`` members" to "reasons for which the pipeline provably never ran" (kernel- or
runtime-sourced, closed either way — never a wildcard).

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
from typing import Protocol

from tos.canonical import CanonicalizationScheme
from tos.engine import EngineEvent, EventKind, EventResult
from tos.engine.records import event_identity
from tos.engine.sink import replay_result_for
from tos.engine.vocabulary import HaltReason
from tos.evidence import ReplayResultState

from tos_runtime.engine.flow_fingerprint import (
    FlowFingerprint,
    first_mismatched_field,
    flow_fingerprint_for,
)
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import (
    NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
)
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["ReplayableCore", "ReplayVerdict", "replay_engine"]


class ReplayableCore(Protocol):
    """The exact surface :func:`replay_engine` uses on whatever its ``build_core`` factory
    returns — ``.handle(event) -> EventResult``, nothing else (verified directly against this
    module's own source: ``build_core()`` and ``core.handle(event)`` are the ONLY two calls made
    on it). Wave-3 review finding #5 (2026-09-09): declaring this Protocol, rather than typing
    the parameter as the concrete :class:`~tos.engine.EngineCore`, lets a wrapper like
    :class:`~tos_runtime.engine.replay_stage.EventCorrelatingCore` satisfy the type checker
    STRUCTURALLY — no ``cast`` needed at the boundary, and the type hint states precisely what
    this module actually depends on, so mypy would catch a future call to any OTHER
    ``EngineCore`` method here as the widening it would be.
    """

    def handle(self, event: EngineEvent) -> EventResult:
        """Handle one event and return its result — the sequencer's own per-event contract."""
        ...


_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"
_REPLAY_DIVERGED_RECORD_CLASS = "REPLAY_DIVERGED"

#: Halt reasons for which ``EventResult.pipeline`` is STRUCTURALLY ``None`` in EVERY run — never
#: merely an artifact of what happened to occur this particular time — so ``outcome_digest`` is
#: unconditionally ``None`` too. This is the ONLY set of halt reasons :func:`replay_engine` treats
#: as "the pipeline never ran" (independent review finding #1, wave 2, 2026-09-09; widened by
#: re-review finding R1, same date — see the module docstring's own R1 paragraph).
#:
#: **Re-review finding R1 renamed this set (was ``_PRE_PIPELINE_HALT_REASONS``).** The old name
#: and its docstring described only "``HaltReason`` members reached before the kernel's decision
#: pipeline runs" — true for the first five entries, but the set is no longer kernel-only: the
#: sixth entry, :data:`~tos_runtime.engine.orthostate_projection
#: .NEW_RISK_HALTED_BY_COUPLING_VIOLATION`, is a RUNTIME-level halt reason
#: (:mod:`tos_runtime.engine.driver`'s new-risk latch check, independent review finding #3) that
#: is not a ``tos.engine.vocabulary.HaltReason`` member at all. What every member of this set
#: actually shares — the ONLY property that licenses membership — is that ``core.handle`` (or,
#: for the latch, the runtime's own would-be call to it) is PROVABLY never invoked for the event,
#: kernel-sourced or runtime-sourced. This must stay a closed, explicitly-enumerated set, never a
#: wildcard or a "any halt_reason" catch-all: several OTHER halt reasons (e.g.
#: ``TRANSMIT_UNAVAILABLE``, ``STAGE_DENIED``, ``NO_ACTION_OUTCOME`` when reached WITH a proposal
#: already produced, ...) are reached from inside ``_run_entries`` AFTER a real proposal already
#: gave ``EventResult.pipeline`` a real, non-``None`` ``outcome_digest`` — a receipt carrying one
#: of THOSE halt reasons must still go through the normal digest comparison; treating ANY
#: ``halt_reason`` as "uncompared" would silently swallow a genuine divergence for one of those
#: (measured directly against this module's own test suite:
#: ``test_mutated_recorded_outcome_digest_is_detected_as_a_divergence`` halts at
#: ``TRANSMIT_UNAVAILABLE`` with a REAL recorded digest and must still be compared and caught as a
#: divergence when that digest is tampered with).
_PIPELINE_NEVER_RAN_HALT_REASONS: frozenset[str] = frozenset(
    {
        HaltReason.AUTHORITY_NOT_CURRENT.value,
        HaltReason.LIVE_SCOPE_NOT_AUTHORIZED.value,
        HaltReason.EVENT_ORDER_REVERSED.value,
        HaltReason.REGISTRY_MISSING.value,
        HaltReason.REGISTRY_EXPLICIT_EMPTY.value,
        # Re-review finding R1 (2026-09-09): a RUNTIME-level halt reason, not a kernel
        # HaltReason member — see this constant's own docstring for why it belongs here anyway.
        NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
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
    """One durable ``EVENT_CONSUMED`` receipt's comparison-relevant fields.

    ``flow_fingerprint`` (wave-3 review finding #1(b), 2026-09-09) is ``None`` for an
    ``EGRESS_RESULT`` receipt (not applicable — see :mod:`tos_runtime.engine.flow_fingerprint`'s
    own docstring) AND for a pre-this-fix ``DECISION_TICK`` receipt that never recorded one —
    :func:`replay_engine` tells the two apart by the ADMITTED EVENT's own kind, never by this
    field alone.
    """

    outcome_digest: str | None
    halt_reason: str | None
    flow_fingerprint: FlowFingerprint | None


def _recorded_receipts(
    evidence_store: SqliteEvidenceStore,
) -> dict[str, _RecordedReceipt]:
    """Read every ``EVENT_CONSUMED`` receipt's recorded comparison-relevant fields, keyed by
    event id (independent review finding #1, wave 2, 2026-09-09: ``halt_reason`` is read
    alongside ``outcome_digest``, so :func:`replay_engine` can tell a genuinely-halted receipt
    apart from the narrow None/None case wave-3 finding #2 describes; wave-3 finding #1(b) adds
    ``flow_fingerprint``)."""
    recorded: dict[str, _RecordedReceipt] = {}
    cur = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (_EVENT_CONSUMED_KIND,),
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json).get("payload", {})
        event_id = payload.get("event_id")
        if event_id is not None:
            fingerprint_payload = payload.get("flow_fingerprint")
            recorded[event_id] = _RecordedReceipt(
                outcome_digest=payload.get("outcome_digest"),
                halt_reason=payload.get("halt_reason"),
                flow_fingerprint=(
                    None
                    if fingerprint_payload is None
                    else FlowFingerprint.model_validate(fingerprint_payload)
                ),
            )
    return recorded


@dataclass(frozen=True)
class _EventOutcome:
    """One admitted event's contribution to a :class:`ReplayVerdict` — extracted so
    :func:`replay_engine`'s own loop stays a thin counter-update, not the comparison logic
    itself (tos size budget's own "extract" discipline)."""

    uncompared: bool
    diverged: bool
    uncompared_reason: str | None = None


def _compare_one_event(
    event: EngineEvent,
    receipt: _RecordedReceipt,
    core: ReplayableCore,
    *,
    event_id: str,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> _EventOutcome:
    """Re-derive and compare ONE admitted event against its recorded receipt (module docstring's
    own "comparison surface, precisely" section covers what is compared and why); durably records
    a ``REPLAY_DIVERGED`` halt itself on a divergence, mirroring :func:`replay_engine`'s own
    former inline behavior exactly."""
    expected_digest = receipt.outcome_digest
    if (
        expected_digest is None
        and receipt.halt_reason in _PIPELINE_NEVER_RAN_HALT_REASONS
    ):
        # Wave-2 finding #1 / re-review R1 (see module docstring): the LIVE run's own receipt is
        # itself a halt reached before the pipeline ever ran (kernel- or runtime-sourced, closed
        # set). Never call core.handle for this event: the live run's own HaltReason accounting
        # already establishes "nothing is consumed" — skipping reproduces that ledger state
        # exactly, rather than manufacturing a digest with nothing honest to compare it against.
        return _EventOutcome(
            uncompared=True, diverged=False, uncompared_reason=receipt.halt_reason
        )

    # Always re-derive the event's outcome (advances the SAME core's ledger state for every
    # subsequent event in the stream) even when the comparison below is skipped.
    result = core.handle(event)
    actual_digest = result.outcome_digest
    if expected_digest is None and actual_digest is None:
        # Wave-3 review finding #2: since kernel lane KW3-RD, reachable ONLY by a Coordinator-
        # gate refusal (or equivalent) with no recorded halt_reason at all — never an
        # EGRESS_RESULT (module docstring's "comparison surface" section).
        assert event.kind is not EventKind.EGRESS_RESULT, (
            "an EGRESS_RESULT reached the None/None skip branch — outcome_digest must be real "
            "for every EGRESS_RESULT since kernel lane KW3-RD (783fadf0); this would silently "
            "reopen the exact comparison gap that commit closed"
        )
        return _EventOutcome(uncompared=True, diverged=False)

    fingerprint_mismatch: str | None = None
    if event.kind is EventKind.DECISION_TICK:
        if receipt.flow_fingerprint is None:
            # Wave-3 finding #1(b): a pre-this-fix receipt never recorded a fingerprint — never
            # silently treat that as "ok" (fail-closed disclosure).
            return _EventOutcome(
                uncompared=True,
                diverged=False,
                uncompared_reason="RECEIPT_FINGERPRINT_MISSING",
            )
        actual_fingerprint = flow_fingerprint_for(result)
        assert (
            actual_fingerprint is not None
        )  # DECISION_TICK guarantees this structurally
        fingerprint_mismatch = first_mismatched_field(
            receipt.flow_fingerprint, actual_fingerprint
        )

    state = replay_result_for(
        expected_outcome_digest=expected_digest,
        actual_outcome_digest=actual_digest,
        baseline_supported=True,
        input_complete=True,
    )
    diverged = state is not ReplayResultState.MATCH or fingerprint_mismatch is not None
    if diverged:
        record_halt(
            evidence_store,
            emergency_log,
            payload={
                "event_id": event_id,
                "expected_outcome_digest": expected_digest,
                "actual_outcome_digest": actual_digest,
                "replay_result_state": state.value,
                "fingerprint_mismatch_field": fingerprint_mismatch,
            },
            kind=_REPLAY_DIVERGED_KIND,
            record_class=_REPLAY_DIVERGED_RECORD_CLASS,
        )
    return _EventOutcome(uncompared=False, diverged=diverged)


def replay_engine(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    build_core: Callable[[], ReplayableCore],
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
        build_core: A zero-argument factory returning a FRESH :class:`ReplayableCore` (typically
            an :class:`~tos.engine.EngineCore`, or a wrapper like
            :class:`~tos_runtime.engine.replay_stage.EventCorrelatingCore`) — never constructed
            here (see module docstring for what "fresh" does and does not guarantee about side
            effects).
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
        outcome = _compare_one_event(
            event,
            recorded[event_id],
            core,
            event_id=event_id,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
        )
        if outcome.uncompared:
            uncompared += 1
            if outcome.uncompared_reason is not None:
                uncompared_halt_reasons.append((event_id, outcome.uncompared_reason))
            continue
        compared += 1
        if outcome.diverged:
            diverged.append(event_id)
    return ReplayVerdict(
        total_compared=compared,
        diverged=tuple(diverged),
        uncompared=uncompared,
        uncompared_halt_reasons=tuple(uncompared_halt_reasons),
    )
