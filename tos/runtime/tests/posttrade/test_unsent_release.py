"""Hermetic tests for :mod:`tos_runtime.posttrade.unsent_release` (#974 Q2; plan §5 ②④⑤).

Three layers, each answering a different question.

1. **The predicate, condition by condition** — a real :class:`~tos_runtime.evidence.store
   .SqliteEvidenceStore` holding exactly the rows a halted flow writes, with ONE of plan §3.1's
   five conditions removed per test. Writing the rows rather than deriving them is what makes a
   single-condition input constructible at all: a real sequencer cannot, for instance, produce a
   step-13 halt that also carries a ``SEND_SEALED`` row. :func:`test_a_real_halted_flow_is_the
   _shape_these_tests_write` is what keeps that honest — it drives a real
   :class:`~tos_runtime.engine.driver.EngineDriver` through a real halt and shows the predicate
   accepts the rows IT wrote.
2. **The trap review-1022 item 3 names** — a flow whose only send attempt ended in
   ``TRANSMIT_RAISED``, with no ``SEND_HANDED_OFF`` anywhere, which the kernel's own gates accept
   (asserted directly, so the test fails if the predicate ever stops being what refuses it).
3. **The release action** — RCL before engine, the row only on a ``True``, the boot-retry resume,
   and review-1022 item 4's same-reservation cross-check under a ``proposal_id`` collision.

Hermetic: ``tmp_path`` sqlite only, no network, no ambient env (D1.4).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme
from tos.engine import CommitmentStep, EngineCore, Stage
from tos.engine.records import InstrumentKey, UnsentDiscardRef
from tos.engine.state import ProvisionalReservationLedger
from tos.engine.vocabulary import (
    RESERVATION_DISCARDED_UNSENT_KIND,
    UnsentDiscardReason,
)
from tos.rcl import (
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.nontrade.latch import latch_restrictive
from tos_runtime.posttrade.close_history import (
    _UNSENT_RELEASE_CAUSE,
    _UNSENT_RELEASE_COMMAND_PREFIX,
)
from tos_runtime.posttrade.unsent_release import (
    CAPACITY_RELEASE_INTENT_KIND,
    SEND_EVIDENCE_KINDS,
    UNSENT_RELEASE_CAUSE,
    UNSENT_RELEASE_COMMAND_PREFIX,
    UnsentReleasePass,
    find_unsent_release_candidate,
    unsent_release_command_id,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id

from ..engine import _fixtures as fx
from ..engine.conftest import FakeMonotonicSource, FixedKeyProvider

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ACCOUNT = "acct-unsent"
_INSTRUMENT = "101U12"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_EVENT_ID = "event-unsent-1"
_PERMIT = "afg-permit-unsent-1"
#: A ``DECISION_TICK``'s ``EVENT_CONSUMED`` carries the emitted Proposal's canonical digest, and
#: a Proposal is content-addressed, so this is the id the predicate must reconstruct from it.
_OUTCOME_DIGEST = "d" * 64
_PROPOSAL_ID = f"prop-{_OUTCOME_DIGEST}"
_RESERVATION_ID = permit_reservation_id(_ACCOUNT, _INSTRUMENT, _PERMIT)
#: Step 14 — the last step before the Send Boundary, and the one plan §5 ③ injects a failure at.
_HALT_STEP = CommitmentStep.TRANSMISSION_CAPABILITY.value
#: Step 18 — AFTER the send boundary. ``TRANSMIT_RAISED``'s own step (review-1022 item 3).
_NETWORK_CALL_STEP = CommitmentStep.NETWORK_CALL.value
_NO_TIMEOUT_WITHIN_TEST = 10**12


# ===========================================================================
# fixtures + the row writer
# ===========================================================================


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> Iterator[SqliteEventInbox]:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def emergency_log(tmp_path: Path) -> EmergencyAppendLog:
    return EmergencyAppendLog(tmp_path / "emergency.jsonl")


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def _write_halted_flow(
    store: SqliteEvidenceStore,
    *,
    account: str = _ACCOUNT,
    instrument: str = _INSTRUMENT,
    event_id: str = _EVENT_ID,
    permit_identity: str | None = _PERMIT,
    halt_step: str | None = _HALT_STEP,
    consumed: bool = True,
    handed_off: bool = False,
    attempt_id: str | None = None,
    send_kind: str | None = None,
    interrupted_reason: str | None = None,
    possibly_live_row: bool = False,
    outcome_digest: str | None = _OUTCOME_DIGEST,
    fingerprint: bool = True,
    unreadable_event_id: bool = False,
) -> None:
    """Append the rows one pre-send halt leaves behind, in the order the live run writes them.

    Every default is the five-condition shape plan §3.1 admits; each keyword removes or changes
    exactly one of them. The field names are the ones the live writers use:
    ``tos.engine.records.EngineEvidenceRecord`` for the two kernel kinds and
    :meth:`tos_runtime.engine.driver.EngineDriver._record_consumed` for the receipt.
    """
    key = {"account": account, "instrument": instrument}
    if permit_identity is not None:
        store.append(
            {
                "kind": "FLOW_STEP_ADMITTED",
                "instrument_key": key,
                "step": CommitmentStep.ATOMIC_COMMIT.value,
                "event_id": 17 if unreadable_event_id else event_id,
                "bound_identity": permit_identity,
                "bound_digest": "conformance-digest",
            },
            kind="FLOW_STEP_ADMITTED",
            record_class="FLOW_STEP_ADMITTED",
        )
    if attempt_id is not None:
        store.append(
            {
                "kind": "ATTEMPT_REQUEST_CREATED",
                "instrument_key": key,
                "step": CommitmentStep.ATTEMPT_REQUEST.value,
                "event_id": event_id,
                "attempt_id": attempt_id,
            },
            kind="ATTEMPT_REQUEST_CREATED",
            record_class="ATTEMPT_REQUEST_CREATED",
        )
    if send_kind is not None:
        store.append(
            {"attempt_id": attempt_id, "event_id": event_id},
            kind=send_kind,
            record_class=send_kind,
        )
    if halt_step is not None:
        store.append(
            {
                "kind": "FLOW_HALTED",
                "instrument_key": key,
                "step": halt_step,
                "event_id": event_id,
                "halt_reason": "STAGE_UNKNOWN",
            },
            kind="FLOW_HALTED",
            record_class="FLOW_HALTED",
        )
    if possibly_live_row:
        store.append(
            {"event_id": event_id, "handling_started_evidence_seq": 1},
            kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
            record_class="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
        )
    if consumed:
        store.append(
            {
                "event_id": event_id,
                "payload_digest": "payload-digest",
                "outcome_digest": outcome_digest,
                "halt_reason": interrupted_reason or "STAGE_UNKNOWN",
                "flow_fingerprint": (
                    {
                        "handed_off": handed_off,
                        "halt_step": halt_step,
                        "halt_reason": "STAGE_UNKNOWN",
                        "attempt_id": None,
                    }
                    if fingerprint
                    else None
                ),
                "nontrade_disposition": None,
            },
            kind="EVENT_CONSUMED",
            record_class="EVENT_CONSUMED",
        )


def _candidate(store: SqliteEvidenceStore) -> Any:
    return find_unsent_release_candidate(
        store, account=_ACCOUNT, instrument=_INSTRUMENT
    )


# ===========================================================================
# plan §5 ② — the five conditions, one missing at a time
# ===========================================================================


def test_the_five_conditions_together_are_what_admits_a_release(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """The baseline every test below removes exactly one thing from."""
    _write_halted_flow(evidence_store, attempt_id="attempt-unsent-1")
    candidate = _candidate(evidence_store)
    assert candidate is not None
    assert candidate.event_id == _EVENT_ID
    assert candidate.proposal_id == _PROPOSAL_ID
    assert candidate.permit_identity == _PERMIT
    assert candidate.attempt_id == "attempt-unsent-1"
    assert candidate.halt_step == _HALT_STEP


def test_condition_1_without_the_step_9_commit_nothing_is_released(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """No ``FLOW_STEP_ADMITTED(ATOMIC_COMMIT)``: no reservation is attributable to this flow,
    so there is nothing this evidence can say about one."""
    _write_halted_flow(evidence_store, permit_identity=None)
    assert _candidate(evidence_store) is None


@pytest.mark.parametrize(
    "halt_step",
    [
        CommitmentStep.LEDGER_VERIFICATION.value,  # 8 — before the commit
        CommitmentStep.SEND_BOUNDARY_VERIFICATION.value,  # 15 — TRANSMIT_UNAVAILABLE
        _NETWORK_CALL_STEP,  # 18 — TRANSMIT_RAISED, possibly live
        CommitmentStep.EVIDENCE_RECORD.value,  # 19
    ],
)
def test_condition_2_a_halt_outside_steps_10_to_14_is_never_a_release(
    evidence_store: SqliteEvidenceStore, halt_step: str
) -> None:
    """Only the five steps between the atomic commit and the Send Boundary prove non-execution.

    Steps 15 and 18 are the two that matter in practice: ``TRANSMIT_UNAVAILABLE`` and
    ``TRANSMIT_RAISED`` both leave a ``NOT_SENT`` reservation the kernel would discard, and
    neither is evidence that nothing was sent.
    """
    _write_halted_flow(evidence_store, halt_step=halt_step)
    assert _candidate(evidence_store) is None


def test_condition_2_without_any_halt_at_all_nothing_is_released(
    evidence_store: SqliteEvidenceStore,
) -> None:
    _write_halted_flow(evidence_store, halt_step=None)
    assert _candidate(evidence_store) is None


@pytest.mark.parametrize("send_kind", SEND_EVIDENCE_KINDS)
def test_condition_3_any_send_record_in_the_flow_window_refuses(
    evidence_store: SqliteEvidenceStore, send_kind: str
) -> None:
    """All four kinds, each on its own: a hand-off, a seal, and the transport's two rows."""
    _write_halted_flow(
        evidence_store, attempt_id="attempt-unsent-1", send_kind=send_kind
    )
    assert _candidate(evidence_store) is None


