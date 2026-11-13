"""Replay durable inbox events against a fresh core and compare recorded outcomes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

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
from tos_runtime.engine.replay_discards import EngineDiscards
from tos_runtime.engine.replay_releases import EngineReleases, RclCommitted
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["ReplayableCore", "ReplayVerdict", "replay_engine"]


class ReplayableCore(Protocol):
    """The exact surface :func:`replay_engine` uses on whatever its ``build_core`` factory"""

    def handle(self, event: EngineEvent) -> EventResult:
        """Handle one event and return its result — the sequencer's own per-event contract."""
        ...


_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_REPLAY_DIVERGED_KIND = "REPLAY_DIVERGED"
_REPLAY_DIVERGED_RECORD_CLASS = "REPLAY_DIVERGED"

_PIPELINE_NEVER_RAN_HALT_REASONS: frozenset[str] = frozenset(
    {
        HaltReason.AUTHORITY_NOT_CURRENT.value,
        HaltReason.LIVE_SCOPE_NOT_AUTHORIZED.value,
        HaltReason.EVENT_ORDER_REVERSED.value,
        HaltReason.REGISTRY_MISSING.value,
        HaltReason.REGISTRY_EXPLICIT_EMPTY.value,
        NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
    }
)


@dataclass(frozen=True)
class ReplayVerdict:
    """The outcome of one :func:`replay_engine` run."""

    total_compared: int
    diverged: tuple[str, ...]
    uncompared: int = 0
    uncompared_halt_reasons: tuple[tuple[str, str], ...] = ()
    has_unverifiable_receipts: bool = False

    @property
    def ok(self) -> bool:
        """Whether every compared event's replay state was ``MATCH``."""
        return len(self.diverged) == 0


@dataclass(frozen=True)
class _RecordedReceipt:
    """One durable ``EVENT_CONSUMED`` receipt's comparison-relevant fields."""

    outcome_digest: str | None
    halt_reason: str | None
    flow_fingerprint: FlowFingerprint | None


def _recorded_receipts(
    evidence_store: SqliteEvidenceStore,
) -> dict[str, _RecordedReceipt]:
    """Read every ``EVENT_CONSUMED`` receipt's recorded comparison-relevant fields, keyed by"""
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
    """One admitted event's contribution to a :class:`ReplayVerdict` — extracted so"""

    uncompared: bool
    diverged: bool
    uncompared_reason: str | None = None
    fingerprint_uncompared: bool = False


def _check_fingerprint(
    event: EngineEvent, result: EventResult, receipt: _RecordedReceipt
) -> tuple[str | None, bool]:
    """The ``DECISION_TICK``-only flow-fingerprint half of the comparison (re-review finding R1,"""
    if event.kind is not EventKind.DECISION_TICK:
        return None, False
    if receipt.flow_fingerprint is None:
        return None, True
    actual_fingerprint = flow_fingerprint_for(result)
    assert actual_fingerprint is not None
    return (
        first_mismatched_field(receipt.flow_fingerprint, actual_fingerprint),
        False,
    )


def _record_divergence_halt(
    *,
    event_id: str,
    expected_digest: str | None,
    actual_digest: str | None,
    state: ReplayResultState,
    fingerprint_mismatch: str | None,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> None:
    """Durably record one ``REPLAY_DIVERGED`` halt — factored out of :func:`_compare_one_event`"""
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


def _compare_one_event(
    event: EngineEvent,
    receipt: _RecordedReceipt,
    core: ReplayableCore,
    *,
    event_id: str,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> _EventOutcome:
    """Re-derive and compare ONE admitted event against its recorded receipt (module docstring's"""
    expected_digest = receipt.outcome_digest
    if (
        expected_digest is None
        and receipt.halt_reason in _PIPELINE_NEVER_RAN_HALT_REASONS
    ):
        return _EventOutcome(
            uncompared=True, diverged=False, uncompared_reason=receipt.halt_reason
        )

    result = core.handle(event)
    actual_digest = result.outcome_digest
    if expected_digest is None and actual_digest is None:
        assert event.kind is not EventKind.EGRESS_RESULT, (
            "an EGRESS_RESULT reached the None/None skip branch — outcome_digest must be real "
            "since kernel lane KW3-RD (783fadf0); this would silently reopen the exact "
            "comparison gap that change closed"
        )
        return _EventOutcome(uncompared=True, diverged=False)

    fingerprint_mismatch, fingerprint_uncompared = _check_fingerprint(
        event, result, receipt
    )

    state = replay_result_for(
        expected_outcome_digest=expected_digest,
        actual_outcome_digest=actual_digest,
        baseline_supported=True,
        input_complete=True,
    )
    diverged = state is not ReplayResultState.MATCH or fingerprint_mismatch is not None
    if diverged:
        _record_divergence_halt(
            event_id=event_id,
            expected_digest=expected_digest,
            actual_digest=actual_digest,
            state=state,
            fingerprint_mismatch=fingerprint_mismatch,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
        )
    return _EventOutcome(
        uncompared=False,
        diverged=diverged,
        fingerprint_uncompared=fingerprint_uncompared,
    )


def _load_releases(
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    rcl_committed: RclCommitted | None,
) -> EngineReleases:
    """The live engine's recorded projection releases, each corroboration failure or replay"""

    def _halt(payload: dict[str, Any]) -> None:
        record_halt(
            evidence_store,
            emergency_log,
            payload=payload,
            kind=_REPLAY_DIVERGED_KIND,
            record_class=_REPLAY_DIVERGED_RECORD_CLASS,
        )

    return EngineReleases.load(
        evidence_store, rcl_committed=rcl_committed, on_divergence=_halt
    )


def _load_discards(
    evidence_store: SqliteEvidenceStore, emergency_log: EmergencyAppendLog
) -> EngineDiscards:
    """The live engine's recorded never-sent discards, each replay refusal recorded as a"""

    def _halt(payload: dict[str, Any]) -> None:
        record_halt(
            evidence_store,
            emergency_log,
            payload=payload,
            kind=_REPLAY_DIVERGED_KIND,
            record_class=_REPLAY_DIVERGED_RECORD_CLASS,
        )

    return EngineDiscards.load(evidence_store, on_divergence=_halt)


def replay_engine(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    build_core: Callable[[], ReplayableCore],
    *,
    scheme: CanonicalizationScheme,
    window_events: int | None,
    rcl_committed: RclCommitted | None = None,
) -> ReplayVerdict:
    """Independently re-derive the inbox's admitted events and compare outcomes."""
    if window_events is not None and window_events <= 0:
        raise ValueError(
            f"replay_engine window_events must be a positive int or None (got {window_events!r}) "
            "— a zero/negative window is not a smaller replay, it is a silently-disabled one"
        )

    recorded = _recorded_receipts(evidence_store)
    releases = _load_releases(evidence_store, emergency_log, rcl_committed)
    discards = _load_discards(evidence_store, emergency_log)
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
            continue
        diverged.extend(releases.before(event, event_id, core))
        diverged.extend(discards.before(event_id, core))
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
            has_unverifiable_receipts = True
            uncompared_halt_reasons.append((event_id, "RECEIPT_FINGERPRINT_MISSING"))
        if outcome.diverged:
            diverged.append(event_id)
    diverged.extend(releases.before(None, None, core))
    diverged.extend(discards.before(None, core))
    return ReplayVerdict(
        total_compared=compared,
        diverged=tuple(diverged),
        uncompared=uncompared,
        uncompared_halt_reasons=tuple(uncompared_halt_reasons),
        has_unverifiable_receipts=has_unverifiable_receipts,
    )
