"""Hermetic tests for :mod:`tos_runtime.posttrade.release_consumer` (TOS Phase 5 W2-R; plan §10"""

from __future__ import annotations

import sys
from decimal import Decimal
from types import SimpleNamespace

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind, StageOutcome
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.recon import FreshnessMarker
from tos.time.domains import HealthState
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import FinalityResult, SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import (
    CAPACITY_RELEASE_HELD_KIND,
    CAPACITY_RELEASE_INTENT_KIND,
    RELEASE_PROOF_OVERDUE_KIND,
    FinalityConsumerTimeReader,
    FinalityReleaseConsumer,
    ReleaseHoldReason,
    entry_release_command_id,
    release_command_id,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import (
    permit_reservation_id,
    scope_reservation_id,
)
from tos_runtime.rcl.reservation_lookup import reservation_id_for_attempt
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import (
    BrokerWitness,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService
from tos_runtime.risk.ledger_stages import verdict_for_scope
from tos_runtime.riskstate.close_bound import DurableEntryCloseBoundReader

from .conftest import MONOTONIC_BASE_MS as _MONOTONIC_BASE_MS
from .conftest import Rig

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = "acct-relc"
_INSTRUMENT = "101S06"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_ATTEMPT_ID = "attempt-relc-1"
_RESERVATION_ID = scope_reservation_id(_ACCOUNT, _INSTRUMENT)
_MAIN_PERMIT = "afg-permit-relc-main"


class _TrustedTimeService:
    """A minimal ``TrustworthyTimeService`` double reporting a genuinely TRUSTED snapshot —"""

    health_state: HealthState = HealthState.TRUSTED

    def current_snapshot(self) -> SimpleNamespace:
        identity = SimpleNamespace(tts_generation=1)
        return SimpleNamespace(
            health_state=HealthState.TRUSTED, time_continuity_identity=identity
        )


class _UntrustedTimeService:
    """A ``TrustworthyTimeService`` double reporting a NOT-``TRUSTED`` health state — for the H2"""

    health_state: HealthState = HealthState.UNTRUSTED

    def current_snapshot(self) -> SimpleNamespace:
        identity = SimpleNamespace(tts_generation=None)
        return SimpleNamespace(
            health_state=HealthState.UNTRUSTED, time_continuity_identity=identity
        )


def _finality_config(*, release_proof_wait_ms: int = 60_000) -> FinalityConfig:
    return FinalityConfig(
        currency="KRW",
        value_date="2026-09-09",
        source_revision="relc-test-rev-1",
        proof_recipe_id="relc-test-recipe-1",
        release_proof_wait_ms=release_proof_wait_ms,
    )


def _producer() -> SyntheticFinalityProducer:
    return SyntheticFinalityProducer(config=_finality_config(), scheme=SCHEME)


@pytest.fixture(autouse=True)
def _attempt_permit_join(evidence_store: SqliteEvidenceStore) -> None:
    """This attempt's durable ``event_id`` join, which every real flow writes."""
    _record_join(evidence_store, attempt_id=_ATTEMPT_ID, permit_identity=_MAIN_PERMIT)


def _open_reservation(
    rcl_log: SqliteCommitLog,
    *,
    to_state: CapacityState = CapacityState.POTENTIALLY_LIVE,
    scope: ReservationScope | None = None,
    command: str = "relc-setup",
) -> None:
    """Commit a genuinely open RCL reservation under this module's own scope-level id."""
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rcl_log.acquire_epoch(identity)
    rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=_RESERVATION_ID,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=to_state,
            scope=(
                scope
                if scope is not None
                else ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT)
            ),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id=f"cmd-{command}",
        command_digest=f"dig-{command}",
        expected_seq=-1,
    )


def _commit_transition(
    rcl_log: SqliteCommitLog,
    *,
    epoch: int,
    from_state: CapacityState,
    to_state: CapacityState,
    command_id: str,
) -> None:
    """Commit one more reservation-lifecycle transition on the ALREADY-open ``_RESERVATION_ID``"""
    current_seq = SqliteReservationProjectionReader(rcl_log).reservation_last_seq(
        _RESERVATION_ID
    )
    expected_seq = -1 if current_seq is None else current_seq
    rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=_RESERVATION_ID,
            writer_epoch=epoch,
            from_state=from_state,
            to_state=to_state,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id=command_id,
        command_digest=command_id,
        expected_seq=expected_seq,
    )


def _record_full_fill_receipt(
    evidence_store: SqliteEvidenceStore, *, finality_proof_recorded: bool
) -> None:
    payload: dict[str, object] = {
        "attempt_id": _ATTEMPT_ID,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "FULL_FILL",
        "filled_quantity": "10",
        "remaining_quantity": "0",
        "broker_execution_id": "exec-relc-1",
    }
    evidence_store.append(
        payload, kind="EGRESS_RESULT_CONSUMED", record_class="EGRESS_RESULT_CONSUMED"
    )
    if finality_proof_recorded:
        evidence_store.append(
            {"idempotency_key": f"synthetic-fqp-proof:{_ATTEMPT_ID}"},
            kind="POSTTRADE_FINALITY_PROOF",
            record_class="POSTTRADE_FINALITY_PROOF",
        )


def _record_non_execution_receipt(
    evidence_store: SqliteEvidenceStore, *, kind: str, finality_proof_recorded: bool
) -> None:
    payload: dict[str, object] = {
        "attempt_id": _ATTEMPT_ID,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": kind,
        "broker_execution_id": "exec-relc-2",
    }
    evidence_store.append(
        payload, kind="EGRESS_RESULT_CONSUMED", record_class="EGRESS_RESULT_CONSUMED"
    )
    if finality_proof_recorded:
        evidence_store.append(
            {"idempotency_key": f"synthetic-fqp-proof:{_ATTEMPT_ID}"},
            kind="POSTTRADE_FINALITY_PROOF",
            record_class="POSTTRADE_FINALITY_PROOF",
        )


class _IndependentFullFillWitness:
    """A genuinely independent (``independent_of_evidence_store=True``) broker witness double"""

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                WitnessOrder(
                    attempt_id=_ATTEMPT_ID,
                    broker_execution_id="exec-relc-1",
                    quantity=Decimal("10"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
            ),
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )


class _IndependentCancelledWitness:
    """A genuinely independent witness reporting a ``CANCELLED`` order."""

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                WitnessOrder(
                    attempt_id=_ATTEMPT_ID,
                    broker_execution_id="exec-relc-2",
                    quantity=Decimal("0"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.CANCELLED,
                ),
            ),
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )


