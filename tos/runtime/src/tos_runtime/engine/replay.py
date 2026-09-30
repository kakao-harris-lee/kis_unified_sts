"""Replay durable inbox events against a fresh core and compare recorded outcomes.

``EGRESS_RESULT`` comparisons use ``EventResult.outcome_digest``.
``DECISION_TICK`` comparisons use that digest plus a
:class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` covering
hand-off, halt, and attempt identity. A recorded pre-pipeline refusal with no
outcome digest is counted as uncompared only for the closed set of halt reasons
that prove the pipeline never ran; other missing or mismatched combinations
are divergences. Missing flow fingerprints remain disclosed as
``RECEIPT_FINGERPRINT_MISSING``.

The module reads but does not mutate the inbox or evidence store. The
``build_core`` factory owns its side effects; compose wiring supplies
side-effect-free replay stages. Windowed replay is sound only when excluded
events carry no reservation state, so replaying the full inbox is the safe
default.
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

    ``uncompared`` counts events for which NEITHER comparison this module performs could run at
    all — never a divergence (``ok`` does not consult it), never merely "not interesting". Three
    DISTINCT reasons put an event here, each named in ``uncompared_halt_reasons`` (re-review
    finding R2, 2026-09-09, replacing an earlier, now-stale claim that every such event was an
    honest ``EGRESS_RESULT`` — untrue since kernel lane KW3-RD, ``783fadf0``, gave every
    ``EGRESS_RESULT`` a real digest):

    1. **Pre-pipeline halt** — the recorded receipt's own ``halt_reason`` is in
       :data:`_PIPELINE_NEVER_RAN_HALT_REASONS`: the LIVE run's pipeline structurally never ran
       (a Coordinator-gate refusal or equivalent), so ``core.handle`` is never even called for
       this event during replay either.
    2. **Coordinator-gate refusal with no recorded reason** — the narrow ``None``/``None`` case
       :func:`_compare_one_event` still recognizes: both sides carry no outcome digest and no
       ``halt_reason``. Structurally never an ``EGRESS_RESULT`` (asserted directly in
       :func:`_compare_one_event`).
    3. **``"RECEIPT_FINGERPRINT_MISSING"``** (wave-3 finding #1(b), re-review finding R1,
       2026-09-09) — a pre-CR6 ``DECISION_TICK`` receipt recorded no
       :class:`~tos_runtime.engine.flow_fingerprint.FlowFingerprint` at all. Unlike the first two
       reasons, THIS one is reported ALONGSIDE the event still being counted in
       ``total_compared``: the digest half is always compared regardless of fingerprint
       availability (re-review finding R1 fixed an early-return that used to skip the digest
       comparison too, silently regressing coverage below what a pre-fingerprint boot already
       had). ``has_unverifiable_receipts`` is ``True`` whenever this reason appears.
    """

    total_compared: int
    diverged: tuple[str, ...]
    uncompared: int = 0
    #: ``(event_id, reason)`` pairs — see this class's own docstring for the three reasons a pair
    #: can name. A ``"RECEIPT_FINGERPRINT_MISSING"`` pair's event IS counted in
    #: ``total_compared`` (digest-only verified); the other two reasons' events are counted in
    #: ``uncompared`` instead (re-review finding R1/R2, 2026-09-09).
    uncompared_halt_reasons: tuple[tuple[str, str], ...] = ()
    #: Re-review finding R1 (2026-09-09): ``True`` iff at least one ``DECISION_TICK`` receipt in
    #: this replay run had no recorded flow fingerprint to compare (a pre-CR6 receipt) — the
    #: digest half was still verified for it, but its commitment-flow outcome (handed off? which
    #: step halted? which attempt?) could not be independently checked. Never a divergence by
    #: itself (a legacy receipt is not evidence of anything wrong) — a durable, visible fact a
    #: caller (the boot gate) records rather than silently discards.
    has_unverifiable_receipts: bool = False

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
    #: A ``CORPORATE_ACTION`` event's recorded :class:`~tos.nontrade.NonTradeDisposition` string
    #: (kernel round #3 §2 결정 3) — ``None`` for every other event kind.
    nontrade_disposition: str | None = None


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
                nontrade_disposition=payload.get("nontrade_disposition"),
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
    #: Re-review finding R1 (2026-09-09): set when this event WAS digest-compared (``uncompared``
    #: is ``False``) but its ``DECISION_TICK`` flow fingerprint could not be — a pre-CR6 receipt.
    #: Never set together with ``uncompared=True`` (that path returns before this could apply).
    fingerprint_uncompared: bool = False


def _check_fingerprint(
    event: EngineEvent, result: EventResult, receipt: _RecordedReceipt
) -> tuple[str | None, bool]:
    """The ``DECISION_TICK``-only flow-fingerprint half of the comparison (re-review finding R1,
    2026-09-09) — factored out of :func:`_compare_one_event` for size-budget discipline.

    Returns:
        ``(fingerprint_mismatch, fingerprint_uncompared)``.
    """
    if event.kind is not EventKind.DECISION_TICK:
        return None, False
    if receipt.flow_fingerprint is None:
        return None, True
    actual_fingerprint = flow_fingerprint_for(result)
    assert actual_fingerprint is not None  # DECISION_TICK guarantees this structurally
    return (
        first_mismatched_field(receipt.flow_fingerprint, actual_fingerprint),
        False,
    )


