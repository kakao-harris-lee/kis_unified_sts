"""tos_runtime.riskstate.flow_observation — inbox/RCL-log/evidence-derived Action Flow"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple

from tos.afg.records import ActionCause, ObservedAmplification
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityComponent, CapacityVector, CommandType

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.policies import DeploymentFlowFacts

__all__ = [
    "FlowObservation",
    "InboxFlowReader",
    "REPLAYS_DEFINITION",
    "committed_flow_vectors",
    "count_duplicate_dispositions",
    "count_recovery_markers",
    "to_observed_amplification",
    "to_action_cause",
]

_SEND_SEALED_KIND = "SEND_SEALED"
_HANDLING_STARTED_KIND = "EVENT_HANDLING_STARTED"
_RECOVERY_MARKER_KINDS = (
    "DECISION_TICK_DROPPED_ON_RECOVERY",
    "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
)

REPLAYS_DEFINITION = (
    "recovery-marker-episodes:DECISION_TICK_DROPPED_ON_RECOVERY+"
    "HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND"
)


@dataclass(frozen=True)
class FlowObservation:
    """One root cause's observed action-flow facts (plan §2.3/§4.1). Every ``int``/``bool``"""

    queue_depth: int | None
    in_flight: int | None
    attempts_for_cause: int | None
    duplicates_rejected: int | None
    replays: int | None
    root_event_seq: int | None
    handling_started_monotonic: int | None
    lineage_found: bool | None
    sources: tuple[str, ...]
    replays_definition: str | None = None


class _HandlingStartedFacts(NamedTuple):
    """The two facts :meth:`InboxFlowReader._resolve_handling_started` reads off the root"""

    appended_at_monotonic_ns: int
    content_event_id: str | None


def _decode_content_event_id(payload_json: str) -> str | None:
    """The root row's own content-addressed ``event_id``, decoded out of an"""
    decoded = json.loads(payload_json)
    payload = decoded.get("payload", decoded)
    if not isinstance(payload, dict):
        return None
    event_id = payload.get("event_id")
    return event_id if isinstance(event_id, str) else None


def _started_monotonic(facts: _HandlingStartedFacts | None) -> int | None:
    """The ``appended_at_monotonic_ns`` projection of a resolved marker, or ``None`` for a"""
    return None if facts is None else facts.appended_at_monotonic_ns


def _read_kind_payloads(
    store: SqliteEvidenceStore, kind: str
) -> list[dict[str, object]]:
    """The shared by-kind raw-SQL idiom (mirrors"""
    try:
        cursor = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        )
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"InboxFlowReader: evidence store query failed for kind={kind!r}: {exc}"
        ) from exc
    payloads: list[dict[str, object]] = []
    for (payload_json,) in rows:
        decoded = json.loads(payload_json)
        payload = decoded.get("payload", decoded)
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _sealed_reference(seal: Mapping[str, object]) -> tuple[str | None, tuple[str, ...]]:
    """Extract ``(event_id, causal_predecessor_ids)`` from a ``send_seal.reference``"""
    reference = seal.get("reference")
    if not isinstance(reference, Mapping):
        return None, ()
    event_id = reference.get("event_id")
    predecessors_raw = reference.get("causal_predecessor_ids")
    predecessors = (
        tuple(p for p in predecessors_raw if isinstance(p, str))
        if isinstance(predecessors_raw, (list, tuple))
        else ()
    )
    return (event_id if isinstance(event_id, str) else None), predecessors


def _traces_to(
    root_event_id: str, event_id: str | None, predecessors: tuple[str, ...]
) -> bool:
    return event_id == root_event_id or root_event_id in predecessors


def count_duplicate_dispositions(
    unmatched_payloads: list[dict[str, object]], *, cause_attempts: set[str]
) -> int:
    'The kernel result-signature dedup count (module docstring\'s own "Two dedup layers"'
    count = 0
    for payload in unmatched_payloads:
        if payload.get("result_disposition") != "DUPLICATE":
            continue
        attempt_id = payload.get("attempt_id")
        if isinstance(attempt_id, str) and attempt_id in cause_attempts:
            count += 1
    return count


def count_recovery_markers(
    marker_payloads: list[dict[str, object]], *, root_event_ids: frozenset[str]
) -> int:
    """The restart-recovery episode count (module docstring's own "replays" section) — rows of"""
    count = 0
    for payload in marker_payloads:
        event_id = payload.get("event_id")
        if isinstance(event_id, str) and event_id in root_event_ids:
            count += 1
    return count