def _consumer(
    rig: Rig,
    *,
    witness: BrokerWitness | None = None,
    release_proof_wait_ms: int = 60_000,
    time_service: FinalityConsumerTimeReader | None = None,
) -> FinalityReleaseConsumer:
    """This suite's consumer; ``witness`` defaults to the independent FULL_FILL double."""
    recon_service = ReconciliationService(
        rcl_reader=SqliteReservationProjectionReader(rig.rcl_log),
        evidence_reader=SqliteEvidenceReceiptReader(rig.evidence_store),
        witness=witness if witness is not None else _IndependentFullFillWitness(),
        reservation_id_for_attempt=lambda _attempt_id: _RESERVATION_ID,
    )
    return FinalityReleaseConsumer(
        rcl_log=rig.rcl_log,
        projection=SqliteReservationProjectionReader(rig.rcl_log),
        evidence_store=rig.evidence_store,
        inbox=rig.inbox,
        recon_service=recon_service,
        time_service=(
            time_service if time_service is not None else _TrustedTimeService()
        ),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=rig.monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=release_proof_wait_ms,
    )


def _held_rows(evidence_store: SqliteEvidenceStore) -> list[dict]:
    import json

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (CAPACITY_RELEASE_HELD_KIND,),
    ).fetchall()
    return [json.loads(payload_json)["payload"] for (payload_json,) in rows]


def _held_rows_after_entry_pending_link(
    evidence_store: SqliteEvidenceStore,
) -> list[dict]:
    rows = _held_rows(evidence_store)
    pending = [row for row in rows if row["reason"] == "ENTRY_DISCHARGE_PENDING"]
    assert len(pending) == 1
    assert pending[0]["attempt_id"] == _CLOSE_ATTEMPT
    assert pending[0]["reservation_id"] == _entry_reservation_id()
    return [row for row in rows if row["reason"] != "ENTRY_DISCHARGE_PENDING"]


def _reservation_state(rcl_log: SqliteCommitLog) -> CapacityState | None:
    for reservation_id, state, _seq, _scope in rcl_log.reservation_rows():
        if reservation_id == _RESERVATION_ID:
            return state
    return None


