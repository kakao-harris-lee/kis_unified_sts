"""GAP 1 close-out tests (TOS Phase 5 W1) for :mod:`tos_runtime.recovery.reconciliation`'s
per-attempt design, over REAL durable stores (``SqliteCommitLog``/``SqliteEvidenceStore``) so
that :class:`~tos_runtime.recon.service.ReconciliationClass.MATCHED` is exercised genuinely,
not through fakes — the ``reservation_id_for_attempt`` bridge only matters against a REAL
:class:`~tos_runtime.rcl.projection.SqliteReservationProjectionReader` over a REAL committed
reservation.

The four scenarios below are the task brief's own acceptance tests:

(a) a possibly-live attempt whose evidence + witness corroborate (a ``FULL_FILL`` receipt with
    finality proof, a durably-linked ``attempt_id`` via ``SEND_HANDED_OFF``, and an open RCL
    reservation) — split into two tests by independent-review finding F2 (2026-09-10), since a
    same-store witness can no longer count as independent corroboration on its own:
    (a1) ``test_a1_synthetic_witness_holds_with_witness_not_independent`` — the SAME
    corroborating setup, but reconciled with the real, store-derived
    ``SyntheticLedgerWitness``, stays HELD with reason ``WITNESS_NOT_INDEPENDENT`` (never
    ``READY``) because the witness is not independent of the evidence-receipt path it is meant
    to corroborate; and
    (a2) ``test_a2_an_independent_witness_double_clears_the_same_attempt`` — the identical
    attempt, but reconciled against a genuinely independent witness double
    (``independent_of_evidence_store=True``, distinct provenance), clears
    (``permits_capacity_release`` and ``permits_rearm`` both ``True``).
(b) the same attempt, but the evidence store is unreachable when reconciliation runs, stays
    HELD with :data:`~tos_runtime.recovery.reconciliation.RECON_UNAVAILABLE`.
(c) the SAME corroborating setup as (a), but the time service never started (so
    :mod:`tos_runtime.recovery.reconciliation`'s own ``_build_freshness_marker`` falls back to
    the kernel's all-``None`` :class:`~tos.recon.FreshnessMarker` default), stays HELD —
    freshness fails closed regardless of how strong the rest of the evidence is.
(d) a mutation guard, at the ``ReconciliationService`` level directly: a stub service that
    reports ``permits_capacity_release`` alone (never ``permits_rearm``) must NOT clear the
    attempt — pins the conjunction :mod:`tos_runtime.recovery.reconciliation`'s own
    ``_reconcile_one`` requires.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from tos.engine.records import event_identity
from tos.rcl import (
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.recon import FreshnessMarker
from tos.time.domains import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recon.ports import (
    EgressReceiptObservation,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import (
    WITNESS_NOT_INDEPENDENT_REASON,
    ReconciliationClass,
    ReconciliationReport,
    ReconciliationService,
)
from tos_runtime.recovery.barrier import RecoveryBarrier
from tos_runtime.recovery.inputs import RecoveryInputs
from tos_runtime.recovery.legacy_receipts import LegacyReceiptFacts
from tos_runtime.recovery.possibly_live import PossiblyLiveAttempt
from tos_runtime.recovery.reconciliation import (
    NO_ATTEMPT_ID,
    RECON_UNAVAILABLE,
    RECONCILED_MATCHED,
    ReconciliationOutcome,
    _reconcile_one,
    reconcile_possibly_live_attempts,
)
from tos_runtime.time.service import TimeServiceNotStarted

from .conftest import SCHEME, fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ATTEMPT_ID = "attempt-recon-a"


class _TrustedTimeService:
    """A minimal :class:`~tos_runtime.time.service.TrustworthyTimeService` double reporting a
    genuinely TRUSTED snapshot — mirrors ``test_inputs.py``'s own ``_NeverStartedTimeService``
    convention (a plain duck-typed double, not the real class) for the OTHER end of the same
    fail-closed/fail-open contrast."""

    def current_snapshot(self) -> SimpleNamespace:
        identity = SimpleNamespace(tts_generation=1)
        return SimpleNamespace(
            health_state=HealthState.TRUSTED, time_continuity_identity=identity
        )


class _NeverStartedTimeService:
    """Reused from ``test_inputs.py``'s own convention: raises the SAME
    ``TimeServiceNotStarted`` a genuinely never-started real service raises."""

    def current_snapshot(self):
        raise TimeServiceNotStarted("never started (test double)")


@pytest.fixture()
def rcl_log(tmp_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def _open_the_scope_reservation(rcl_log: SqliteCommitLog) -> None:
    """Commit a genuinely OPEN RCL reservation under this compose root's own scope-level id
    (``f"resv-{account}-{instrument}"``) — the identity :mod:`tos_runtime.recovery.reconciliation`
    resolves every attempt id onto."""
    key = fx.instrument_key()
    identity = RuntimeIdentity(cell_id="test-cell", process_nonce="test-nonce-1")
    epoch = rcl_log.acquire_epoch(identity)
    transition = CapacityReservationTransition(
        reservation_id=f"resv-{key.account}-{key.instrument}",
        writer_epoch=epoch,
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=ReservationScope(account=key.account, instrument=key.instrument),
    )
    rcl_log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-recon-test",
        command_digest="dig-recon-test",
        expected_seq=-1,
    )


def _record_corroborating_evidence(
    evidence_store: SqliteEvidenceStore, *, event_id: str
) -> None:
    """Everything (a) needs from the evidence store alone: the ``SEND_HANDED_OFF`` link, a
    ``FULL_FILL`` receipt, and its finality proof."""
    key = fx.instrument_key()
    evidence_store.append(
        {"event_id": event_id, "attempt_id": _ATTEMPT_ID},
        kind="SEND_HANDED_OFF",
        record_class="SEND_HANDED_OFF",
    )
    evidence_store.append(
        {
            "attempt_id": _ATTEMPT_ID,
            "instrument_key": {"account": key.account, "instrument": key.instrument},
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": "10",
            "remaining_quantity": "0",
            "broker_execution_id": "exec-recon-a",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    evidence_store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{_ATTEMPT_ID}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def _one_possibly_live_attempt(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> PossiblyLiveAttempt:
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = evidence_store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    return PossiblyLiveAttempt(
        event_id=event_id,
        inbox_seq=receipt.seq,
        handling_started_evidence_seq=marker.seq,
        handling_started_generation=marker.key_generation,
    )


def _clean_inputs(**overrides: object) -> RecoveryInputs:
    base: dict[str, object] = {
        "rcl_writer_epoch": 1,
        "rcl_runtime_generation": 1,
        "open_reservations": (),
        "evidence_tip_seq": 1,
        "evidence_tip_key_generation": 1,
        "legacy_receipts": LegacyReceiptFacts(count=0, event_ids=()),
        "inbox_unconsumed_count": 1,
        "possibly_live_attempts": (),
        "composite_state_incomplete_attempt_ids": (),
        "custody_environment_label": "non-live-test",
        "custody_manifest_digest": "a" * 64,
    }
    base.update(overrides)
    return RecoveryInputs(**base)  # type: ignore[arg-type]


def test_a1_synthetic_witness_holds_with_witness_not_independent(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """Independent-review finding F2 (HIGH): ``reconcile_possibly_live_attempts`` always builds
    a :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness` (Phase 5's only real
    path) — store-derived, never independent of the evidence-receipt path it also reads. Even
    with a fully corroborating setup (SEND_HANDED_OFF link, matching receipt + finality proof,
    an open RCL reservation), the attempt now correctly HOLDS with
    :data:`~tos_runtime.recon.service.WITNESS_NOT_INDEPENDENT_REASON` — this is the honest state
    until a genuinely independent (e.g. real broker) witness replaces it. See
    ``test_a2_an_independent_witness_double_clears_the_same_attempt`` below for the OTHER half,
    proven directly at the :class:`~tos_runtime.recon.service.ReconciliationService` level.
    """
    attempt = _one_possibly_live_attempt(inbox, evidence_store)
    _record_corroborating_evidence(evidence_store, event_id=attempt.event_id)
    _open_the_scope_reservation(rcl_log)
    key = fx.instrument_key()

    reconciliation = reconcile_possibly_live_attempts(
        (attempt,),
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        time_service=_TrustedTimeService(),
        account=key.account,
        instrument=key.instrument,
    )

    assert reconciliation[attempt.event_id] == ReconciliationOutcome(
        cleared=False, reason=WITNESS_NOT_INDEPENDENT_REASON
    )

    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            possibly_live_attempts=(attempt,),
            possibly_live_reconciliation=reconciliation,
        )
    )
    assert verdict.ready is False


def test_a2_an_independent_witness_double_clears_the_same_attempt() -> None:
    """The OTHER half of F2: a genuinely independent witness double (``provenance`` naming a
    real broker, ``independent_of_evidence_store=True``) — never
    ``reconcile_possibly_live_attempts`` (which always builds a ``SyntheticLedgerWitness``), but
    :class:`~tos_runtime.recon.service.ReconciliationService` directly, the SAME mechanism that
    function uses internally — CAN clear a matching attempt, proving F2's fix narrows on the
    witness's OWN declared independence, not on some unrelated always-false gate."""
    key = fx.instrument_key()
    receipt = EgressReceiptObservation(
        attempt_id=_ATTEMPT_ID,
        account=key.account,
        instrument=key.instrument,
        egress_result_kind="FULL_FILL",
        broker_execution_id="exec-recon-a2",
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
        finality_proof_recorded=True,
        source_ref="evidence-egress-result",
    )
    witness_order = WitnessOrder(
        attempt_id=_ATTEMPT_ID,
        broker_execution_id="exec-recon-a2",
        quantity=Decimal("10"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
    )

    class _FakeRclReader:
        def reservation_state(self, _reservation_id: str) -> CapacityState:
            return CapacityState.POSITION_CONSUMED

        def reservation_last_seq(self, _reservation_id: str) -> int | None:
            return None

        def all_reservations(self) -> dict[str, CapacityState]:
            return {}

        def instrument_state(self, _key: object) -> CapacityState | None:
            return None

        def instrument_last_seq(self, _key: object) -> int | None:
            return None

    class _FakeEvidenceReader:
        def receipts(
            self, _scope: WitnessScope
        ) -> tuple[EgressReceiptObservation, ...]:
            return (receipt,)

    class _IndependentWitness:
        def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
            return WitnessSnapshot(
                observed_at_generation=1,
                orders=(witness_order,),
                provenance="independent-broker-double",
                independent_of_evidence_store=True,
            )

    service = ReconciliationService(
        rcl_reader=_FakeRclReader(),
        evidence_reader=_FakeEvidenceReader(),
        witness=_IndependentWitness(),
    )
    report = service.reconcile(
        WitnessScope(account=key.account, attempt_ids=(_ATTEMPT_ID,)),
        freshness=FreshnessMarker(
            fresh_within_horizon=True,
            time_confidence_held=True,
            time_generation=1,
            anchored_generation=1,
        ),
    )

    assert report.permits_capacity_release is True
    assert report.permits_rearm is True


def test_b_evidence_store_unreachable_holds_unavailable(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    attempt = _one_possibly_live_attempt(inbox, evidence_store)
    _record_corroborating_evidence(evidence_store, event_id=attempt.event_id)
    _open_the_scope_reservation(rcl_log)
    key = fx.instrument_key()
    evidence_store.close()  # every downstream read now fails

    reconciliation = reconcile_possibly_live_attempts(
        (attempt,),
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        time_service=_TrustedTimeService(),
        account=key.account,
        instrument=key.instrument,
    )

    assert reconciliation[attempt.event_id] == ReconciliationOutcome(
        cleared=False, reason=RECON_UNAVAILABLE
    )

    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            possibly_live_attempts=(attempt,),
            possibly_live_reconciliation=reconciliation,
        )
    )
    assert verdict.ready is False


def test_c_never_started_time_service_fails_closed_even_when_corroborated(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """The SAME fully-corroborated setup as (a), but the time service never started -- so
    ``_build_freshness_marker`` falls back to the kernel's all-``None`` ``FreshnessMarker()``
    default, and every field fails closed regardless of corroboration strength."""
    attempt = _one_possibly_live_attempt(inbox, evidence_store)
    _record_corroborating_evidence(evidence_store, event_id=attempt.event_id)
    _open_the_scope_reservation(rcl_log)
    key = fx.instrument_key()

    reconciliation = reconcile_possibly_live_attempts(
        (attempt,),
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        time_service=_NeverStartedTimeService(),
        account=key.account,
        instrument=key.instrument,
    )

    outcome = reconciliation[attempt.event_id]
    assert outcome.cleared is False
    assert outcome.reason != RECONCILED_MATCHED
    assert outcome.reason != NO_ATTEMPT_ID

    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            possibly_live_attempts=(attempt,),
            possibly_live_reconciliation=reconciliation,
        )
    )
    assert verdict.ready is False


class _StubService:
    """A minimal stand-in exposing only ``.reconcile`` — used by the (d) mutation guard to
    inject a HAND-PICKED report at the ``_reconcile_one`` level, bypassing the real kernel-backed
    judgement entirely, so the test asserts on ``_reconcile_one``'s own conjunction rather than
    on whether the kernel predicates can be coaxed into a partial report."""

    def __init__(self, report: ReconciliationReport) -> None:
        self._report = report

    def reconcile(
        self, _scope: WitnessScope, *, freshness: FreshnessMarker
    ) -> ReconciliationReport:
        del freshness  # unused -- this stub always returns the canned report
        return self._report


def test_d_mutation_guard_requires_both_capacity_release_and_rearm(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A report granting ``permits_capacity_release`` alone (never ``permits_rearm``), for an
    attempt classified ``MATCHED``, must NOT clear the attempt -- a mutation that changed
    ``_reconcile_one``'s own ``and`` to accept either flag alone would turn this red."""
    from tos_runtime.recon.service import AttemptClassification

    partial_report = ReconciliationReport(
        field_confidences=(),
        classifications=(
            AttemptClassification(
                attempt_id=_ATTEMPT_ID, classification=ReconciliationClass.MATCHED
            ),
        ),
        permits_capacity_release=True,
        permits_rearm=False,
        reason="partial-report-for-mutation-guard",
    )
    _record_corroborating_evidence(evidence_store, event_id="event-mutation-guard")
    key = fx.instrument_key()

    outcome = _reconcile_one(
        event_id="event-mutation-guard",
        service=_StubService(partial_report),  # type: ignore[arg-type]
        evidence_store=evidence_store,
        account=key.account,
        instrument_key=key,
        freshness=FreshnessMarker(
            fresh_within_horizon=True,
            time_confidence_held=True,
            time_generation=1,
            anchored_generation=1,
        ),
    )

    assert outcome == ReconciliationOutcome(
        cleared=False, reason="partial-report-for-mutation-guard"
    )