def _check_disposition_mismatch(
    event: EngineEvent, result: EventResult, receipt: _RecordedReceipt
) -> bool:
    """Kernel round #3 §2 결정 3: a ``CORPORATE_ACTION``'s recorded ``nontrade_disposition`` is
    compared alongside its outcome_digest, exactly the way a ``DECISION_TICK``'s flow_fingerprint
    is compared alongside ITS digest — a second, independent signal over the same event, not
    folded into the digest comparison itself (a digest collision across two different
    dispositions is not claimed impossible; this is defence in depth, mirroring the fingerprint's
    own role). Factored out of :func:`_compare_one_event` for size-budget discipline."""
    return bool(
        event.kind is EventKind.CORPORATE_ACTION
        and result.nontrade_outcome is not None
        and receipt.nontrade_disposition is not None
        and receipt.nontrade_disposition != result.nontrade_outcome.disposition.value
    )


def _record_divergence_halt(
    *,
    event_id: str,
    expected_digest: str | None,
    actual_digest: str | None,
    state: ReplayResultState,
    fingerprint_mismatch: str | None,
    receipt: _RecordedReceipt,
    result: EventResult,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Durably record one ``REPLAY_DIVERGED`` halt — factored out of :func:`_compare_one_event`
    for size-budget discipline."""
    record_halt(
        evidence_store,
        emergency_log,
        payload={
            "event_id": event_id,
            "expected_outcome_digest": expected_digest,
            "actual_outcome_digest": actual_digest,
            "replay_result_state": state.value,
            "fingerprint_mismatch_field": fingerprint_mismatch,
            "expected_nontrade_disposition": receipt.nontrade_disposition,
            "actual_nontrade_disposition": (
                None
                if result.nontrade_outcome is None
                else result.nontrade_outcome.disposition.value
            ),
        },
        kind=_REPLAY_DIVERGED_KIND,
        record_class=_REPLAY_DIVERGED_RECORD_CLASS,
    )


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
        # EGRESS_RESULT (module docstring's "comparison surface" section), and (kernel round #3
        # §2 결정 3) never a CORPORATE_ACTION either — the handler always sets
        # EventResult.nontrade_outcome, so outcome_digest is real for every CORPORATE_ACTION the
        # same way it has been for every EGRESS_RESULT since KW3-RD.
        assert event.kind not in (
            EventKind.EGRESS_RESULT,
            EventKind.CORPORATE_ACTION,
        ), (
            "an EGRESS_RESULT or CORPORATE_ACTION reached the None/None skip branch — "
            "outcome_digest must be real for both since kernel lane KW3-RD (783fadf0) / kernel "
            "round #3 §2 결정 1-3; this would silently reopen the exact comparison gap those "
            "changes closed"
        )
        return _EventOutcome(uncompared=True, diverged=False)

    # Re-review finding R1 (2026-09-09): a pre-CR6 receipt with no recorded fingerprint must
    # NEVER skip the digest comparison below — an early return here (the wave-3 shape) silently
    # regressed coverage to "compares nothing at all" for exactly the receipts that most need
    # verifying (every receipt written before this fix landed). The digest half is ALWAYS
    # compared; only the fingerprint half is reported separately as unverifiable.
    fingerprint_mismatch, fingerprint_uncompared = _check_fingerprint(
        event, result, receipt
    )
    disposition_mismatch = _check_disposition_mismatch(event, result, receipt)

    state = replay_result_for(
        expected_outcome_digest=expected_digest,
        actual_outcome_digest=actual_digest,
        baseline_supported=True,
        input_complete=True,
    )
    diverged = (
        state is not ReplayResultState.MATCH
        or fingerprint_mismatch is not None
        or disposition_mismatch
    )
    if diverged:
        _record_divergence_halt(
            event_id=event_id,
            expected_digest=expected_digest,
            actual_digest=actual_digest,
            state=state,
            fingerprint_mismatch=fingerprint_mismatch,
            receipt=receipt,
            result=result,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
        )
    return _EventOutcome(
        uncompared=False,
        diverged=diverged,
        fingerprint_uncompared=fingerprint_uncompared,
    )


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
    has_unverifiable_receipts = False
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
        if outcome.fingerprint_uncompared:
            # Re-review finding R1: the digest half above WAS compared (this event is already in
            # `compared`) — only the flow fingerprint half is unverifiable (a pre-CR6 receipt).
            has_unverifiable_receipts = True
            uncompared_halt_reasons.append((event_id, "RECEIPT_FINGERPRINT_MISSING"))
        if outcome.diverged:
            diverged.append(event_id)
    return ReplayVerdict(
        total_compared=compared,
        diverged=tuple(diverged),
        uncompared=uncompared,
        uncompared_halt_reasons=tuple(uncompared_halt_reasons),
        has_unverifiable_receipts=has_unverifiable_receipts,
    )