def _count_kind(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    """How many durable rows of ``kind`` the store holds."""
    (count,) = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    return int(count)


def _kind_seq(evidence_store: SqliteEvidenceStore, kind: str) -> list[int]:
    rows = evidence_store.connection.execute(
        "SELECT seq FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    return [seq for (seq,) in rows]


def _full_fill_payload() -> EgressResultPayload:
    """This suite's one FULL_FILL egress result — 10 filled, nothing outstanding."""
    return EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )


def _append_obligation(
    evidence_store: SqliteEvidenceStore, produced: FinalityResult
) -> None:
    """Durably record one produced obligation record AND its finality proof."""
    evidence_store.append(
        produced.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    evidence_store.append(
        produced.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def _seed_full_fill_obligation(
    evidence_store: SqliteEvidenceStore,
) -> tuple[EgressResultPayload, FinalityResult]:
    """Produce this suite's FULL_FILL obligation and record it with its proof."""
    payload = _full_fill_payload()
    produced = _producer().produce(payload)
    assert produced is not None
    _append_obligation(evidence_store, produced)
    return payload, produced


def _payload(kind: EgressResultKind) -> EgressResultPayload:
    """This attempt's egress result of ``kind``, with no fill quantities attached."""
    return EgressResultPayload(instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=kind)


def _arrange_full_fill(rig: Rig) -> tuple[EgressResultPayload, FinalityResult]:
    """A durable FULL_FILL obligation, its witness and receipt, over an open reservation."""
    payload, produced = _seed_full_fill_obligation(rig.evidence_store)
    rig.inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(rig.evidence_store, finality_proof_recorded=False)
    _open_reservation(rig.rcl_log)
    return payload, produced


def test_release_consumer_imports_cleanly_after_a_cold_cache_eviction() -> None:
    """TOS Phase 5 W2-R re-review finding NEW-1 (2026-09-10): ``import"""
    evicted_prefixes = ("tos_runtime.engine",)
    to_evict = [
        name
        for name in list(sys.modules)
        if name == "tos_runtime.posttrade.release_consumer"
        or any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in evicted_prefixes
        )
    ]
    saved = {name: sys.modules.pop(name) for name in to_evict}
    try:
        import tos_runtime.posttrade.release_consumer  # noqa: F401
    finally:
        for name, module in saved.items():
            sys.modules[name] = module
        setattr(  # noqa: B010
            sys.modules["tos_runtime"], "engine", saved["tos_runtime.engine"]
        )


def test_full_fill_with_independent_witness_releases_to_position_consumed(
    rig: Rig,
) -> None:
    payload, produced = _arrange_full_fill(rig)

    consumer = _consumer(rig)
    outcome = consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POSITION_CONSUMED
    assert _held_rows(rig.evidence_store) == []
    intent_seqs = _kind_seq(rig.evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    rcl_seqs = _kind_seq(rig.evidence_store, "RCL_RESERVATION_TRANSITION")
    assert len(intent_seqs) == 1
    assert len(rcl_seqs) >= 1
    assert intent_seqs[0] < rcl_seqs[-1]

    assert outcome.released is True
    assert outcome.attempt_id == _ATTEMPT_ID
    assert outcome.proof_digest == produced.proof.proof_id
    assert outcome.evidence_seq == intent_seqs[0]
    assert outcome.resolution_generation == 0


def test_full_fill_release_outcome_feeds_a_real_kernel_ledger_release(
    rig: Rig,
) -> None:
    """The full kernel round #3 §2 decision 5 / W2-K chain, end to end at the unit level (the"""
    from tos.engine.state import FinalityProofRef, ProvisionalReservationLedger

    payload, produced = _arrange_full_fill(rig)

    consumer = _consumer(rig)
    outcome = consumer.consume(payload)
    assert outcome.released is True

    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    ledger.commit_unbound(_KEY, proposal_id="proposal-relc-1")
    ledger.bind_attempt(_KEY, attempt_id=_ATTEMPT_ID)
    ledger.mark_potentially_live(_KEY)
    application = ledger.apply_egress_result(payload)
    assert application.applied is True
    outstanding = ledger.outstanding(_KEY)
    assert outstanding is not None
    assert outstanding.capacity_state is CapacityState.POSITION_CONSUMED

    assert outcome.proof_digest is not None
    assert outcome.evidence_seq is not None
    assert outcome.resolution_generation is not None
    ref = FinalityProofRef(
        attempt_id=outcome.attempt_id,
        proof_digest=outcome.proof_digest,
        evidence_seq=outcome.evidence_seq,
        resolution_generation=outcome.resolution_generation,
    )
    assert ledger.release(ref) is True
    assert ledger.outstanding(_KEY) is None
    assert ledger.admits_new_exposure(_KEY) is True


def test_full_fill_without_witness_holds(
    rig: Rig,
) -> None:
    """Gate 1: a durable witness that is not exactly ``True`` (e.g. never written, mirroring a"""
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    _record_full_fill_receipt(rig.evidence_store, finality_proof_recorded=True)
    _open_reservation(rig.rcl_log)

    consumer = _consumer(rig)
    outcome = consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NO_WITNESS.value
    assert outcome.released is False
    assert outcome.proof_digest is None
    assert outcome.evidence_seq is None
    assert outcome.resolution_generation is None


def test_report_not_permitting_capacity_release_holds_even_with_witness_and_proof(
    rig: Rig,
) -> None:
    """A ``ReconciliationService`` whose report never permits capacity release (fake PORTS"""
    payload, produced = _seed_full_fill_obligation(rig.evidence_store)
    rig.inbox.record_finality_witness(_ATTEMPT_ID, True)
    _open_reservation(rig.rcl_log)

    consumer = _consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    assert _kind_seq(rig.evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []


def test_full_fill_with_non_independent_witness_holds(
    rig: Rig,
) -> None:
    from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness

    payload, produced = _arrange_full_fill(rig)

    consumer = _consumer(
        rig,
        witness=SyntheticLedgerWitness(rig.evidence_store),
    )
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value


class _StubPermittingReconciliationService:
    """A minimal ``ReconciliationService``-shaped stand-in returning a canned, permitting"""

    def reconcile(self, _scope: WitnessScope, *, freshness: FreshnessMarker) -> object:
        del freshness
        from tos_runtime.recon.service import (
            AttemptClassification,
            ReconciliationReport,
        )

        return ReconciliationReport(
            field_confidences=(),
            classifications=(
                AttemptClassification(
                    attempt_id=_ATTEMPT_ID,
                    classification=ReconciliationClass.MATCHED,
                ),
            ),
            permits_capacity_release=True,
            permits_rearm=True,
            reason=None,
        )


def _non_execution_consumer(
    rig: Rig,
    *,
    recon_service: object | None = None,
) -> FinalityReleaseConsumer:
    """The consumer with gate 3 STUBBED to permit — the same isolation"""
    stub = (
        recon_service
        if recon_service is not None
        else _StubPermittingReconciliationService()
    )
    return FinalityReleaseConsumer(
        rcl_log=rig.rcl_log,
        projection=SqliteReservationProjectionReader(rig.rcl_log),
        evidence_store=rig.evidence_store,
        inbox=rig.inbox,
        recon_service=stub,  # type: ignore[arg-type]
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=rig.monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )


def test_cancel_ack_releases_when_reconciliation_permits_it(
    rig: Rig,
) -> None:
    """Pins the consumer's OWN release wiring for the non-execution path: given a permitting"""
    payload = _payload(EgressResultKind.CANCEL_ACK)
    _open_reservation(rig.rcl_log)

    consumer = _non_execution_consumer(rig)
    outcome = consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.RELEASED
    assert _held_rows(rig.evidence_store) == []
    proof_rows = _count_kind(rig.evidence_store, "POSTTRADE_FINALITY_PROOF")
    assert proof_rows == 1
    obligation_rows = _count_kind(rig.evidence_store, "ECONOMIC_OBLIGATION")
    assert obligation_rows == 1
    intent_seqs = _kind_seq(rig.evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    rcl_seqs = _kind_seq(rig.evidence_store, "RCL_RESERVATION_TRANSITION")
    assert len(intent_seqs) == 1
    assert intent_seqs[0] < rcl_seqs[-1]

    assert outcome.released is True
    assert outcome.attempt_id == _ATTEMPT_ID
    assert outcome.evidence_seq == intent_seqs[0]
    assert outcome.resolution_generation == 0
    assert outcome.proof_digest is not None


def test_cancel_ack_never_releases_under_the_current_reconciliation_model(
    rig: Rig,
) -> None:
    """The honest, undoctored path (module docstring): a fresh ``CANCEL_ACK``, a fully"""
    payload = _payload(EgressResultKind.CANCEL_ACK)
    _record_non_execution_receipt(
        rig.evidence_store, kind="CANCEL_ACK", finality_proof_recorded=False
    )
    _open_reservation(rig.rcl_log)

    consumer = _consumer(
        rig,
        witness=_IndependentCancelledWitness(),
    )
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    proof_rows = _count_kind(rig.evidence_store, "POSTTRADE_FINALITY_PROOF")
    assert proof_rows == 0


@pytest.mark.parametrize(
    "kind,filled,remaining",
    [
        (EgressResultKind.ACK, None, None),
        (EgressResultKind.PARTIAL_FILL, "5", "5"),
        (EgressResultKind.UNKNOWN, None, None),
        (EgressResultKind.TIMEOUT, None, None),
    ],
)
def test_non_release_eligible_kinds_record_nothing_release_related(
    rig: Rig,
    kind: EgressResultKind,
    filled: str | None,
    remaining: str | None,
) -> None:
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=kind,
        filled_quantity=None if filled is None else Decimal(filled),
        remaining_quantity=None if remaining is None else Decimal(remaining),
    )
    _open_reservation(rig.rcl_log)

    consumer = _consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    assert _held_rows(rig.evidence_store) == []
    assert _kind_seq(rig.evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []


def test_obligation_expiry_first_observation_only_records_wait_start(
    rig: Rig,
) -> None:
    payload = _payload(EgressResultKind.ACK)
    _open_reservation(rig.rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rig,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)

    overdue = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert overdue == 0
    assert len(consumer._wait_start_ms) == 1  # noqa: SLF001
    ((_stored_key, stored_first_observed_ms),) = (
        consumer._wait_start_ms.items()
    )  # noqa: SLF001
    assert stored_first_observed_ms == _MONOTONIC_BASE_MS
    wait_start_rows = _count_kind(rig.evidence_store, "RELEASE_PROOF_WAIT_START")
    assert wait_start_rows == 0


def test_obligation_expiry_records_overdue_once_past_the_bound(
    rig: Rig,
) -> None:
    payload = _payload(EgressResultKind.ACK)
    _open_reservation(rig.rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rig,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)

    rig.monotonic_source.advance(1_001)
    consumer.consume(payload)

    overdue = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert overdue == 1

    consumer.consume(payload)
    overdue_again = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert overdue_again == 1


def test_obligation_expiry_never_fires_for_a_non_overdue_eligible_state(
    rig: Rig,
) -> None:
    payload = _payload(EgressResultKind.ACK)
    _open_reservation(rig.rcl_log, to_state=CapacityState.POTENTIALLY_LIVE)

    consumer = _consumer(
        rig,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)
    rig.monotonic_source.advance(5_000)
    consumer.consume(payload)

    for kind in (RELEASE_PROOF_OVERDUE_KIND, "RELEASE_PROOF_WAIT_START"):
        count = _count_kind(rig.evidence_store, kind)
        assert count == 0


def test_obligation_expiry_evaluates_nothing_when_time_is_not_trusted(
    rig: Rig,
) -> None:
    """Independent-review finding H2: with ``time_service.health_state`` not ``TRUSTED``,"""
    payload = _payload(EgressResultKind.ACK)
    _open_reservation(rig.rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rig,
        release_proof_wait_ms=1_000,
        time_service=_UntrustedTimeService(),
    )
    consumer.consume(payload)
    rig.monotonic_source.advance(5_000)
    consumer.consume(payload)

    assert consumer._wait_start_ms == {}  # noqa: SLF001
    for kind in (RELEASE_PROOF_OVERDUE_KIND, "RELEASE_PROOF_WAIT_START"):
        count = _count_kind(rig.evidence_store, kind)
        assert count == 0


def test_obligation_expiry_records_overdue_again_for_a_new_occupancy(
    rig: Rig,
) -> None:
    """Independent-review finding M1: leaving the overdue-eligible state and re-entering it"""
    payload = _payload(EgressResultKind.ACK)
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rig.rcl_log.acquire_epoch(identity)
    rig.rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=_RESERVATION_ID,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.QUARANTINED_UNKNOWN,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-relc-occupancy-1",
        command_digest="dig-relc-occupancy-1",
        expected_seq=-1,
    )

    consumer = _consumer(
        rig,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)
    rig.monotonic_source.advance(1_001)
    consumer.consume(payload)

    first_overdue = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert first_overdue == 1

    _commit_transition(
        rig.rcl_log,
        epoch=epoch,
        from_state=CapacityState.QUARANTINED_UNKNOWN,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-exit-occupancy-1",
    )
    _commit_transition(
        rig.rcl_log,
        epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.QUARANTINED_UNKNOWN,
        command_id="cmd-relc-enter-occupancy-2",
    )

    consumer.consume(payload)
    still_one = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert still_one == 1

    rig.monotonic_source.advance(1_001)
    consumer.consume(payload)

    second_overdue = _count_kind(rig.evidence_store, RELEASE_PROOF_OVERDUE_KIND)
    assert second_overdue == 2


def test_gate4_holds_when_the_rcl_persisted_scope_diverges_from_the_proof(
    rig: Rig,
) -> None:
    """Independent-review finding H1: ``target_leg_scope``'s account now comes from the RCL"""
    payload, produced = _seed_full_fill_obligation(rig.evidence_store)
    rig.inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(rig.evidence_store, finality_proof_recorded=False)
    _open_reservation(
        rig.rcl_log,
        scope=ReservationScope(account="divergent-account", instrument=_INSTRUMENT),
        command="relc-setup-divergent",
    )

    consumer = _consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_TRANSFERABLE.value


def test_gate4_holds_when_a_newer_obligation_generation_supersedes_the_proof(
    rig: Rig,
) -> None:
    """Independent-review finding H1: ``active_generation`` now comes from the NEWEST"""
    payload, produced = _arrange_full_fill(rig)
    rig.evidence_store.append(
        {
            "account_scope": _ACCOUNT,
            "instrument_identity": _INSTRUMENT,
            "obligation_generation": 1,
        },
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )

    consumer = _consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_CURRENT.value


def test_non_execution_path_genuinely_reloads_rather_than_trusting_produced_proof(
    rig: Rig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent-review finding M3 (mutation (d), direct pin): forces"""
    monkeypatch.setattr(
        FinalityReleaseConsumer,
        "_reload_proof",
        lambda *_args, **_kwargs: None,
    )
    payload = _payload(EgressResultKind.CANCEL_ACK)
    _open_reservation(rig.rcl_log)

    consumer = _non_execution_consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_RELOADED.value
    proof_rows = _count_kind(rig.evidence_store, "POSTTRADE_FINALITY_PROOF")
    assert proof_rows == 1


def test_non_execution_path_holds_when_gate4_diverges_too(
    rig: Rig,
) -> None:
    """Independent-review finding M3 (routing through gate 4): the non-execution destination now"""
    payload = _payload(EgressResultKind.CANCEL_ACK)
    _open_reservation(
        rig.rcl_log,
        scope=ReservationScope(account="divergent-account", instrument=_INSTRUMENT),
        command="relc-setup-divergent",
    )

    consumer = _non_execution_consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_TRANSFERABLE.value
    proof_rows = _count_kind(rig.evidence_store, "POSTTRADE_FINALITY_PROOF")
    assert proof_rows == 1


def test_non_execution_proof_never_shadows_an_earlier_full_fill_proof_for_the_same_attempt(
    rig: Rig,
) -> None:
    """Independent-review finding M4: a ``FULL_FILL`` proof recorded for an attempt, followed by"""
    fill_payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    producer = _producer()
    fill_result = producer.produce(fill_payload)
    assert fill_result is not None
    rig.evidence_store.append(
        fill_result.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    rig.evidence_store.append(
        fill_result.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )

    non_exec_payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.CANCEL_ACK
    )
    non_exec_result = producer.produce_non_execution(non_exec_payload)
    assert non_exec_result is not None
    rig.evidence_store.append(
        non_exec_result.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    rig.evidence_store.append(
        non_exec_result.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )

    from tos_runtime.posttrade.finality import (
        FULL_FILL_OBLIGATION_ID_PREFIX,
        FULL_FILL_PROOF_ID_PREFIX,
        NON_EXECUTION_OBLIGATION_ID_PREFIX,
        NON_EXECUTION_PROOF_ID_PREFIX,
    )

    _open_reservation(rig.rcl_log)
    consumer = _consumer(rig)

    reloaded_fill_proof = consumer._reload_proof(  # noqa: SLF001
        _ATTEMPT_ID, id_prefix=FULL_FILL_PROOF_ID_PREFIX
    )
    reloaded_nonexec_proof = consumer._reload_proof(  # noqa: SLF001
        _ATTEMPT_ID, id_prefix=NON_EXECUTION_PROOF_ID_PREFIX
    )
    assert reloaded_fill_proof is not None
    assert reloaded_nonexec_proof is not None
    assert reloaded_fill_proof.amount == Decimal("10")
    assert reloaded_nonexec_proof.amount == Decimal("0")
    assert reloaded_fill_proof.proof_id != reloaded_nonexec_proof.proof_id

    reloaded_fill_obligation = consumer._reload_obligation(  # noqa: SLF001
        _ATTEMPT_ID, id_prefix=FULL_FILL_OBLIGATION_ID_PREFIX
    )
    reloaded_nonexec_obligation = consumer._reload_obligation(  # noqa: SLF001
        _ATTEMPT_ID, id_prefix=NON_EXECUTION_OBLIGATION_ID_PREFIX
    )
    assert reloaded_fill_obligation is not None
    assert reloaded_nonexec_obligation is not None
    assert (
        reloaded_fill_obligation.obligation_id
        != reloaded_nonexec_obligation.obligation_id
    )


def test_matched_conjunct_holds_when_no_classification_covers_the_attempt(
    rig: Rig,
) -> None:
    """Independent-review finding M7 (mutation (m)): a report that permits capacity release but"""

    class _StubPermittingButUnclassifiedReport:
        def reconcile(
            self, _scope: WitnessScope, *, freshness: FreshnessMarker
        ) -> object:
            del freshness
            from tos_runtime.recon.service import ReconciliationReport

            return ReconciliationReport(
                field_confidences=(),
                classifications=(),
                permits_capacity_release=True,
                permits_rearm=True,
                reason=None,
            )

    payload = _payload(EgressResultKind.CANCEL_ACK)
    _open_reservation(rig.rcl_log)

    consumer = _non_execution_consumer(
        rig,
        recon_service=_StubPermittingButUnclassifiedReport(),
    )
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(rig.evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    proof_rows = _count_kind(rig.evidence_store, "POSTTRADE_FINALITY_PROOF")
    assert proof_rows == 0


def test_release_reads_from_state_dynamically_not_a_hardcoded_constant(
    rig: Rig,
) -> None:
    """LOW L1: opens the reservation directly at ``ATTEMPT_BOUND`` (never touching"""
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rig.rcl_log.acquire_epoch(identity)
    rig.rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=_RESERVATION_ID,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.ATTEMPT_BOUND,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-relc-attempt-bound",
        command_digest="dig-relc-attempt-bound",
        expected_seq=-1,
    )
    assert _reservation_state(rig.rcl_log) is CapacityState.ATTEMPT_BOUND

    payload, produced = _seed_full_fill_obligation(rig.evidence_store)
    rig.inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(rig.evidence_store, finality_proof_recorded=False)

    consumer = _consumer(rig)
    consumer.consume(payload)

    assert _reservation_state(rig.rcl_log) is CapacityState.POSITION_CONSUMED
    assert _held_rows(rig.evidence_store) == []


_ENTRY_ATTEMPT = "attempt-relc-entry"
_CLOSE_ATTEMPT = "attempt-relc-close"
_ENTRY_PERMIT = "afg-permit-relc-entry"
_CLOSE_PERMIT = "afg-permit-relc-close"
_ENTRY_QTY = Decimal("10")


def _entry_reservation_id() -> str:
    return permit_reservation_id(_ACCOUNT, _INSTRUMENT, _ENTRY_PERMIT)


def _close_reservation_id() -> str:
    return permit_reservation_id(_ACCOUNT, _INSTRUMENT, _CLOSE_PERMIT)


def _record_join(
    evidence_store: SqliteEvidenceStore, *, attempt_id: str, permit_identity: str
) -> None:
    """The two durable rows :mod:`tos_runtime.rcl.reservation_lookup` joins on ``event_id``."""
    event_id = f"evt-{attempt_id}"
    evidence_store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": event_id,
            "bound_identity": permit_identity,
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    evidence_store.append(
        {
            "kind": "ATTEMPT_REQUEST_CREATED",
            "event_id": event_id,
            "attempt_id": attempt_id,
        },
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )


def _commit_named_reservation(
    rcl_log: SqliteCommitLog,
    *,
    reservation_id: str,
    to_state: CapacityState,
    command_id: str,
) -> None:
    """Commit one reservation under ``reservation_id``, reading the tip fresh."""
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rcl_log.current_epoch() or rcl_log.acquire_epoch(identity)
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    witness = True if to_state is CapacityState.POSITION_CONSUMED else None
    cause = (
        TransitionCause.FINAL_QUANTITY_PROOF
        if witness is True
        else TransitionCause.STRONGLY_AUTHORIZED_COMMAND
    )
    command_type = (
        CommandType.RELEASE_RESERVATION if witness is True else CommandType.BIND_ATTEMPT
    )
    receipt = rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=to_state,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        cause,
        command_type=command_type,
        command_id=command_id,
        command_digest=command_id,
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=witness,
    )
    assert not isinstance(receipt, AppendRefusal), receipt


def _record_receipt(
    evidence_store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    filled: Decimal,
    remaining: Decimal,
    broker_execution_id: str,
    result_kind: str = "FULL_FILL",
) -> None:
    evidence_store.append(
        {
            "attempt_id": attempt_id,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": result_kind,
            "filled_quantity": format(filled, "f"),
            "remaining_quantity": format(remaining, "f"),
            "broker_execution_id": broker_execution_id,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )


class _CycleWitness:
    """An independent witness reporting BOTH the entry's and the close's orders as filled."""

    def __init__(
        self,
        *,
        positions: tuple[tuple[str, Decimal], ...] = (),
        positions_complete: bool = True,
        close_quantity: Decimal = _ENTRY_QTY,
    ) -> None:
        self._positions = positions
        self._positions_complete = positions_complete
        self._close_quantity = close_quantity

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                WitnessOrder(
                    attempt_id=_ENTRY_ATTEMPT,
                    broker_execution_id="exec-relc-entry",
                    quantity=_ENTRY_QTY,
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
                WitnessOrder(
                    attempt_id=_CLOSE_ATTEMPT,
                    broker_execution_id="exec-relc-close",
                    quantity=self._close_quantity,
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
            ),
            positions=self._positions,
            positions_complete=self._positions_complete,
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )


def _cycle_consumer(
    rig: Rig, *, witness: BrokerWitness | None = None
) -> FinalityReleaseConsumer:
    """Like :func:`_consumer`, but with the PRODUCTION reservation bridge (the durable permit"""
    projection = SqliteReservationProjectionReader(rig.rcl_log)
    recon_service = ReconciliationService(
        rcl_reader=projection,
        evidence_reader=SqliteEvidenceReceiptReader(rig.evidence_store),
        witness=witness if witness is not None else _CycleWitness(),
        reservation_id_for_attempt=lambda attempt_id: reservation_id_for_attempt(
            rig.evidence_store,
            projection,
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            attempt_id=attempt_id,
        ),
    )
    return FinalityReleaseConsumer(
        rcl_log=rig.rcl_log,
        projection=projection,
        evidence_store=rig.evidence_store,
        inbox=rig.inbox,
        recon_service=recon_service,
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=rig.monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )


def _close_payload(*, filled: Decimal = _ENTRY_QTY, remaining: Decimal = Decimal("0")):
    return EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_CLOSE_ATTEMPT,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=filled,
        remaining_quantity=remaining,
        broker_execution_id="exec-relc-close",
    )


def _arrange_close(
    rig: Rig,
    *,
    close_filled: Decimal = _ENTRY_QTY,
    close_remaining: Decimal = Decimal("0"),
    extra_consumed: bool = False,
):
    """A filled entry plus a close whose fill is being consumed — the #966 cycle's second half."""
    _record_join(
        rig.evidence_store, attempt_id=_ENTRY_ATTEMPT, permit_identity=_ENTRY_PERMIT
    )
    _record_join(
        rig.evidence_store, attempt_id=_CLOSE_ATTEMPT, permit_identity=_CLOSE_PERMIT
    )
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_entry_reservation_id(),
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-relc-entry",
    )
    if extra_consumed:
        _commit_named_reservation(
            rig.rcl_log,
            reservation_id=permit_reservation_id(
                _ACCOUNT, _INSTRUMENT, "afg-permit-relc-second"
            ),
            to_state=CapacityState.POSITION_CONSUMED,
            command_id="cmd-relc-second",
        )
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_close_reservation_id(),
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-close",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ENTRY_ATTEMPT,
        filled=_ENTRY_QTY,
        remaining=Decimal("0"),
        broker_execution_id="exec-relc-entry",
    )
    rig.evidence_store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{_ENTRY_ATTEMPT}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_CLOSE_ATTEMPT,
        filled=close_filled,
        remaining=close_remaining,
        broker_execution_id="exec-relc-close",
    )
    payload = _close_payload(filled=close_filled, remaining=close_remaining)
    produced = _producer().produce(payload)
    assert produced is not None
    _append_obligation(rig.evidence_store, produced)
    rig.inbox.record_finality_witness(_CLOSE_ATTEMPT, True)
    return payload


def _states(rcl_log: SqliteCommitLog) -> dict[str, CapacityState]:
    return {
        reservation_id: state
        for reservation_id, state, _seq, _scope in rcl_log.reservation_rows()
    }


def test_a_close_fill_releases_its_own_reservation_and_discharges_the_entry(
    rig: Rig,
) -> None:
    """Both reservations end ``RELEASED``: the close opened no position, and the entry's is"""
    payload = _arrange_close(rig)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(),
    )

    outcome = consumer.consume(payload)

    assert outcome.released is True
    states = _states(rig.rcl_log)
    assert states[_close_reservation_id()] is CapacityState.RELEASED
    assert states[_entry_reservation_id()] is CapacityState.RELEASED
    assert _held_rows_after_entry_pending_link(rig.evidence_store) == []
    destinations = [row["destination"] for row in _intent_rows(rig.evidence_store)]
    assert destinations == ["RELEASED", "RELEASED"]


def test_the_entry_discharge_uses_its_own_command_id(
    rig: Rig,
) -> None:
    """Two release transitions from ONE close attempt need two command ids."""
    payload = _arrange_close(rig)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(),
    )
    consumer.consume(payload)

    command_ids = [
        entry.command_id
        for entry in rig.rcl_log.replay()
        if entry.kind == CommandType.RELEASE_RESERVATION.value
    ]
    assert release_command_id(_CLOSE_ATTEMPT) in command_ids
    assert entry_release_command_id(_CLOSE_ATTEMPT) in command_ids
    assert len(set(command_ids)) == len(command_ids)


def test_a_broker_still_reporting_the_position_holds_the_entry(
    rig: Rig,
) -> None:
    """The close filled, but the witness still holds the instrument -> the entry stays."""
    payload = _arrange_close(rig)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(positions=((_INSTRUMENT, _ENTRY_QTY),)),
    )

    consumer.consume(payload)

    states = _states(rig.rcl_log)
    assert states[_close_reservation_id()] is CapacityState.RELEASED
    assert states[_entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    (held,) = _held_rows_after_entry_pending_link(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.BROKER_POSITION_NOT_FLAT.value
    assert held["reservation_id"] == _entry_reservation_id()


def test_a_partial_close_holds_the_entry(
    rig: Rig,
) -> None:
    """A close that discharges 4 of the entry's 10 units leaves the entry reservation held."""
    payload = _arrange_close(
        rig,
        close_filled=Decimal("4"),
        close_remaining=Decimal("0"),
    )
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(close_quantity=Decimal("4")),
    )

    consumer.consume(payload)

    states = _states(rig.rcl_log)
    assert states[_entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    (held,) = _held_rows_after_entry_pending_link(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.ENTRY_QUANTITY_UNPROVEN.value


def test_a_second_outstanding_reservation_holds_instead_of_guessing(
    rig: Rig,
) -> None:
    """A scope holding TWO consumed positions is not a shape this consumer acts on: it cannot"""
    payload = _arrange_close(rig, extra_consumed=True)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(),
    )

    outcome = consumer.consume(payload)

    assert outcome.released is False
    states = _states(rig.rcl_log)
    assert states[_close_reservation_id()] is CapacityState.POTENTIALLY_LIVE
    assert states[_entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.AMBIGUOUS_SCOPE_RESERVATIONS.value


def test_an_attempt_with_no_resolvable_reservation_holds(
    rig: Rig,
) -> None:
    """No join rows and no legacy row: the consumer records a hold and names no reservation."""
    rig.inbox.record_finality_witness(_CLOSE_ATTEMPT, True)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(),
    )

    outcome = consumer.consume(_close_payload())

    assert outcome.released is False
    assert _states(rig.rcl_log) == {}
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.NO_RESERVATION.value
    assert held["reservation_id"] is None


def _intent_rows(evidence_store: SqliteEvidenceStore) -> list[dict]:
    import json

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (CAPACITY_RELEASE_INTENT_KIND,),
    ).fetchall()
    return [json.loads(payload_json)["payload"] for (payload_json,) in rows]


def test_an_incomplete_holdings_observation_holds_the_entry(
    rig: Rig,
) -> None:
    """#966 review round 1 (Codex HIGH): empty positions are NOT proof of flatness."""
    payload = _arrange_close(rig)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(positions=(), positions_complete=False),
    )

    consumer.consume(payload)

    states = _states(rig.rcl_log)
    assert states[_close_reservation_id()] is CapacityState.RELEASED
    assert states[_entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    (held,) = _held_rows_after_entry_pending_link(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.BROKER_POSITION_NOT_FLAT.value
    assert held["reservation_id"] == _entry_reservation_id()


def test_a_complete_empty_holdings_observation_releases_the_entry(
    rig: Rig,
) -> None:
    """The positive control for the test above: the SAME empty tuple, declared complete."""
    payload = _arrange_close(rig)
    consumer = _cycle_consumer(
        rig,
        witness=_CycleWitness(positions=(), positions_complete=True),
    )

    consumer.consume(payload)

    assert _states(rig.rcl_log)[_entry_reservation_id()] is CapacityState.RELEASED
    assert _held_rows_after_entry_pending_link(rig.evidence_store) == []


_MAIN_PERMIT_RESERVATION_ID = permit_reservation_id(_ACCOUNT, _INSTRUMENT, _MAIN_PERMIT)


def _arrange_cancelled_partial_fill(
    rig: Rig,
    *,
    partial_filled: Decimal = Decimal("4"),
    partial_remaining: Decimal = Decimal("2"),
    cancel_filled: Decimal = Decimal("4"),
    cancel_remaining: Decimal = Decimal("2"),
) -> EgressResultPayload:
    """#980's input: an entry that filled part of its order, then had the rest cancelled."""
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_MAIN_PERMIT_RESERVATION_ID,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-partial-entry",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=partial_filled,
        remaining=partial_remaining,
        broker_execution_id="exec-relc-partial",
        result_kind="PARTIAL_FILL",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=cancel_filled,
        remaining=cancel_remaining,
        broker_execution_id="exec-relc-partial",
        result_kind="CANCEL_ACK",
    )
    return _payload(EgressResultKind.CANCEL_ACK)


def _obligation_quantities(evidence_store: SqliteEvidenceStore) -> list[Decimal]:
    import json

    rows = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        ("ECONOMIC_OBLIGATION",),
    ).fetchall()
    return [
        Decimal(str(json.loads(payload_json)["payload"]["quantity"]))
        for (payload_json,) in rows
    ]


def test_a_cancel_after_a_partial_fill_consumes_the_filled_quantity(
    rig: Rig,
) -> None:
    """#980: the entry filled 4 of 6 and the rest was cancelled — the 4 are a POSITION."""
    payload = _arrange_cancelled_partial_fill(rig)

    outcome = _non_execution_consumer(rig).consume(payload)

    assert outcome.released is True
    assert (
        _states(rig.rcl_log)[_MAIN_PERMIT_RESERVATION_ID]
        is CapacityState.POSITION_CONSUMED
    )
    assert _held_rows(rig.evidence_store) == []
    assert _obligation_quantities(rig.evidence_store) == [Decimal("4")]
    assert [row["destination"] for row in _intent_rows(rig.evidence_store)] == [
        CapacityState.POSITION_CONSUMED.value
    ]

    rows = SqliteReservationProjectionReader(rig.rcl_log).scope_reservations(_KEY)
    assert verdict_for_scope("CLOSE", rows).outcome is StageOutcome.ADMIT
    assert verdict_for_scope("OPEN", rows).outcome is StageOutcome.DENY


def test_the_cancelled_remainder_never_counts_toward_the_close_bound(
    rig: Rig,
) -> None:
    """#980: the durable bound a CLOSE is sized and fenced by is the 4 that filled, not the 6."""
    payload = _arrange_cancelled_partial_fill(rig)

    assert _non_execution_consumer(rig).consume(payload).released is True

    bound = DurableEntryCloseBoundReader(
        rcl_log=rig.rcl_log,
        evidence_store=rig.evidence_store,
        projection=SqliteReservationProjectionReader(rig.rcl_log),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    ).read()

    assert bound.proven is True
    assert bound.entry_reservation_id == _MAIN_PERMIT_RESERVATION_ID
    assert bound.entry_attempt_id == _ATTEMPT_ID
    assert bound.entry_quantity == Decimal("4")
    assert bound.prior_closed == Decimal("0")
    assert bound.remaining == Decimal("4")


def _close_bound(rig: Rig):
    return DurableEntryCloseBoundReader(
        rcl_log=rig.rcl_log,
        evidence_store=rig.evidence_store,
        projection=SqliteReservationProjectionReader(rig.rcl_log),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    ).read()


def test_a_late_fill_after_the_cancel_does_not_grow_the_close_bound(
    rig: Rig,
) -> None:
    """#1160 review MEDIUM-1: receipts that outgrow the issued proof deny the CLOSE."""
    payload = _arrange_cancelled_partial_fill(rig)
    assert _non_execution_consumer(rig).consume(payload).released is True
    assert _close_bound(rig).entry_quantity == Decimal("4")

    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=Decimal("5"),
        remaining=Decimal("1"),
        broker_execution_id="exec-relc-partial-late",
        result_kind="PARTIAL_FILL",
    )
    rig.evidence_store.append(
        {
            "attempt_id": _ATTEMPT_ID,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "CANCEL_ACK",
            "broker_execution_id": "exec-relc-partial-late",
        },
        kind="RESULT_UNMATCHED",
        record_class="RESULT_UNMATCHED",
    )

    bound = _close_bound(rig)
    assert bound.proven is False
    assert bound.entry_quantity is None
    assert bound.remaining is None


