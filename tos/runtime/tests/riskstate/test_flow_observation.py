"""Tests for :mod:`tos_runtime.riskstate.flow_observation` (TOS risk state service wave,
lane a)."""

from __future__ import annotations

from decimal import Decimal

from tos.afg.records import ActionAmplificationEnvelope
from tos.rcl import CommandType, CommitEntry
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.flow_observation import (
    FlowObservation,
    InboxFlowReader,
    committed_flow_vectors,
    to_action_cause,
    to_observed_amplification,
)
from tos_runtime.riskstate.policies import DeploymentFlowFacts

from .conftest import seed_send_sealed

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
    assert obs.duplicates_rejected is None
    assert obs.replays is None
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
    from .conftest import seed_egress_result

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