def test_condition_3_a_receipt_whose_fingerprint_says_handed_off_refuses(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """The receipt's own flow fingerprint is the second, independent source for condition 3 —
    it comes off the live ``EventResult``, not off the rows the sink wrote."""
    _write_halted_flow(evidence_store, handed_off=True)
    assert _candidate(evidence_store) is None


def test_condition_3_a_receipt_with_no_fingerprint_at_all_refuses(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A pre-CR6 receipt proves nothing about the hand-off, so it releases nothing."""
    _write_halted_flow(evidence_store, fingerprint=False)
    assert _candidate(evidence_store) is None


def test_condition_4_an_interrupted_handling_is_never_read_as_not_sent(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """``HANDLING_INTERRUPTED_*`` means "we do not know whether it was sent" (``driver.py``)."""
    _write_halted_flow(
        evidence_store, interrupted_reason="HANDLING_INTERRUPTED_NO_SEND_EVIDENCE"
    )
    assert _candidate(evidence_store) is None


def test_condition_4_a_possibly_live_send_halt_row_for_this_event_refuses(
    evidence_store: SqliteEvidenceStore,
) -> None:
    _write_halted_flow(evidence_store, possibly_live_row=True)
    assert _candidate(evidence_store) is None


def test_condition_5_without_the_consumption_receipt_nothing_is_released(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """No ``EVENT_CONSUMED``: the flow was not recorded to its end, so nothing is concluded —
    and writing the discard row here would sort it ahead of its own event on the next boot.
    """
    _write_halted_flow(evidence_store, consumed=False)
    assert _candidate(evidence_store) is None


def test_a_flow_in_another_scope_is_never_this_scope_s_candidate(
    evidence_store: SqliteEvidenceStore,
) -> None:
    _write_halted_flow(evidence_store, instrument="101U03")
    assert _candidate(evidence_store) is None


def test_a_receipt_with_no_outcome_digest_releases_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Without the digest there is no proposal identity to hand the kernel."""
    _write_halted_flow(evidence_store, outcome_digest=None)
    assert _candidate(evidence_store) is None


# ===========================================================================
# plan §5 ② — an evidence read failure releases nothing
# ===========================================================================


def test_an_unreadable_evidence_store_releases_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A closed connection raises out of the very first query; the answer is "no candidate"."""
    _write_halted_flow(evidence_store)
    assert _candidate(evidence_store) is not None
    evidence_store.connection.close()
    assert _candidate(evidence_store) is None


def test_an_unreadable_anchor_row_releases_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Ambiguity is not an absence of send evidence. The scope's newest step-9 commit carries no
    readable ``event_id``, so nothing downstream of it can be correlated — and the answer is a
    refusal, never a fall-through to an older commit that is no longer the one being held.
    """
    _write_halted_flow(evidence_store, unreadable_event_id=True)
    assert _candidate(evidence_store) is None


# ===========================================================================
# plan §5 ⑤ + review-1022 item 3 — the two shapes that look discardable to the kernel
# ===========================================================================


def test_a_halt_after_the_send_was_sealed_releases_nothing(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """Plan §5 ⑤. The realistic shape: the gateway sealed the send, the transport wrote its row,
    and the call then failed at step 18. TWO independent conditions refuse it."""
    _write_halted_flow(
        evidence_store,
        attempt_id="attempt-unsent-sealed",
        send_kind="SEND_SEALED",
        halt_step=_NETWORK_CALL_STEP,
    )
    assert _candidate(evidence_store) is None


def test_the_transmit_raised_trap_is_refused_although_the_kernel_would_accept_it(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """review-1022 item 3, on the real store a raising transmit leaves behind.

    Concrete input: a live flow whose ``transmit`` raised. The store then holds ``FLOW_HALTED``
    at step 18 (``TRANSMIT_RAISED``) and NO ``SEND_HANDED_OFF`` row anywhere — so a boot replay
    installs no recorded transmit at all (``any_recorded_hand_off`` is false) and rebuilds that
    reservation as ``ATTEMPT_BOUND``/``NOT_SENT``, which is the ledger built below. The order may
    be live at the broker.

    Concrete result: the kernel accepts a discard of that rebuilt reservation (asserted last — so
    this test fails the day the predicate stops being what refuses), the predicate returns no
    candidate, and the whole pass — RCL reservation present, so nothing else can be what stops it
    — releases nothing.
    """

    def _raising_transmit(attempt: Any) -> Any:
        raise RuntimeError("the socket died mid-call")

    live = fx.build_core(
        stages=fx.admitting_stages(),
        transmit=_raising_transmit,
        sink=EngineEvidenceSinkAdapter(evidence_store),
    )
    driver = _driver(live, inbox, evidence_store, emergency_log)
    driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert _seqs(evidence_store, "SEND_HANDED_OFF") == []
    held = live.ledger.outstanding(fx.instrument_key())
    assert held is not None and held.proposal_id is not None
    assert held.attempt_id is not None

    # What a boot replay rebuilds from exactly that store: no hand-off recorded, so the replay
    # core is built with transmit=None and the flow stops at step 15 — never reaching
    # mark_potentially_live, which is why this is ATTEMPT_BOUND/NOT_SENT and not POTENTIALLY_LIVE.
    rebuilt = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    rebuilt.commit_unbound(fx.instrument_key(), proposal_id=held.proposal_id)
    rebuilt.bind_attempt(fx.instrument_key(), attempt_id=held.attempt_id)
    _open_rcl_reservation(
        rcl_log,
        reservation_id=permit_reservation_id(
            fx.ACCOUNT, fx.INSTRUMENT, fx.PERMIT_IDENTITY
        ),
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
    )

    assert (
        find_unsent_release_candidate(
            evidence_store, account=fx.ACCOUNT, instrument=fx.INSTRUMENT
        )
        is None
    )
    assert (
        UnsentReleasePass(
            rcl_log=rcl_log,
            projection=SqliteReservationProjectionReader(rcl_log),
            evidence_store=evidence_store,
            ledger=rebuilt,
            scheme=SCHEME,
            account=fx.ACCOUNT,
            instrument=fx.INSTRUMENT,
        ).run()
        is False
    )
    assert rebuilt.outstanding(fx.instrument_key()) is not None
    # The kernel's own gates: nothing here refuses, which is the whole point of item 3.
    assert (
        rebuilt.discard_unsent(
            UnsentDiscardRef(
                proposal_id=held.proposal_id,
                reason=UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION,
            )
        )
        is True
    )


# ===========================================================================
# the real driver — the shapes above, and review-1022 item 1's write order
# ===========================================================================


def _driver(
    core: EngineCore,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> EngineDriver:
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=SCHEME,
        continuity_id="unsent-release-tests",
        monotonic_source=FakeMonotonicSource(),
        max_send_result_wait_ms=_NO_TIMEOUT_WITHIN_TEST,
        orthostate_projector=fx.orthostate_projector(
            inbox, evidence_store, emergency_log
        ),
        finality_producer=fx.finality_producer(),
    )
    driver.bind_nontrade_latch(latch_restrictive)
    return driver


def _halting_core(
    evidence_store: SqliteEvidenceStore, *, step: CommitmentStep
) -> EngineCore:
    stages: dict[CommitmentStep, Stage] = fx.admitting_stages(
        unknown_steps=frozenset({step})
    )
    return fx.build_core(
        stages=stages,
        transmit=None,
        sink=EngineEvidenceSinkAdapter(evidence_store),
    )


def _seqs(store: SqliteEvidenceStore, kind: str) -> list[int]:
    return [
        int(seq)
        for (seq,) in store.connection.execute(
            "SELECT seq FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def _open_rcl_reservation(
    rcl_log: SqliteCommitLog,
    *,
    reservation_id: str,
    account: str,
    instrument: str,
) -> None:
    """Commit the ``COMMITTED_UNBOUND`` row step 9 commits in production."""
    epoch = rcl_log.acquire_epoch(
        RuntimeIdentity(cell_id="unsent-cell", process_nonce="unsent-nonce")
    )
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.COMMITTED_UNBOUND,
            scope=ReservationScope(account=account, instrument=instrument),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.COMMIT_RESERVATION,
        command_id=f"commit-{reservation_id}",
        command_digest=f"dig-{reservation_id}",
        expected_seq=-1 if view.last_seq is None else view.last_seq,
    )


def test_a_real_halted_flow_is_the_shape_these_tests_write_and_the_row_follows_its_receipt(
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    emergency_log: EmergencyAppendLog,
    rcl_log: SqliteCommitLog,
) -> None:
    """review-1022 item 1, on the real seam, plus the pin for the written-row tests above.

    Concrete input: a tick whose step-14 stage answers UNKNOWN, driven through a real
    ``EngineDriver`` with the pass bound to ``bind_after_turn``; then a second tick. Concrete
    result: the predicate accepts the rows the REAL run wrote, and the
    ``RESERVATION_DISCARDED_UNSENT`` row lands strictly after the halting event's own
    ``EVENT_CONSUMED`` and strictly before the next event's — the window
    :mod:`tos_runtime.engine.replay_discards` re-applies it in. The second tick is then admitted
    past step 8, which is the #974 block clearing.
    """
    core = _halting_core(evidence_store, step=CommitmentStep.TRANSMISSION_CAPABILITY)
    reservation_id = permit_reservation_id(
        fx.ACCOUNT, fx.INSTRUMENT, fx.PERMIT_IDENTITY
    )
    _open_rcl_reservation(
        rcl_log,
        reservation_id=reservation_id,
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
    )
    driver = _driver(core, inbox, evidence_store, emergency_log)
    release = UnsentReleasePass(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        ledger=core.ledger,
        scheme=SCHEME,
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
    )
    driver.bind_after_turn(release)

    first = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert first.flow is not None
    assert first.flow.halt_step is CommitmentStep.TRANSMISSION_CAPABILITY
    first_consumed, *_ = _seqs(evidence_store, "EVENT_CONSUMED")
    (discard_seq,) = _seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)
    assert discard_seq > first_consumed
    assert (
        SqliteReservationProjectionReader(rcl_log).reservation_state(reservation_id)
        is CapacityState.RELEASED
    )

    second = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    consumed = _seqs(evidence_store, "EVENT_CONSUMED")
    assert len(consumed) == 2
    assert first_consumed < discard_seq < consumed[1]
    # The second tick reached step 14 — so step 8 admitted it. Before the release it would have
    # stopped at LEDGER_VERIFICATION with AT_MOST_ONE_EXPOSURE_HELD, which is the #974 block.
    assert second.flow is not None
    assert second.flow.halt_step is CommitmentStep.TRANSMISSION_CAPABILITY


# ===========================================================================
# the release action — order, idempotency, and the same-reservation cross-check
# ===========================================================================


def _ledger(
    *, proposal_id: str = _PROPOSAL_ID, attempt_id: str | None = None
) -> ProvisionalReservationLedger:
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    ledger.commit_unbound(_KEY, proposal_id=proposal_id)
    if attempt_id is not None:
        ledger.bind_attempt(_KEY, attempt_id=attempt_id)
    return ledger


def _pass(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    ledger: ProvisionalReservationLedger,
) -> UnsentReleasePass:
    return UnsentReleasePass(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        ledger=ledger,
        scheme=SCHEME,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )


def _release_transitions(rcl_log: SqliteCommitLog) -> list[Any]:
    history = rcl_log.reservation_transition_history(
        writer_epoch=rcl_log.current_epoch()
    )
    return [
        row for row in history.transitions if row.to_state is CapacityState.RELEASED
    ]


def test_the_release_commits_the_rcl_then_the_engine_and_records_both_rows(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """The whole action on the happy path, with every durable consequence named."""
    _write_halted_flow(evidence_store)
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    ledger = _ledger()

    assert _pass(rcl_log, evidence_store, ledger).run() is True

    projection = SqliteReservationProjectionReader(rcl_log)
    assert projection.reservation_state(_RESERVATION_ID) is CapacityState.RELEASED
    assert ledger.outstanding(_KEY) is None
    assert ledger.admits_new_exposure(_KEY) is True
    (transition,) = _release_transitions(rcl_log)
    assert transition.command_id == unsent_release_command_id(_RESERVATION_ID)
    assert transition.cause is TransitionCause.FINAL_QUANTITY_PROOF
    assert transition.kind is CommandType.RELEASE_RESERVATION
    assert transition.finality_witness is True
    assert len(_seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)) == 1
    intent = _payloads(evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    assert len(intent) == 1
    assert intent[0]["cause"] == UNSENT_RELEASE_CAUSE
    assert intent[0]["reservation_id"] == _RESERVATION_ID
    assert intent[0]["proof_id"] is None


def _payloads(store: SqliteEvidenceStore, kind: str) -> list[dict[str, Any]]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def test_a_repeated_run_after_the_discard_writes_no_second_row(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """review-1022 item 5's idempotency half, in one process: the scope holds nothing any more,
    so every later turn stops before the kernel is asked a second time."""
    _write_halted_flow(evidence_store)
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    ledger = _ledger()
    release = _pass(rcl_log, evidence_store, ledger)

    assert release.run() is True
    assert release.run() is False
    assert release.run() is False

    assert len(_seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)) == 1
    assert len(_release_transitions(rcl_log)) == 1


def test_a_boot_whose_rcl_release_already_committed_finishes_the_engine_half_only(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """review-1022 item 5's crash half. The RCL release committed, then the process died before
    the engine discard — the durable state a ``kill -9`` in that window leaves. A fresh boot
    rebuilds the engine ledger (the replay does), finds the RCL already ``RELEASED``, skips the
    RCL step, and does the engine half: exactly one release transition, exactly one row.
    """
    _write_halted_flow(evidence_store)
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    crashed = _pass(rcl_log, evidence_store, _ledger())
    assert crashed._commit_rcl_release(  # noqa: SLF001 - the exact kill-9 window
        _RESERVATION_ID, from_state=CapacityState.COMMITTED_UNBOUND
    )
    assert _seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND) == []

    rebooted_ledger = _ledger()
    assert _pass(rcl_log, evidence_store, rebooted_ledger).run() is True

    assert rebooted_ledger.outstanding(_KEY) is None
    assert len(_release_transitions(rcl_log)) == 1
    assert len(_seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND)) == 1


def test_without_an_rcl_reservation_row_nothing_is_released(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """The permit the evidence names must resolve to a reservation the authority actually holds."""
    _write_halted_flow(evidence_store)
    ledger = _ledger()
    assert _pass(rcl_log, evidence_store, ledger).run() is False
    assert ledger.outstanding(_KEY) is not None


# -- review-1022 item 4 ------------------------------------------------------


def test_a_proposal_id_collision_releases_no_other_scope_s_reservation(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """review-1022 item 4 / LOW-1, as a probe.

    ``discard_unsent`` resolves a ``proposal_id`` across EVERY scope and removes the first match.
    Here the judged scope has moved on to another proposal while a sibling scope still holds the
    judged one — so the kernel, asked, would delete the sibling's entry. The cross-check refuses
    before the kernel is asked at all: nothing is released, in either scope, and the RCL commits
    no transition.
    """
    _write_halted_flow(evidence_store)
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    sibling = InstrumentKey(account=_ACCOUNT, instrument="101U03")
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    ledger.commit_unbound(sibling, proposal_id=_PROPOSAL_ID)
    ledger.commit_unbound(_KEY, proposal_id="prop-a-different-proposal")

    assert _pass(rcl_log, evidence_store, ledger).run() is False

    assert ledger.outstanding(sibling) is not None
    assert ledger.outstanding(_KEY) is not None
    assert _release_transitions(rcl_log) == []
    assert _seqs(evidence_store, RESERVATION_DISCARDED_UNSENT_KIND) == []


def test_an_attempt_binding_the_evidence_does_not_name_refuses(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """The other half of item 4: the scope's reservation is bound to an attempt this flow's
    evidence never created, so the judgement is not about this reservation."""
    _write_halted_flow(evidence_store, attempt_id="attempt-from-evidence")
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    ledger = _ledger(attempt_id="attempt-the-ledger-holds")

    assert _pass(rcl_log, evidence_store, ledger).run() is False
    assert ledger.outstanding(_KEY) is not None


def test_a_matching_attempt_binding_is_released(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """The positive control for the test above — a step-13/14 halt binds an attempt, and the
    same attempt on both sides is admitted."""
    _write_halted_flow(evidence_store, attempt_id="attempt-both-sides")
    _open_rcl_reservation(
        rcl_log,
        reservation_id=_RESERVATION_ID,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    )
    ledger = _ledger(attempt_id="attempt-both-sides")

    assert _pass(rcl_log, evidence_store, ledger).run() is True
    assert ledger.outstanding(_KEY) is None


def test_an_empty_scope_is_the_cheap_short_circuit(
    evidence_store: SqliteEvidenceStore, rcl_log: SqliteCommitLog
) -> None:
    """Nothing outstanding: the pass answers without reading the evidence store at all, which
    is what makes binding it to every drained turn affordable."""
    _write_halted_flow(evidence_store)
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    evidence_store.connection.close()  # any read at all would raise through
    assert _pass(rcl_log, evidence_store, ledger).run() is False


def test_the_close_history_literals_stay_in_lockstep_with_this_module() -> None:
    """``close_history`` redeclares both strings (its own lockstep-literal convention); this is
    the test its comment points at."""
    assert _UNSENT_RELEASE_CAUSE == UNSENT_RELEASE_CAUSE
    assert _UNSENT_RELEASE_COMMAND_PREFIX == UNSENT_RELEASE_COMMAND_PREFIX
    assert UnsentDiscardReason.UNSENT_FLOW_NON_EXECUTION.value == UNSENT_RELEASE_CAUSE


def test_the_kernel_at_most_one_retention_is_what_anchors_the_predicate(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """The anchor is the NEWEST step-9 commit for the scope, and the kernel guarantees there can
    be only one unresolved reservation behind it — a later tick that halts at step 8 against it
    records no commit of its own, so it cannot move the anchor. That is the #974 shape itself.
    """
    _write_halted_flow(evidence_store)
    ledger = _ledger()
    with pytest.raises(ArtifactIntegrityError):
        ledger.commit_unbound(_KEY, proposal_id="prop-a-second-one")
    _write_halted_flow(
        evidence_store,
        event_id="event-unsent-2",
        permit_identity=None,
        halt_step=CommitmentStep.LEDGER_VERIFICATION.value,
    )
    candidate = _candidate(evidence_store)
    assert candidate is not None and candidate.event_id == _EVENT_ID