def test_the_close_bound_rests_on_the_recorded_obligation_quantity(
    rig: Rig,
) -> None:
    """#1160 review MEDIUM-1: receipts alone never size a CLOSE — the obligation must agree."""
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_MAIN_PERMIT_RESERVATION_ID,
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-relc-partial-consumed",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=Decimal("4"),
        remaining=Decimal("2"),
        broker_execution_id="exec-relc-partial",
        result_kind="PARTIAL_FILL",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=Decimal("4"),
        remaining=Decimal("2"),
        broker_execution_id="exec-relc-partial",
        result_kind="CANCEL_ACK",
    )
    rig.evidence_store.append(
        {"idempotency_key": f"synthetic-fqp-partial-proof:{_ATTEMPT_ID}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )
    rig.evidence_store.append(
        {
            "idempotency_key": f"synthetic-fqp-partial-obligation:{_ATTEMPT_ID}",
            "quantity": "5",
        },
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )

    assert _close_bound(rig).proven is False

    rig.evidence_store.append(
        {
            "idempotency_key": f"synthetic-fqp-partial-obligation:{_ATTEMPT_ID}",
            "quantity": "4",
        },
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )

    # SAFETY: two obligations disagreeing is still not a quantity — it must stay refused.
    assert _close_bound(rig).proven is False


class _PartialEntryCycleWitness:
    """Reports the partially filled entry and the CLOSE that discharges it, with a flat book."""

    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(
            observed_at_generation=1,
            orders=(
                WitnessOrder(
                    attempt_id=_ATTEMPT_ID,
                    broker_execution_id="exec-relc-partial",
                    quantity=Decimal("4"),
                    remaining=Decimal("2"),
                    state=WitnessOrderState.CANCELLED,
                ),
                WitnessOrder(
                    attempt_id=_CLOSE_ATTEMPT,
                    broker_execution_id="exec-relc-close",
                    quantity=Decimal("4"),
                    remaining=Decimal("0"),
                    state=WitnessOrderState.FILLED,
                ),
            ),
            positions=(),
            positions_complete=True,
            provenance="independent-broker-double",
            independent_of_evidence_store=True,
        )


def test_a_close_of_the_cancelled_partial_fill_discharges_the_entry(
    rig: Rig,
) -> None:
    """#1160 review LOW-2: the 4 that filled can be closed and the entry then reaches RELEASED."""
    entry_payload = _arrange_cancelled_partial_fill(rig)
    assert _non_execution_consumer(rig).consume(entry_payload).released is True

    _record_join(
        rig.evidence_store, attempt_id=_CLOSE_ATTEMPT, permit_identity=_CLOSE_PERMIT
    )
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_close_reservation_id(),
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-close",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_CLOSE_ATTEMPT,
        filled=Decimal("4"),
        remaining=Decimal("0"),
        broker_execution_id="exec-relc-close",
    )
    close_payload = _close_payload(filled=Decimal("4"), remaining=Decimal("0"))
    produced = _producer().produce(close_payload)
    assert produced is not None
    _append_obligation(rig.evidence_store, produced)
    rig.inbox.record_finality_witness(_CLOSE_ATTEMPT, True)

    outcome = _cycle_consumer(rig, witness=_PartialEntryCycleWitness()).consume(
        close_payload
    )

    assert outcome.released is True
    states = _states(rig.rcl_log)
    assert states[_close_reservation_id()] is CapacityState.RELEASED
    assert states[_MAIN_PERMIT_RESERVATION_ID] is CapacityState.RELEASED


def test_consuming_the_same_cancel_twice_never_releases_the_position(
    rig: Rig,
) -> None:
    """#980: a re-projected CANCEL_ACK re-runs the branch — the position is consumed once."""
    payload = _arrange_cancelled_partial_fill(rig)
    consumer = _non_execution_consumer(rig)

    assert consumer.consume(payload).released is True
    assert consumer.consume(payload).released is False

    assert (
        _states(rig.rcl_log)[_MAIN_PERMIT_RESERVATION_ID]
        is CapacityState.POSITION_CONSUMED
    )
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.RCL_TRANSITION_REFUSED.value


def test_a_cancelled_partial_fill_holds_when_the_receipts_disagree(
    rig: Rig,
) -> None:
    """review-973 M3 is unchanged where the quantity is unproven: contradictory receipts hold."""
    payload = _arrange_cancelled_partial_fill(
        rig, cancel_filled=Decimal("5"), cancel_remaining=Decimal("2")
    )

    outcome = _non_execution_consumer(rig).consume(payload)

    assert outcome.released is False
    assert (
        _states(rig.rcl_log)[_MAIN_PERMIT_RESERVATION_ID]
        is CapacityState.POTENTIALLY_LIVE
    )
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.FILLED_QUANTITY_STILL_HELD.value
    assert _obligation_quantities(rig.evidence_store) == []

    rows = SqliteReservationProjectionReader(rig.rcl_log).scope_reservations(_KEY)
    assert verdict_for_scope("OPEN", rows).outcome is StageOutcome.DENY
    assert verdict_for_scope("CLOSE", rows).outcome is StageOutcome.DENY


def test_a_cancelled_partial_fill_of_a_close_still_holds(
    rig: Rig,
) -> None:
    """#980 stops at the entry: a partially filled CLOSE would be a second position."""
    _record_join(
        rig.evidence_store, attempt_id=_ENTRY_ATTEMPT, permit_identity=_ENTRY_PERMIT
    )
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_entry_reservation_id(),
        to_state=CapacityState.POSITION_CONSUMED,
        command_id="cmd-relc-entry",
    )
    payload = _arrange_cancelled_partial_fill(rig)

    outcome = _non_execution_consumer(rig).consume(payload)

    assert outcome.released is False
    states = _states(rig.rcl_log)
    assert states[_MAIN_PERMIT_RESERVATION_ID] is CapacityState.POTENTIALLY_LIVE
    assert states[_entry_reservation_id()] is CapacityState.POSITION_CONSUMED
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.FILLED_QUANTITY_STILL_HELD.value

    rows = SqliteReservationProjectionReader(rig.rcl_log).scope_reservations(_KEY)
    assert verdict_for_scope("OPEN", rows).outcome is StageOutcome.DENY
    assert verdict_for_scope("CLOSE", rows).outcome is StageOutcome.DENY


