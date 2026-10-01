"""Tests for :mod:`tos_runtime.riskstate.flow_observation` (TOS risk state service wave,
lane a)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.afg.records import ActionAmplificationEnvelope
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent, InstrumentKey
from tos.engine.vocabulary import EgressResultKind, EventKind
from tos.rcl import CommandType, CommitEntry
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.flow_observation import (
    REPLAYS_DEFINITION,
    FlowObservation,
    InboxFlowReader,
    committed_flow_vectors,
    count_duplicate_dispositions,
    count_recovery_markers,
    to_action_cause,
    to_observed_amplification,
)
from tos_runtime.riskstate.policies import DeploymentFlowFacts

from .._sqlite_plans import query_plans
from .conftest import (
    seed_egress_result,
    seed_recovery_marker,
    seed_send_sealed,
)

_ACCOUNT = "acct-1"
_INSTRUMENT = "K200F"
_ROOT = "ev-root"


def _empty_facts() -> DeploymentFlowFacts:
    return DeploymentFlowFacts(
        concurrent_consumers_share_one_envelope=False,
        envelope_reset_on_duplicate=False,
        duplicate_event_created_new_allowance=False,
    )


def test_empty_ports_yield_all_zero_observation(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.queue_depth == 0
    assert obs.in_flight == 0
    assert obs.attempts_for_cause == 0
    # TOS action-flow observation completion wave (2026-09-16): a completed durable-evidence
    # scan with no matches is a genuine 0, never None (module docstring's own "Two dedup
    # layers"/"replays" sections) — never None-by-omission.
    assert obs.duplicates_rejected == 0
    assert obs.replays == 0
    assert obs.replays_definition == REPLAYS_DEFINITION
    assert obs.root_event_seq is None
    assert obs.handling_started_monotonic is None
    assert obs.lineage_found is None


def test_attempt_traced_to_root_via_event_id(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="1",
        event_id=_ROOT,
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.lineage_found is True
    assert obs.attempts_for_cause == 1
    assert obs.in_flight == 1  # sealed, no terminal result


def test_attempt_traced_to_root_via_causal_predecessor(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="1",
        event_id="ev-child",
        causal_predecessor_ids=(_ROOT,),
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.lineage_found is True
    assert obs.attempts_for_cause == 1


def test_attempt_not_tracing_to_root_is_lineage_false(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="1",
        event_id="unrelated-event",
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.lineage_found is False
    assert obs.attempts_for_cause == 0


def test_absent_attempt_id_is_lineage_none(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """M2's own scenario: an attempt this reader never saw sealed at all stays UNKNOWN, never
    fabricated ``True``."""
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="never-sealed")
    assert obs.lineage_found is None


def test_terminal_attempt_is_not_in_flight(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="1",
        event_id=_ROOT,
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="1",
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.attempts_for_cause == 1
    assert obs.in_flight == 0


def test_queue_depth_reflects_inbox_unconsumed_count(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    # A real EngineEvent needs a full DecisionContextCapsule (many required fields); rather
    # than construct one just to exercise `unconsumed_count`, this test asserts the READER
    # surfaces whatever the inbox itself reports — verified against the inbox's own public
    # counter directly (a real read, no EngineEvent construction needed for the empty case).
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.queue_depth == inbox.unconsumed_count == 0


# ===========================================================================
# count_duplicate_dispositions / count_recovery_markers (pure helpers, TOS
# action-flow observation completion wave, 2026-09-16)
# ===========================================================================


def test_count_duplicate_dispositions_empty_scan_is_zero() -> None:
    assert count_duplicate_dispositions([], cause_attempts=set()) == 0


def test_count_duplicate_dispositions_counts_only_cause_attempts() -> None:
    payloads: list[dict[str, object]] = [
        {"result_disposition": "DUPLICATE", "attempt_id": "in-cause"},
        {"result_disposition": "DUPLICATE", "attempt_id": "outside-cause"},
    ]
    assert count_duplicate_dispositions(payloads, cause_attempts={"in-cause"}) == 1


def test_count_duplicate_dispositions_ignores_non_duplicate_disposition() -> None:
    payloads: list[dict[str, object]] = [
        {"result_disposition": "ORPHAN_NO_RESERVATION", "attempt_id": "a1"},
        {"result_disposition": "MISMATCHED_ATTEMPT", "attempt_id": "a1"},
    ]
    assert count_duplicate_dispositions(payloads, cause_attempts={"a1"}) == 0


def test_count_recovery_markers_empty_scan_is_zero() -> None:
    assert count_recovery_markers([], root_event_ids=frozenset()) == 0


def test_count_recovery_markers_ignores_unrelated_event_id() -> None:
    payloads: list[dict[str, object]] = [{"event_id": "unrelated"}]
    assert count_recovery_markers(payloads, root_event_ids=frozenset({"root-1"})) == 0


def test_count_recovery_markers_counts_each_recovery_kind() -> None:
    """Both marker kinds (module docstring's own :data:`_RECOVERY_MARKER_KINDS`) count when
    keyed to a matching ``event_id`` — the helper itself is kind-agnostic (the caller reads
    both kinds into one combined list), so this pins that neither kind is silently dropped.
    """
    payloads: list[dict[str, object]] = [{"event_id": "root-1"}, {"event_id": "root-1"}]
    assert count_recovery_markers(payloads, root_event_ids=frozenset({"root-1"})) == 2


# ===========================================================================
# InboxFlowReader.observe — real evidence-store integration (dedup/replay axes)
# ===========================================================================


def test_observe_counts_duplicate_disposition_from_real_evidence_store(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """Integration pin: a REAL ``RESULT_UNMATCHED`` row shaped exactly like
    ``tos/src/tos/engine/core.py:705-720``'s own emission (``result_disposition="DUPLICATE"``,
    ``attempt_id``) durably yields ``duplicates_rejected == 1`` — never ``None`` — for a cause
    the attempt traces to via ``SEND_SEALED`` lineage. ``replays`` stays a genuine ``0`` (no
    recovery marker was ever seeded, and no ``root_event_seq`` was supplied either)."""
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="1",
        event_id=_ROOT,
    )
    seed_egress_result(
        evidence_store,
        kind="RESULT_UNMATCHED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity=None,
        result_disposition="DUPLICATE",
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.duplicates_rejected == 1
    assert obs.replays == 0


def test_observe_ignores_duplicate_disposition_outside_cause(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """A ``DUPLICATE``-disposition row for an attempt that never sealed against THIS root
    (never a member of ``cause_attempts``) is never counted — the scan still completes and
    returns a genuine ``0``, not ``None``."""
    seed_egress_result(
        evidence_store,
        kind="RESULT_UNMATCHED",
        attempt_id="unrelated-attempt",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity=None,
        result_disposition="DUPLICATE",
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.duplicates_rejected == 0


def test_observe_counts_recovery_marker_for_resolved_root_event(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """Integration pin: a REAL restart-recovery marker keyed to the CURRENT row's own
    content-addressed ``event_id`` (read back via
    :meth:`InboxFlowReader._resolve_handling_started`'s own ``EVENT_HANDLING_STARTED``
    lookup, the SAME write-ahead idiom ``EngineDriver._process_next`` uses) durably yields
    ``replays >= 1`` — never ``None``, never silently zero for a genuinely matching marker.
    """
    payload = EgressResultPayload(
        instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
        attempt_id="a1",
        kind=EgressResultKind.ACK,
    )
    event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
    receipt = inbox.enqueue(event)
    marker = evidence_store.append(
        {"event_id": receipt.event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker.seq is not None
    assert marker.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    seed_recovery_marker(
        evidence_store,
        kind="DECISION_TICK_DROPPED_ON_RECOVERY",
        event_id=receipt.event_id,
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(
        root_event_id=_ROOT, attempt_id="a1", root_event_seq=receipt.seq
    )
    assert obs.replays == 1
    assert obs.duplicates_rejected == 0


def test_observe_ignores_recovery_marker_for_a_different_event(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """A recovery marker keyed to an unrelated ``event_id`` is never counted for this root —
    the scan still completes and returns a genuine ``0``, not ``None``."""
    seed_recovery_marker(
        evidence_store,
        kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
        event_id="some-other-event",
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1")
    assert obs.replays == 0


def _seed_real_handling_started(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore, *, attempt_id: str
) -> tuple[str, int]:
    """Enqueues one real ``EgressResultPayload`` event and durably marks it "handling
    started" — the SAME write-ahead idiom :meth:`test_observe_counts_recovery_marker_for_
    resolved_root_event` above already exercises, split out so the two new
    ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND``-kind tests below (review HIGH, PR #707: the
    prior suite never seeded this SECOND marker kind at all — removing it from
    ``_RECOVERY_MARKER_KINDS`` stayed green) don't repeat the setup. Returns the row's own
    ``(content-addressed event_id, inbox seq)``."""
    payload = EgressResultPayload(
        instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
        attempt_id=attempt_id,
        kind=EgressResultKind.ACK,
    )
    event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
    receipt = inbox.enqueue(event)
    marker = evidence_store.append(
        {"event_id": receipt.event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker.seq is not None
    assert marker.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    return receipt.event_id, receipt.seq


def test_observe_counts_handling_interrupted_possibly_live_send_marker(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """Review HIGH (PR #707): pins the SECOND recovery marker kind specifically —
    ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND`` (the halt path,
    ``tos_runtime/engine/driver.py:517-528``, ``record_halt``'s own payload shape, which also
    carries ``handling_started_evidence_seq`` alongside ``event_id`` — cited and reproduced by
    :func:`~tests.riskstate.conftest.seed_recovery_marker`'s own ``handling_started_evidence_
    seq`` argument). A mutation dropping this kind from ``_RECOVERY_MARKER_KINDS`` must fail
    this exact assertion (the prior suite only ever seeded the OTHER kind,
    ``DECISION_TICK_DROPPED_ON_RECOVERY``, so that mutation previously stayed green)."""
    event_id, seq = _seed_real_handling_started(inbox, evidence_store, attempt_id="a1")
    seed_recovery_marker(
        evidence_store,
        kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
        event_id=event_id,
        handling_started_evidence_seq=seq,
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1", root_event_seq=seq)
    assert obs.replays == 1


def test_observe_counts_both_recovery_marker_kinds_together(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """Review HIGH (PR #707): one marker of EACH kind for the SAME root event durably sums
    to ``replays == 2`` — pins that :func:`count_recovery_markers` is kind-agnostic once fed
    both kinds' payloads (:meth:`InboxFlowReader._count_amplification_axes` reads both kinds
    into one combined list before counting), not merely tolerant of either kind alone.
    """
    event_id, seq = _seed_real_handling_started(inbox, evidence_store, attempt_id="a1")
    seed_recovery_marker(
        evidence_store,
        kind="DECISION_TICK_DROPPED_ON_RECOVERY",
        event_id=event_id,
    )
    seed_recovery_marker(
        evidence_store,
        kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
        event_id=event_id,
        handling_started_evidence_seq=seq,
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)
    obs = reader.observe(root_event_id=_ROOT, attempt_id="a1", root_event_seq=seq)
    assert obs.replays == 2


# ===========================================================================
# committed_flow_vectors
# ===========================================================================


def test_committed_flow_vectors_empty_when_no_permit_entries(
    rcl_log: SqliteCommitLog,
) -> None:
    assert committed_flow_vectors(rcl_log, flow_dimension_id="afg.ORDER") == ()


def test_committed_flow_vectors_reports_unknown_magnitude_per_committed_permit(
    rcl_log: SqliteCommitLog,
) -> None:
    """A real ``CommandType.ISSUE_ACTION_FLOW_PERMIT`` entry is proven to exist but its
    magnitude cannot be read back (module docstring's own extensive gap disclosure) — this
    function reports it as an UNKNOWN-magnitude component, never a fabricated number."""
    identity = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")
    epoch = rcl_log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="permit-nonce-1",
        command_digest="permit-digest-1",
        kind=CommandType.ISSUE_ACTION_FLOW_PERMIT,
    )
    result = rcl_log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    from tos.rcl import AppendReceipt

    assert isinstance(result, AppendReceipt)

    vectors = committed_flow_vectors(rcl_log, flow_dimension_id="afg.ORDER")
    assert len(vectors) == 1
    assert vectors[0].magnitude("afg.ORDER") is None
    assert vectors[0].declares("afg.ORDER") is True


def test_committed_flow_vectors_ignores_non_permit_entries(
    rcl_log: SqliteCommitLog,
) -> None:
    identity = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")
    epoch = rcl_log.acquire_epoch(identity)
    entry = CommitEntry(
        command_id="cmd-1", command_digest="dig-1", kind=CommandType.COMMIT_RESERVATION
    )
    rcl_log.append_cas(entry, expected_seq=-1, writer_epoch=epoch)
    assert committed_flow_vectors(rcl_log, flow_dimension_id="afg.ORDER") == ()


# ===========================================================================
# to_observed_amplification (M3: queries pin)
# ===========================================================================


def test_to_observed_amplification_queries_always_zero() -> None:
    obs = FlowObservation(
        queue_depth=3,
        in_flight=2,
        attempts_for_cause=5,
        duplicates_rejected=1,
        replays=0,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=True,
        sources=(),
    )
    amp = to_observed_amplification(
        obs, _empty_facts(), elapsed_monotonic=Decimal(100), fan_out=1, depth=1
    )
    assert amp.queries == 0
    assert amp.attempts == 5
    assert amp.mutations == 5
    assert amp.queue_depth == 3
    assert amp.in_flight == 2
    assert amp.duplicate_redelivery_expansion == 1
    assert amp.failover_reconnect_replay_expansion == 0
    assert amp.amplification_per_cause == Decimal(5)
    assert amp.concurrent_consumers_share_one_envelope is False
    assert amp.envelope_reset_on_duplicate is False
    assert amp.duplicate_event_created_new_allowance is False


def test_to_observed_amplification_none_attempts_propagate() -> None:
    obs = FlowObservation(
        queue_depth=None,
        in_flight=None,
        attempts_for_cause=None,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=None,
        sources=(),
    )
    amp = to_observed_amplification(obs, _empty_facts(), elapsed_monotonic=None)
    assert amp.attempts is None
    assert amp.mutations is None
    assert amp.amplification_per_cause is None
    assert amp.queries == 0


def test_declares_every_bound_pin_still_requires_full_envelope() -> None:
    """Regression pin: :class:`~tos.afg.ActionAmplificationEnvelope` still requires every axis
    declared (unrelated to this module's own pure functions, but exercised so a future change
    to the kernel envelope shape is caught here too)."""
    envelope = ActionAmplificationEnvelope(
        max_fan_out=1,
        max_depth=1,
        max_attempts=1,
        max_mutations=1,
        max_queries=1,
        max_queue_depth=1,
        max_in_flight=1,
        max_elapsed_monotonic=Decimal(1000),
        max_duplicate_redelivery_expansion=1,
        max_failover_reconnect_replay_expansion=1,
        max_amplification_per_cause=Decimal(1),
    )
    assert envelope.declares_every_bound() is True


# ===========================================================================
# to_action_cause
# ===========================================================================


def test_to_action_cause_lineage_attested_follows_lineage_found_true() -> None:
    """M2: ``lineage_attested`` is ``True`` only when this reader positively traced lineage."""
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=1,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=True,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id=_ROOT,
        proposal_id="prop-1",
        command_identity="cmd-1",
        command_digest="dig-1",
        max_attempts=3,
    )
    assert cause.lineage_attested is True
    assert cause.inconsistent is False
    assert cause.cyclic is False
    assert cause.forked_beyond_bound is False
    assert cause.root_cause_identity == _ROOT
    assert cause.parent_lineage == ("prop-1",)


def test_to_action_cause_lineage_none_is_inconsistent_unknown_never_attested() -> None:
    """M2's own red scenario: an attempt not found in the inbox at all is ``inconsistent=None``
    (UNKNOWN) and NEVER ``lineage_attested=True`` without a real inbox read."""
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=0,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=None,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id=_ROOT,
        proposal_id="prop-1",
        command_identity=None,
        command_digest=None,
        max_attempts=None,
    )
    assert cause.lineage_attested is False
    assert cause.inconsistent is None
    assert cause.forked_beyond_bound is None


def test_to_action_cause_lineage_false_is_positively_inconsistent() -> None:
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=0,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=False,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id=_ROOT,
        proposal_id="prop-1",
        command_identity=None,
        command_digest=None,
        max_attempts=None,
    )
    assert cause.lineage_attested is False
    assert cause.inconsistent is True


def test_to_action_cause_cyclic_when_root_equals_proposal() -> None:
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=0,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=True,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id="same-id",
        proposal_id="same-id",
        command_identity=None,
        command_digest=None,
        max_attempts=None,
    )
    assert cause.cyclic is True


def test_to_action_cause_forked_beyond_bound() -> None:
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=5,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=True,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id=_ROOT,
        proposal_id="prop-1",
        command_identity=None,
        command_digest=None,
        max_attempts=3,
    )
    assert cause.forked_beyond_bound is True


def test_to_action_cause_forked_beyond_bound_none_when_max_attempts_absent() -> None:
    obs = FlowObservation(
        queue_depth=0,
        in_flight=0,
        attempts_for_cause=5,
        duplicates_rejected=None,
        replays=None,
        root_event_seq=None,
        handling_started_monotonic=None,
        lineage_found=True,
        sources=(),
    )
    cause = to_action_cause(
        obs,
        root_event_id=_ROOT,
        proposal_id="prop-1",
        command_identity=None,
        command_digest=None,
        max_attempts=None,
    )
    assert cause.forked_beyond_bound is None


def test_handling_started_monotonic_resolves_from_a_real_inbox_row(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """HIGH-4 (review of PR #704, 2026-09-16): every existing test above only exercises
    ``root_event_seq=None`` (8 instances). None pins the structural fix (team-lead
    disposition, same date) that resolves ``handling_started_monotonic`` from a REAL,
    currently-handled inbox row via ``current_seq_reader``/``next_unconsumed`` rather than an
    identity-recomputation match. This test enqueues a real ``EngineEvent``, marks it
    "handling started" with a real ``EVENT_HANDLING_STARTED`` evidence receipt — the SAME
    write-ahead idiom ``tos_runtime.engine.driver.EngineDriver._process_next`` itself uses
    (``driver.py``'s own ``_EVENT_HANDLING_STARTED_KIND``/``_EVENT_HANDLING_STARTED_RECORD_CLASS``
    constants) — and supplies that row's own ``seq`` via ``observe(root_event_seq=...)``,
    mirroring how :class:`~tos_runtime.riskstate.service.RiskStateService`'s
    ``current_seq_reader`` feeds this in production (built from
    ``SqliteEventInbox.next_unconsumed()`` in ``tos_runtime.compose._riskstate_wiring``).

    A mutation that hardcodes :meth:`InboxFlowReader._resolve_handling_started` (or
    ``RiskStateService._elapsed_monotonic_ms``) to always return ``None`` must fail exactly
    this assertion — the review's own M11 finding.
    """
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    payload = EgressResultPayload(
        instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
        attempt_id="a1",
        kind=EgressResultKind.ACK,
    )
    event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
    receipt = inbox.enqueue(event)
    marker = evidence_store.append(
        {"event_id": receipt.event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    assert marker.seq is not None
    assert marker.key_generation is not None
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log, scheme=scheme)
    obs = reader.observe(
        root_event_id=_ROOT, attempt_id="a1", root_event_seq=receipt.seq
    )
    assert obs.root_event_seq == receipt.seq
    assert obs.handling_started_monotonic is not None
    assert isinstance(obs.handling_started_monotonic, int)


# ============================================================================
# A2-b — the handling-started row is fetched by primary key, not walked
# (evidence growth plan docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md
#  §2 A2-b · §7.1.12 "읽어야 할 것" 2)
# ============================================================================


def _walk_handling_started_monotonic(
    evidence_store: SqliteEvidenceStore, evidence_seq: int
) -> int | None:
    """The PRE-A2-b resolution, reproduced verbatim: walk the whole table and take the first
    row matching both ``seq`` and the handling-started kind.

    Kept as the oracle the new primary-key lookup is compared against, so "faster" is held to
    "same answer" on the shapes where the answer is meant to be the same. The one shape where
    it is deliberately NOT the same — a row from another key generation — has its own test
    below, which asserts this oracle and the new resolution DISAGREE.
    """
    for entry in evidence_store.iter_entry_meta():
        if entry.seq == evidence_seq and entry.kind == "EVENT_HANDLING_STARTED":
            return entry.appended_at_monotonic_ns
    return None


def _resolved_monotonic(reader: InboxFlowReader, inbox_seq: int) -> int | None:
    facts = reader._resolve_handling_started(inbox_seq)
    return None if facts is None else facts.appended_at_monotonic_ns


def _seed_handling_started_pointing_at(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    *,
    shape: str,
) -> tuple[int, int]:
    """Enqueue one real event, append some unrelated evidence rows around it, and point the
    inbox row's handling-started receipt at ``shape``'s evidence row.

    Returns ``(inbox seq, the evidence seq that receipt names)``. The shapes are the ones the
    resolution can meet: the real marker row, a row of ANOTHER kind at that seq, a seq no row
    carries at all, and a marker row written under a DIFFERENT key generation than the one
    the receipt recorded (``stale_generation`` — what a restore from an older evidence backup
    under a surviving inbox looks like).
    """
    payload = EgressResultPayload(
        instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
        attempt_id="a1",
        kind=EgressResultKind.ACK,
    )
    event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
    receipt = inbox.enqueue(event)

    # Rows on both sides of the target, so a walk that stopped early or late would differ
    # from a lookup that goes straight to the row.
    evidence_store.append({"n": 0}, kind="NOISE", record_class="NOISE")
    marker_kind = (
        "SOME_OTHER_KIND" if shape == "kind_mismatch" else "EVENT_HANDLING_STARTED"
    )
    marker = evidence_store.append(
        {"event_id": receipt.event_id},
        kind=marker_kind,
        record_class=marker_kind,
    )
    evidence_store.append({"n": 1}, kind="NOISE", record_class="NOISE")
    assert marker.seq is not None
    assert marker.key_generation is not None

    evidence_seq = marker.seq
    generation = marker.key_generation
    if shape == "absent":
        evidence_seq = 10_000
    elif shape == "stale_generation":
        # The evidence file was replaced under a surviving inbox: the receipt still names a
        # seq, but the row now AT that seq was signed under a later generation — a different
        # event's marker. Rotating and re-appending reproduces that without mutating a row
        # (the append-only triggers forbid mutation, which is why this is the real shape).
        evidence_store.rotate(marker.key_generation + 1, b"rotated-key-bytes-riskstate")
        replacement = evidence_store.append(
            {"event_id": "some-other-events-identity"},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        assert replacement.seq is not None
        assert replacement.key_generation == marker.key_generation + 1
        evidence_seq = replacement.seq

    inbox.mark_handling_started(
        receipt.seq, evidence_seq=evidence_seq, generation=generation
    )
    return receipt.seq, evidence_seq


@pytest.mark.parametrize("shape", ["present", "kind_mismatch", "absent"])
def test_handling_started_lookup_agrees_with_the_pre_a2b_walk(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
    shape: str,
) -> None:
    """A2-b replaced a full-table walk with a primary-key lookup. Behaviour on the shapes the
    walk could meet must be byte-identical, absence included — the resolution's contract is a
    RECORDED absence (``None``), never a guessed timestamp, and a faster wrong answer would
    be worse than the slow one it replaced."""
    inbox_seq, evidence_seq = _seed_handling_started_pointing_at(
        inbox, evidence_store, shape=shape
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)

    expected = _walk_handling_started_monotonic(evidence_store, evidence_seq)
    resolved = _resolved_monotonic(reader, inbox_seq)

    assert resolved == expected
    if shape == "present":
        assert isinstance(resolved, int)
    else:
        assert resolved is None


def test_a_marker_row_from_another_key_generation_is_a_recorded_absence(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """``mark_handling_started`` stores ``(evidence_seq, generation)`` TOGETHER, and the
    generation is the half that says WHICH row the seq meant. Checking only ``kind`` accepts
    any handling-started row that happens to sit at that seq — so an evidence file restored
    from an older backup, or re-seeded, under a surviving inbox hands back ANOTHER event's
    timestamp and content identity as if they were this cause's. That is precisely the
    guessed fact this module's contract forbids, and it is silent.

    Both facts must come back absent, not merely the timestamp: ``content_event_id`` feeds
    ``count_recovery_markers``'s ``root_event_ids``, so a wrong identity there would count
    another event's recovery markers as this cause's replays.

    This test is red before the generation check: the assertion below shows the pre-A2-b
    walk — which also matched on ``kind`` alone — DOES return a value for this store, so the
    two disagree by design here, unlike the three shapes in the equality test above.
    """
    inbox_seq, evidence_seq = _seed_handling_started_pointing_at(
        inbox, evidence_store, shape="stale_generation"
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)

    # The row IS there and IS a handling-started row — kind alone accepts it.
    assert _walk_handling_started_monotonic(evidence_store, evidence_seq) is not None
    assert reader._resolve_handling_started(inbox_seq) is None


def test_handling_started_resolution_never_scans_the_evidence_table(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """The A2-b regression guard: the resolution must reach its row by primary key.

    Equality with the old walk (the test above) cannot catch a reintroduced scan — the walk
    returns the right answer, it just reads the whole history to get it, which is the ≥130 s
    per-proposal cost on a 365-day store that §2 A2-b exists to remove. So this asserts the
    PLAN instead: every statement the resolution issues against ``entries`` must seek the
    integer primary key, and none may scan. Red before A2-b: the walk's own
    ``SELECT … FROM entries ORDER BY seq ASC`` plans as ``SCAN entries``.
    """
    inbox_seq, _evidence_seq = _seed_handling_started_pointing_at(
        inbox, evidence_store, shape="present"
    )
    for index in range(20):
        evidence_store.append({"i": index}, kind="NOISE", record_class="NOISE")
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)

    plans = query_plans(
        evidence_store.connection,
        "entries",
        lambda: reader._resolve_handling_started(inbox_seq),
    )

    assert plans, "the resolution issued no statement against entries at all"
    assert not any(plan.startswith("SCAN") for plan in plans), plans
    assert all("USING INTEGER PRIMARY KEY" in plan for plan in plans), plans


def test_handling_started_resolution_reads_its_row_exactly_once(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    rcl_log: SqliteCommitLog,
) -> None:
    """Both facts come from ONE row, so one statement reads it. Before the merge, ``observe``
    read the same row twice per attempt — meta through the store, payload through a
    hand-written ``SELECT payload_json`` against the raw connection — and that second
    statement coupled this package to the ``entries`` column layout. Counting the statements
    pins the merge, which the plan guard above cannot see (two PK seeks both plan fine).
    """
    inbox_seq, _evidence_seq = _seed_handling_started_pointing_at(
        inbox, evidence_store, shape="present"
    )
    reader = InboxFlowReader(inbox, evidence_store, rcl_log)

    plans = query_plans(
        evidence_store.connection,
        "entries",
        lambda: reader._resolve_handling_started(inbox_seq),
    )
    assert len(plans) == 1, plans

    facts = reader._resolve_handling_started(inbox_seq)
    assert facts is not None
    assert isinstance(facts.appended_at_monotonic_ns, int)
    assert facts.content_event_id is not None
