"""tos_runtime.riskstate.flow_observation — inbox/RCL-log/evidence-derived Action Flow
observations (TOS risk state service wave, plan §2.3/§4.1; DR-0003 §2.3 "Action-flow facts:
observed versus declared").

**Lineage bridge (measured, cited, not invented).** ``tos.egressgw.seal.SendSeal.reference``
is a ``tos.ordering.OrderingEvent`` (``tos/src/tos/egressgw/seal.py:219`` — "the causal-ordering
event itself — sealed like every other transport argument"), and ``OrderingEvent`` carries both
``event_id`` and ``causal_predecessor_ids`` (``tos/src/tos/ordering/_ordering.py:59-68``). Every
durable ``SEND_SEALED`` evidence row therefore already carries, per ``attempt_id``, the exact
causal-ordering coordinates this module needs for lineage: this is the ``event -> proposal ->
attempt`` chain DR-0003 §2.3 names as an observation, read from the SAME evidence rows
:mod:`tos_runtime.riskstate.position` reads for position, never a second invented mechanism.

**Two fields this fixed 3-argument reader (``InboxFlowReader(inbox, evidence_store, rcl_log)``,
plan §4.1) cannot honestly source, and why (deviation, reported).**

* ``duplicates_rejected`` — ``SqliteEventInbox.enqueue`` returns a typed
  ``InboxReceipt.duplicate`` flag (``tos_runtime/engine/inbox.py:227-236``), but that flag is a
  TRANSIENT return value at the moment of ONE enqueue call — it is never durably counted or
  otherwise recorded anywhere this reader's three injected ports can see (measured: no
  ``DUPLICATE``/dedup-count evidence kind exists in this runtime, confirmed by grep across
  ``tos_runtime/engine/*.py`` and ``tos_runtime/compose/_engine_wiring.py``). Left ``None``
  (never a fabricated ``0``).
* ``replays`` — the only durable replay-verdict evidence kinds this runtime has
  (``REPLAY_VERDICT_IDENTICAL``/``REPLAY_DIVERGED``, cited by
  ``tos_runtime/recovery/inputs.py:85-86``) are ONE-PER-BOOT verdicts over the WHOLE log, not a
  per-root-cause replay count — scoping a whole-log verdict to one ``root_event_id`` would be a
  fabrication, not an observation. Left ``None``.

**``root_event_seq``/``handling_started_monotonic`` need a canonicalization scheme this fixed
constructor does not carry (deviation, reported).** ``SqliteEventInbox`` computes and stores
each row's own content-addressed ``event_id`` at ``enqueue`` time (``event_identity(event,
scheme=...)``, ``inbox.py:348``) but exposes NO public "read seq by event_id" method — the only
way to resolve a caller-supplied ``root_event_id`` string back to an inbox ``seq`` is to
recompute ``event_identity`` per replayed row and compare, which needs the SAME
canonicalization scheme the inbox itself was constructed with. The plan §4.1 interface fixes
this reader's constructor to exactly ``(inbox, evidence_store, rcl_log)`` — no scheme. This
module therefore accepts an OPTIONAL, additive ``scheme`` keyword (widening a Protocol-shaped
constructor is still a satisfying implementation of it, the
``tos_runtime.rcl.log.SqliteCommitLog.append_cas`` "a wider signature is still a satisfying
implementation of the narrower Protocol" convention): when a scheme is supplied,
``root_event_seq`` is resolved by replaying the inbox and recomputing each event's identity;
``handling_started_monotonic`` is then read from :meth:`~tos_runtime.evidence.store
.SqliteEvidenceStore.iter_entry_meta`'s own ``appended_at_monotonic_ns`` column for that seq's
``EVENT_HANDLING_STARTED`` evidence receipt. Without a scheme, both fields are ``None`` (never
guessed).

**Superseded in production by a second, additive widening (team-lead disposition
2026-09-16): :meth:`InboxFlowReader.observe` now also accepts an optional
``root_event_seq``.** The identity-recomputation match above only succeeds when a caller's
``root_event_id`` string happens to equal the inbox's own content-addressed identity for that
row — this runtime's engine driver (``tos_runtime/engine/driver.py``) never guarantees that
(``StageRequest.reference.event_id`` is a caller-authored label threaded through from the
DECISION_TICK payload, not that digest). The engine handles exactly ONE inbox row at a time
(``EngineDriver._process_next``'s own ``_draining``/re-entrancy guard), so the CURRENTLY
handled row's ``seq`` is a genuine structural fact a caller can read directly off
``SqliteEventInbox.next_unconsumed()`` (still not-yet-consumed at that point in the flow —
``mark_consumed`` runs only after ``core.handle`` returns) and pass straight through, skipping
the identity-recomputation match entirely. :mod:`tos_runtime.compose._riskstate_wiring` wires
exactly this for :class:`~tos_runtime.riskstate.service.RiskStateService`.

**``committed_flow_vectors`` — measured, and empirically ``()`` under the current e2e wiring
(deviation, reported prominently).** DR-0003 §2.3 names "the committed flow vectors (unconsumed
permits in the commit log)" as an observation. Two facts, both measured directly against
``tos_runtime/rcl/log.py``:

1. ``SqliteCommitLog.replay()`` selects only ``seq, writer_epoch, command_id, command_digest,
   kind, payload_digest`` (``log.py:578-581``) — ``CommitEntry`` itself
   (``tos/src/tos/rcl/commitlog.py:195-200``) has no payload field at all, only
   ``payload_digest``. There is therefore NO public read surface anywhere on
   ``SqliteCommitLog`` that returns a committed entry's actual ``payload_json`` (unlike
   ``SqliteEvidenceStore``, which exposes ``.connection`` for exactly this reason — ``log.py``
   has no such property).
2. ``ledger_stages.AtomicCommitStage`` (the step-9 stage the real e2e uses) commits the
   reservation + permit binding as ONE entry whose ``kind`` is ``CommandType
   .COMMIT_RESERVATION`` (``risk/flow.py``'s own module docstring, "``ledger_stages
   .AtomicCommitStage``'s combined commit uses ``CommandType.COMMIT_RESERVATION`` instead"),
   never ``CommandType.ISSUE_ACTION_FLOW_PERMIT`` — that dedicated kind is written ONLY by
   :meth:`~tos_runtime.risk.flow.ActionFlowGovernor.issue_permit`'s STANDALONE path
   (``risk/flow.py:429-487``, "NOT used by the combined step-9 atomic commit"), which the real
   e2e does not call.

So even setting aside fact 1, fact 2 means the production commit path never writes an
``ISSUE_ACTION_FLOW_PERMIT``-kind entry at all — :func:`committed_flow_vectors` genuinely
returns ``()`` under the current e2e wiring, always. This function is still implemented against
the STANDALONE path's kind (for a caller — e.g. a future test, or a future e2e that DOES call
``issue_permit`` — that produces one): each matching entry contributes one
:class:`~tos.rcl.CapacityVector` with an UNKNOWN (``magnitude=None``) component on
``flow_dimension_id`` — never a fabricated magnitude (rcl's own ``CapacityComponent`` docstring:
"``None`` for an UNKNOWN/unbounded dimension ... UNKNOWN consumes capacity" — so a proven-to-
exist-but-unreadable committed permit is conservative, not silently absent). This is reported to
the operator/team-lead as a real gap requiring either a new ``SqliteCommitLog`` public reader or
a durable, out-of-band permit-vector evidence write from the atomic commit path — kernel round
#4 / a future lane, not this one (plan §6 item 4 already lists a sibling kernel-round candidate
here: "RCL 예약 행에 committed 벡터 영속").

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.engine.inbox`` +
``tos_runtime.evidence.store`` + ``tos_runtime.rcl.log`` only.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

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
    "committed_flow_vectors",
    "to_observed_amplification",
    "to_action_cause",
]

_SEND_SEALED_KIND = "SEND_SEALED"
_HANDLING_STARTED_KIND = "EVENT_HANDLING_STARTED"


@dataclass(frozen=True)
class FlowObservation:
    """One root cause's observed action-flow facts (plan §2.3/§4.1). Every ``int``/``bool``
    field is ``None`` when this reader's injected ports carry no real source for it — see the
    module docstring's own "deviation, reported" sections for exactly which fields that is and
    why. ``queries`` is deliberately NOT a field here — it is a structural constant computed by
    :func:`to_observed_amplification` directly (module docstring; plan §4.1's own exception).
    """

    queue_depth: int | None
    in_flight: int | None
    attempts_for_cause: int | None
    duplicates_rejected: int | None
    replays: int | None
    root_event_seq: int | None
    handling_started_monotonic: int | None
    lineage_found: bool | None
    sources: tuple[str, ...]


def _read_kind_payloads(
    store: SqliteEvidenceStore, kind: str
) -> list[dict[str, object]]:
    """The shared by-kind raw-SQL idiom (mirrors
    :mod:`tos_runtime.riskstate.position`'s own identically-named helper — kept local rather
    than imported across a sibling module boundary within this same package, matching this
    package's own convention of not sharing private helpers between its modules)."""
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
    """Extract ``(event_id, causal_predecessor_ids)`` from a ``send_seal.reference``
    (``OrderingEvent``) sub-mapping — module docstring's lineage bridge."""
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


class InboxFlowReader:
    """Folds the durable inbox/evidence store into one :class:`FlowObservation` for a single
    root cause (module docstring)."""

    def __init__(
        self,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        rcl_log: SqliteCommitLog,
        *,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Bind this reader to its three ports (plan §4.1's fixed interface) plus an OPTIONAL,
        additive ``scheme`` (module docstring's own disclosed widening — ``rcl_log`` is
        accepted per the fixed interface but is not read by this reader; it is reserved for a
        caller-symmetric construction site alongside :func:`committed_flow_vectors`, which
        takes its own ``rcl_log`` argument directly rather than reading it through this
        instance).

        Args:
            inbox: The durable event inbox (read-only — ``unconsumed_count`` only).
            evidence_store: The durable evidence store (read-only).
            rcl_log: Accepted for interface symmetry with :func:`committed_flow_vectors`;
                unused by this reader itself (module docstring).
            scheme: Optional canonicalization scheme — see module docstring's
                ``root_event_seq``/``handling_started_monotonic`` section.
        """
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

    def _resolve_handling_started_monotonic(
        self, root_event_seq: int | None
    ) -> int | None:
        if root_event_seq is None:
            return None
        receipt = self._inbox.handling_started_receipt(root_event_seq)
        if receipt is None:
            return None
        evidence_seq, _generation = receipt
        for entry in self._evidence_store.iter_entry_meta():
            if entry.seq == evidence_seq and entry.kind == _HANDLING_STARTED_KIND:
                return entry.appended_at_monotonic_ns
        return None

    def observe(
        self,
        *,
        root_event_id: str,
        attempt_id: str,
        root_event_seq: int | None = None,
    ) -> FlowObservation:
        """Assemble one :class:`FlowObservation` for ``root_event_id``/``attempt_id`` (module
        docstring).

        Args:
            root_event_seq: An OPTIONAL, additive, directly-resolved inbox seq for the root
                event (lane b widening, TOS risk state service wave team-lead disposition
                2026-09-16) — when supplied, it is used DIRECTLY in place of this reader's own
                ``root_event_id``-to-``event_identity``-recomputation match
                (:meth:`_resolve_root_event_seq`), which only succeeds when the caller's
                ``root_event_id`` string happens to equal the durable inbox's own
                content-addressed identity for that row — a coincidence this runtime's own
                compose test fixtures do NOT guarantee (measured:
                ``tests/compose/_fixtures.py::crossing_event`` sets ``reference.event_id`` to
                a human label, never that digest). A caller that already knows which inbox
                row is CURRENTLY being handled (e.g. ``SqliteEventInbox.next_unconsumed()``'s
                own ``seq`` — the engine handles exactly one inbox row at a time, so this is a
                genuine structural fact, not a guess) should resolve it there and pass it
                here, never recomputing an identity match. ``None`` (the default) preserves
                this reader's prior behavior unchanged."""
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

        cause_attempts: set[str] = set()
        in_flight_count = 0
        this_attempt_lineage_found: bool | None = None
        for payload in sealed_payloads:
            aid = payload.get("attempt_id")
            seal = payload.get("send_seal")
            if not isinstance(aid, str) or not isinstance(seal, Mapping):
                continue
            event_id, predecessors = _sealed_reference(seal)
            traces = _traces_to(root_event_id, event_id, predecessors)
            if aid == attempt_id:
                this_attempt_lineage_found = traces
            if traces:
                cause_attempts.add(aid)
                if aid not in terminal_attempts:
                    in_flight_count += 1

        sources: list[str] = []
        if sealed_payloads:
            sources.append(f"evidence:{_SEND_SEALED_KIND}")
        if consumed_payloads:
            sources.append("evidence:EGRESS_RESULT_CONSUMED")
        if unmatched_payloads:
            sources.append("evidence:RESULT_UNMATCHED")
        sources.append("inbox:unconsumed_count")

        resolved_root_event_seq: int | None
        if root_event_seq is not None:
            resolved_root_event_seq = root_event_seq
            sources.append("inbox:current_seq")
        else:
            resolved_root_event_seq = self._resolve_root_event_seq(root_event_id)
            if self._scheme is not None:
                sources.append("inbox:event_identity")
        handling_started_monotonic = self._resolve_handling_started_monotonic(
            resolved_root_event_seq
        )
        if handling_started_monotonic is not None:
            sources.append(f"evidence:{_HANDLING_STARTED_KIND}")

        return FlowObservation(
            queue_depth=self._inbox.unconsumed_count,
            in_flight=in_flight_count,
            attempts_for_cause=len(cause_attempts),
            duplicates_rejected=None,
            replays=None,
            root_event_seq=resolved_root_event_seq,
            handling_started_monotonic=handling_started_monotonic,
            lineage_found=this_attempt_lineage_found,
            sources=tuple(sources),
        )


def committed_flow_vectors(
    rcl_log: SqliteCommitLog, *, flow_dimension_id: str
) -> tuple[CapacityVector, ...]:
    """The RCL log's own committed Action Flow Permit vectors on ``flow_dimension_id`` (module
    docstring's own extensive "measured, and empirically ``()``" section — read that first).

    Each ``CommandType.ISSUE_ACTION_FLOW_PERMIT`` entry :meth:`~tos_runtime.rcl.log
    .SqliteCommitLog.replay` yields contributes one UNKNOWN-magnitude
    :class:`~tos.rcl.CapacityVector` (never a fabricated number — ``SqliteCommitLog`` exposes
    no public read of a committed entry's ``payload_json``, so this function can prove a
    committed permit EXISTS but not what it committed).
    """
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
    """Pure transform: :class:`FlowObservation` (+ the governed :class:`DeploymentFlowFacts`
    declaration + caller-supplied structural facts) -> :class:`~tos.afg.ObservedAmplification`
    (plan §2.1/§4.1).

    ``queries=0`` is a STRUCTURAL constant, not a literal fabrication: no ``tos_runtime``
    transport (``tos_runtime/transport/``) exposes any method whose name contains ``query`` —
    pinned mechanically by ``tests/riskstate/test_structural_pins.py`` so a future query path
    forces this observation to be rebuilt (module docstring's own cross-reference; DR-0003 §2.3
    "the number of broker queries — which is zero because the runtime's transports expose no
    query path, a structural fact pinned by a test"). ``mutations`` is defined as ``attempts``
    (plan §4.1) — a governed broker mutation IS an attempt in this runtime's vocabulary, there
    is no narrower "mutation-only" subset counted separately. ``amplification_per_cause`` is
    ``attempts / 1`` (plan §2.1's own formula — one root cause, so the per-cause rate is the
    raw attempt count).
    """
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
    """Pure transform: :class:`FlowObservation` -> :class:`~tos.afg.ActionCause` (plan
    §2.1/§4.1). Never a ``True``/``False`` literal except where derived as documented below:

    * ``lineage_attested = obs.lineage_found is True`` — a positive attestation ONLY when this
      reader positively traced the attempt's own sealed lineage to ``root_event_id``; ``None``
      (could not determine — no sealed row for this attempt at all) and ``False`` both yield
      ``lineage_attested=False``, never conflated with a genuine positive trace.
    * ``cyclic = root_event_id in (proposal_id,)`` — a purely structural self-reference check
      (plan §4.1's own formula), never an observation of a real cyclic graph.
    * ``forked_beyond_bound`` — ``None`` when either ``max_attempts`` or
      ``obs.attempts_for_cause`` is unavailable (fail-closed to UNKNOWN, never assumed within
      bound); otherwise the observed count strictly exceeding the injected bound.
    * ``inconsistent = None if obs.lineage_found is None else not obs.lineage_found`` — an
      attempt this reader could not place in the inbox at all stays UNKNOWN (never assumed
      consistent); one it PROVED does not trace to the named root is positively inconsistent.
    """
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