def test_a_full_fill_receipt_with_a_remainder_still_holds(
    rig: Rig,
) -> None:
    """A FULL_FILL that declares a remainder is malformed — it proves no position quantity."""
    _commit_named_reservation(
        rig.rcl_log,
        reservation_id=_MAIN_PERMIT_RESERVATION_ID,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-partial-entry",
    )
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=Decimal("4"),
        remaining=Decimal("2"),
        broker_execution_id="exec-relc-partial",
    )

    outcome = _non_execution_consumer(rig).consume(
        _payload(EgressResultKind.CANCEL_ACK)
    )

    assert outcome.released is False
    assert (
        _states(rig.rcl_log)[_MAIN_PERMIT_RESERVATION_ID]
        is CapacityState.POTENTIALLY_LIVE
    )
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.FILLED_QUANTITY_STILL_HELD.value


def test_a_cancel_with_nothing_filled_still_releases(
    rig: Rig,
) -> None:
    """The positive control for M3: a receipt recording a zero fill releases as before."""
    _open_reservation(rig.rcl_log)
    _record_receipt(
        rig.evidence_store,
        attempt_id=_ATTEMPT_ID,
        filled=Decimal("0"),
        remaining=Decimal("6"),
        broker_execution_id="exec-relc-nofill",
    )
    payload = _payload(EgressResultKind.CANCEL_ACK)

    outcome = _non_execution_consumer(rig).consume(payload)

    assert outcome.released is True
    assert _reservation_state(rig.rcl_log) is CapacityState.RELEASED
    assert _held_rows(rig.evidence_store) == []