class InboxFlowReader:
    """Folds the durable inbox/evidence store into one :class:`FlowObservation` for a single"""

    def __init__(
        self,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        rcl_log: SqliteCommitLog,
        *,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Bind this reader to its three ports (plan §4.1's fixed interface) plus an OPTIONAL,"""
        self._inbox = inbox
        self._evidence_store = evidence_store
        self._rcl_log = rcl_log
        self._scheme = scheme

    def _resolve_root_event_seq(self, root_event_id: str) -> int | None:
        if self._scheme is None:
            return None
        from tos.engine.records import event_identity

        for seq, event in self._inbox.replay():
            if event_identity(event, scheme=self._scheme) == root_event_id:
                return seq
        return None

    def _resolve_handling_started(
        self, root_event_seq: int | None
    ) -> _HandlingStartedFacts | None:
        """Both facts this reader reads off ``root_event_seq``'s own ``EVENT_HANDLING_STARTED``"""
        if root_event_seq is None:
            return None
        receipt = self._inbox.handling_started_receipt(root_event_seq)
        if receipt is None:
            return None
        evidence_seq, generation = receipt
        entry = self._evidence_store.entry(evidence_seq)
        if entry is None:
            return None
        if entry.meta.kind != _HANDLING_STARTED_KIND:
            return None
        if entry.meta.key_generation != generation:
            return None
        return _HandlingStartedFacts(
            appended_at_monotonic_ns=entry.meta.appended_at_monotonic_ns,
            content_event_id=_decode_content_event_id(entry.payload_json),
        )

    def _count_amplification_axes(
        self,
        *,
        unmatched_payloads: list[dict[str, object]],
        cause_attempts: set[str],
        handling_started: _HandlingStartedFacts | None,
    ) -> tuple[int, int, tuple[str, ...]]:
        """The dedup/replay axis counts — split out of :meth:`observe` purely for that"""
        duplicates_rejected = count_duplicate_dispositions(
            unmatched_payloads, cause_attempts=cause_attempts
        )
        root_content_event_id = (
            handling_started.content_event_id if handling_started is not None else None
        )
        root_event_ids = (
            frozenset({root_content_event_id})
            if root_content_event_id is not None
            else frozenset()
        )
        recovery_payloads: list[dict[str, object]] = []
        extra_sources: list[str] = []
        for kind in _RECOVERY_MARKER_KINDS:
            payloads = _read_kind_payloads(self._evidence_store, kind)
            if payloads:
                extra_sources.append(f"evidence:{kind}")
            recovery_payloads.extend(payloads)
        replays = count_recovery_markers(
            recovery_payloads, root_event_ids=root_event_ids
        )
        return duplicates_rejected, replays, tuple(extra_sources)

    def _scan_sealed_lineage(
        self,
        sealed_payloads: list[dict[str, object]],
        *,
        root_event_id: str,
        attempt_id: str,
        terminal_attempts: set[str],
        resolved_root_event_seq: int | None,
    ) -> tuple[set[str], int, bool | None]:
        """The sealed-payload lineage scan + the pre-seal fallback — split out of"""
        cause_attempts: set[str] = set()
        in_flight_count = 0
        this_attempt_sealed = False
        this_attempt_lineage_found: bool | None = None
        for payload in sealed_payloads:
            aid = payload.get("attempt_id")
            seal = payload.get("send_seal")
            if not isinstance(aid, str) or not isinstance(seal, Mapping):
                continue
            event_id, predecessors = _sealed_reference(seal)
            traces = _traces_to(root_event_id, event_id, predecessors)
            if aid == attempt_id:
                this_attempt_sealed = True
                this_attempt_lineage_found = traces
            if traces:
                cause_attempts.add(aid)
                if aid not in terminal_attempts:
                    in_flight_count += 1
        if not this_attempt_sealed and resolved_root_event_seq is not None:
            this_attempt_lineage_found = True
        return cause_attempts, in_flight_count, this_attempt_lineage_found

    def observe(
        self,
        *,
        root_event_id: str,
        attempt_id: str,
        root_event_seq: int | None = None,
    ) -> FlowObservation:
        """Assemble one :class:`FlowObservation` for ``root_event_id``/``attempt_id`` (module"""
        sealed_payloads = _read_kind_payloads(self._evidence_store, _SEND_SEALED_KIND)
        consumed_payloads = _read_kind_payloads(
            self._evidence_store, "EGRESS_RESULT_CONSUMED"
        )
        unmatched_payloads = _read_kind_payloads(
            self._evidence_store, "RESULT_UNMATCHED"
        )
        terminal_attempts: set[str] = set()
        for payload in consumed_payloads + unmatched_payloads:
            aid = payload.get("attempt_id")
            if isinstance(aid, str):
                terminal_attempts.add(aid)

        sources: list[str] = []

        resolved_root_event_seq: int | None
        if root_event_seq is not None:
            resolved_root_event_seq = root_event_seq
            sources.append("inbox:current_seq")
        else:
            resolved_root_event_seq = self._resolve_root_event_seq(root_event_id)
            if self._scheme is not None:
                sources.append("inbox:event_identity")

        cause_attempts, in_flight_count, this_attempt_lineage_found = (
            self._scan_sealed_lineage(
                sealed_payloads,
                root_event_id=root_event_id,
                attempt_id=attempt_id,
                terminal_attempts=terminal_attempts,
                resolved_root_event_seq=resolved_root_event_seq,
            )
        )

        if sealed_payloads:
            sources.append(f"evidence:{_SEND_SEALED_KIND}")
        if consumed_payloads:
            sources.append("evidence:EGRESS_RESULT_CONSUMED")
        if unmatched_payloads:
            sources.append("evidence:RESULT_UNMATCHED")
        sources.append("inbox:unconsumed_count")

        handling_started = self._resolve_handling_started(resolved_root_event_seq)
        handling_started_monotonic = _started_monotonic(handling_started)
        if handling_started_monotonic is not None:
            sources.append(f"evidence:{_HANDLING_STARTED_KIND}")

        duplicates_rejected, replays, amplification_sources = (
            self._count_amplification_axes(
                unmatched_payloads=unmatched_payloads,
                cause_attempts=cause_attempts,
                handling_started=handling_started,
            )
        )
        sources.extend(amplification_sources)

        return FlowObservation(
            queue_depth=self._inbox.unconsumed_count,
            in_flight=in_flight_count,
            attempts_for_cause=len(cause_attempts),
            duplicates_rejected=duplicates_rejected,
            replays=replays,
            root_event_seq=resolved_root_event_seq,
            handling_started_monotonic=handling_started_monotonic,
            lineage_found=this_attempt_lineage_found,
            sources=tuple(sources),
            replays_definition=REPLAYS_DEFINITION,
        )


def committed_flow_vectors(
    rcl_log: SqliteCommitLog, *, flow_dimension_id: str
) -> tuple[CapacityVector, ...]:
    """The RCL log's own committed Action Flow Permit vectors on ``flow_dimension_id`` (module"""
    vectors: list[CapacityVector] = []
    for entry in rcl_log.replay():
        if entry.kind is CommandType.ISSUE_ACTION_FLOW_PERMIT:
            vectors.append(
                CapacityVector(
                    components=(
                        CapacityComponent(
                            dimension_id=flow_dimension_id, magnitude=None
                        ),
                    )
                )
            )
    return tuple(vectors)


def to_observed_amplification(
    obs: FlowObservation,
    facts: DeploymentFlowFacts,
    *,
    elapsed_monotonic: Decimal | None,
    fan_out: int | None = None,
    depth: int | None = None,
) -> ObservedAmplification:
    """Pure transform: :class:`FlowObservation` (+ the governed :class:`DeploymentFlowFacts`"""
    attempts = obs.attempts_for_cause
    return ObservedAmplification(
        fan_out=fan_out,
        depth=depth,
        attempts=attempts,
        mutations=attempts,
        queries=0,
        queue_depth=obs.queue_depth,
        in_flight=obs.in_flight,
        elapsed_monotonic=elapsed_monotonic,
        duplicate_redelivery_expansion=obs.duplicates_rejected,
        failover_reconnect_replay_expansion=obs.replays,
        amplification_per_cause=(None if attempts is None else Decimal(attempts)),
        duplicate_event_created_new_allowance=facts.duplicate_event_created_new_allowance,
        envelope_reset_on_duplicate=facts.envelope_reset_on_duplicate,
        concurrent_consumers_share_one_envelope=facts.concurrent_consumers_share_one_envelope,
    )


def to_action_cause(
    obs: FlowObservation,
    *,
    root_event_id: str,
    proposal_id: str,
    command_identity: str | None,
    command_digest: str | None,
    max_attempts: int | None,
) -> ActionCause:
    """Pure transform: :class:`FlowObservation` -> :class:`~tos.afg.ActionCause` (plan"""
    return ActionCause(
        root_cause_identity=root_event_id,
        parent_lineage=(proposal_id,),
        lineage_attested=obs.lineage_found is True,
        cyclic=root_event_id in (proposal_id,),
        forked_beyond_bound=(
            None
            if max_attempts is None or obs.attempts_for_cause is None
            else obs.attempts_for_cause > max_attempts
        ),
        inconsistent=(None if obs.lineage_found is None else not obs.lineage_found),
        command_identity=command_identity,
        command_digest=command_digest,
    )