def test_an_attempt_with_no_flow_evidence_resolves_to_no_reservation(
    rig: Rig,
) -> None:
    """review-973 L1: a failed join must not fall through to the scope row."""
    _open_reservation(rig.rcl_log)
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id="attempt-with-no-evidence",
        kind=EgressResultKind.CANCEL_ACK,
    )

    outcome = _non_execution_consumer(rig).consume(payload)

    assert outcome.released is False
    assert _reservation_state(rig.rcl_log) is CapacityState.POTENTIALLY_LIVE
    (held,) = _held_rows(rig.evidence_store)
    assert held["reason"] == ReleaseHoldReason.NO_RESERVATION.value
    assert held["reservation_id"] is None


def test_post_trade_currentness_ignores_a_sibling_scope(
    rig: Rig,
) -> None:
    """review-973 L3: ``resv-A-I`` must not match ``resv-A-I2-<permit>``."""
    sibling = permit_reservation_id(_ACCOUNT, f"{_INSTRUMENT}2", "afg-permit-sibling")
    rig.evidence_store.append(
        {
            "attempt_id": "attempt-sibling",
            "reservation_id": sibling,
            "reason": ReleaseHoldReason.NOT_CORROBORATED.value,
            "detail": None,
        },
        kind=CAPACITY_RELEASE_HELD_KIND,
        record_class=CAPACITY_RELEASE_HELD_KIND,
    )
    consumer = _non_execution_consumer(rig)

    assert consumer.latest_release_is_conflict_free() is True

    rig.evidence_store.append(
        {
            "attempt_id": _ATTEMPT_ID,
            "reservation_id": _RESERVATION_ID,
            "reason": ReleaseHoldReason.NOT_CORROBORATED.value,
            "detail": None,
        },
        kind=CAPACITY_RELEASE_HELD_KIND,
        record_class=CAPACITY_RELEASE_HELD_KIND,
    )
    assert consumer.latest_release_is_conflict_free() is False
