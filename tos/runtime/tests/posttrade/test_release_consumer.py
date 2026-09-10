"""Hermetic tests for :mod:`tos_runtime.posttrade.release_consumer` (TOS Phase 5 W2-R; plan §10
row ①).

**A genuine structural finding, disclosed here rather than worked around (see
``test_cancel_ack_never_releases_under_the_current_reconciliation_model`` below and the
module-under-test's own docstring for the full write-up).** For a ``CANCEL_ACK``/``EXPIRED``/
``REJECT`` attempt, :class:`~tos_runtime.recon.service.ReconciliationService`'s
``permits_capacity_release`` is **structurally unreachable** under the CURRENT reconciliation
model, for two independent reasons, either one sufficient on its own:

1. :func:`tos.recon.predicates.field_reconciled_proof_ok`'s own docstring names "cancel ACK /
   terminal-status-without-quantity => no FQP token => False" as an explicit, intended case —
   and this consumer's own design produces a non-execution proof ONLY AFTER reconciliation
   corroborates (plan §3's rejected alternative "주문 응답으로 finality 판정"), so no FQP token
   can possibly exist yet when reconciliation runs for a fresh attempt.
2. Measured directly (not merely inferred): ``ReconciliationService``'s own
   ``_QUANTITY_FIELDS`` corroboration (``CUMULATIVE_FILLED_QUANTITY``/
   ``REMAINING_EXECUTABLE_QUANTITY``) requires TWO independent numeric-magnitude observations
   to reach ``CORROBORATED`` — one from the evidence-receipt path, one from the witness path.
   ``EgressResultPayload``'s own validator forbids ANY fill magnitude on a ``CANCEL_ACK``/
   ``EXPIRED``/``REJECT`` payload, so the real
   :class:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter`-written evidence receipt for
   these three kinds NEVER carries a quantity observation — even a fully independent witness
   reporting an explicit zero quantity is then, structurally, ``SINGLE_SOURCE`` at best, never
   ``CORROBORATED``. Fabricating a non-``None`` quantity on the evidence-receipt side in a test
   would misrepresent what the real runtime ever produces, so this suite does not do that.

The consumer's OWN release wiring for this path (produce the non-execution proof, append its
evidence, re-load it, apply the transferable/current gates, release) is still exercised and
pinned — via a hand-picked stub :class:`~tos_runtime.recon.service.ReconciliationService`-shaped
double reporting a canned permitting report, the SAME pattern
``tests/recovery/test_reconciliation.py``'s own scenario (d) mutation guard already uses in this
codebase — never a fake kernel predicate, never a relaxed gate in the module under test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
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
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import (
    CAPACITY_RELEASE_HELD_KIND,
    CAPACITY_RELEASE_INTENT_KIND,
    RELEASE_PROOF_OVERDUE_KIND,
    FinalityReleaseConsumer,
    ReleaseHoldReason,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import scope_reservation_id
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService

from ..engine.conftest import FakeMonotonicSource, FixedKeyProvider  # noqa: F401

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = "acct-relc"
_INSTRUMENT = "101S06"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_ATTEMPT_ID = "attempt-relc-1"
_RESERVATION_ID = scope_reservation_id(_ACCOUNT, _INSTRUMENT)


class _TrustedTimeService:
    """A minimal ``TrustworthyTimeService`` double reporting a genuinely TRUSTED snapshot —
    mirrors ``tests/recovery/test_reconciliation.py``'s own ``_TrustedTimeService``. Also
    exposes ``health_state`` directly (TOS Phase 5 W2-R independent-review H2 fix): the real
    :class:`~tos_runtime.time.service.TrustworthyTimeService` exposes it as a property, and
    :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer
    ._check_obligation_expiry` reads it directly, not through ``current_snapshot()``."""

    health_state: HealthState = HealthState.TRUSTED

    def current_snapshot(self) -> SimpleNamespace:
        identity = SimpleNamespace(tts_generation=1)
        return SimpleNamespace(
            health_state=HealthState.TRUSTED, time_continuity_identity=identity
        )


class _UntrustedTimeService:
    """A ``TrustworthyTimeService`` double reporting a NOT-``TRUSTED`` health state — for the H2
    "evaluate and record nothing" negative test."""

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


@pytest.fixture
def evidence_store(tmp_path: Path) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> SqliteEventInbox:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(tmp_path: Path, evidence_store: SqliteEvidenceStore) -> SqliteCommitLog:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


@pytest.fixture
def monotonic_source() -> FakeMonotonicSource:
    return FakeMonotonicSource()


def _open_reservation(
    rcl_log: SqliteCommitLog,
    *,
    to_state: CapacityState = CapacityState.POTENTIALLY_LIVE,
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
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-relc-setup",
        command_digest="dig-relc-setup",
        expected_seq=-1,
    )


def _open_reservation_under_scope(
    rcl_log: SqliteCommitLog, *, scope: ReservationScope
) -> None:
    """Like :func:`_open_reservation`, but persists a caller-supplied
    :class:`~tos.rcl.ReservationScope` (H1 fix tests: a scope genuinely divergent from what the
    finality proof under test claims)."""
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rcl_log.acquire_epoch(identity)
    rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=_RESERVATION_ID,
            writer_epoch=epoch,
            from_state=CapacityState.COMMITTED_UNBOUND,
            to_state=CapacityState.POTENTIALLY_LIVE,
            scope=scope,
        ),
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-relc-setup-divergent",
        command_digest="dig-relc-setup-divergent",
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
    """Commit one more reservation-lifecycle transition on the ALREADY-open ``_RESERVATION_ID``
    reservation, reading the current tip fresh (M1 fix test: chaining the reservation through
    multiple occupancies of the same overdue-eligible state)."""
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
        # A minimal shape sufficient for SqliteEvidenceReceiptReader's own idempotency-key
        # scan (module docstring, "fake recon PORTS") -- never read by FinalityReleaseConsumer
        # itself, which always re-loads its OWN proof independently.
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
    """A genuinely independent (``independent_of_evidence_store=True``) broker witness double
    reporting a ``FILLED`` order — mirrors ``test_reconciliation.py``'s own ``a2`` scenario.
    """

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
    *,
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    witness: object,
    monotonic_source: FakeMonotonicSource,
    release_proof_wait_ms: int = 60_000,
    time_service: object | None = None,
) -> FinalityReleaseConsumer:
    recon_service = ReconciliationService(
        rcl_reader=SqliteReservationProjectionReader(rcl_log),
        evidence_reader=SqliteEvidenceReceiptReader(evidence_store),
        witness=witness,
        reservation_id_for_attempt=lambda _attempt_id: _RESERVATION_ID,
    )
    return FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=recon_service,
        time_service=(
            time_service if time_service is not None else _TrustedTimeService()
        ),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=monotonic_source,
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


def _reservation_state(rcl_log: SqliteCommitLog) -> CapacityState | None:
    for reservation_id, state, _seq, _scope in rcl_log.reservation_rows():
        if reservation_id == _RESERVATION_ID:
            return state
    return None


def _kind_seq(evidence_store: SqliteEvidenceStore, kind: str) -> list[int]:
    rows = evidence_store.connection.execute(
        "SELECT seq FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    ).fetchall()
    return [seq for (seq,) in rows]


# -- FULL_FILL -> POSITION_CONSUMED (happy path) -------------------------------------


def test_full_fill_with_independent_witness_releases_to_position_consumed(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    # finality_proof_recorded=False here: the REAL proof was already appended above (line 315);
    # a second, minimal-shaped POSTTRADE_FINALITY_PROOF row with the same idempotency key would
    # shadow it in _reload_proof's ORDER BY seq DESC scan (a self-inflicted test bug caught while
    # writing this suite -- see this module's own docstring discipline of never faking a proof).
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=False)
    _open_reservation(rcl_log)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POSITION_CONSUMED
    assert _held_rows(evidence_store) == []
    # Ordering pin: CAPACITY_RELEASE_INTENT must be durable strictly BEFORE the RCL log's own
    # RCL_RESERVATION_TRANSITION evidence row for this transition.
    intent_seqs = _kind_seq(evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    rcl_seqs = _kind_seq(evidence_store, "RCL_RESERVATION_TRANSITION")
    assert len(intent_seqs) == 1
    assert len(rcl_seqs) >= 1
    assert intent_seqs[0] < rcl_seqs[-1]


def test_full_fill_without_witness_holds(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Gate 1: a durable witness that is not exactly ``True`` (e.g. never written, mirroring a
    non-``FULL_FILL`` producer outcome) holds -- never releases."""
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=True)
    _open_reservation(rcl_log)
    # deliberately never calling inbox.record_finality_witness(...)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NO_WITNESS.value


# -- mutation pin (a): a non-positive report must hold even for a FULL_FILL payload ---


def test_report_not_permitting_capacity_release_holds_even_with_witness_and_proof(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """A ``ReconciliationService`` whose report never permits capacity release (fake PORTS
    reporting no receipt at all, so the kernel predicate itself refuses) must hold -- catches
    a hypothetical implementation that released off the payload's own ``FULL_FILL`` kind alone,
    bypassing the reconciliation report."""
    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    _open_reservation(rcl_log)
    # No EGRESS_RESULT_CONSUMED receipt recorded at all -- the evidence-receipt path sees
    # nothing, so classification can never reach MATCHED and permits_capacity_release is False.

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    assert _kind_seq(evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []


# -- non-independent (synthetic) witness holds, exactly like the composed runtime today --


def test_full_fill_with_non_independent_witness_holds(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness

    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    # finality_proof_recorded=False: the REAL proof is already appended above -- see the
    # matching comment on test_full_fill_with_independent_witness_releases_to_position_consumed.
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=False)
    _open_reservation(rcl_log)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=SyntheticLedgerWitness(evidence_store),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value


# -- CANCEL_ACK / EXPIRED / REJECT -> RELEASED --------------------------------------


class _StubPermittingReconciliationService:
    """A minimal ``ReconciliationService``-shaped stand-in returning a canned, permitting
    report -- the SAME pattern ``tests/recovery/test_reconciliation.py``'s own scenario (d)
    mutation guard uses (module docstring): exercises THIS consumer's own release wiring in
    isolation from whether the real kernel-backed reconciliation model can reach that report
    for a ``CANCEL_ACK``/``EXPIRED``/``REJECT`` attempt today (see
    ``test_cancel_ack_never_releases_under_the_current_reconciliation_model`` for that).
    """

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


def test_cancel_ack_releases_when_reconciliation_permits_it(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Pins the consumer's OWN release wiring for the non-execution path: given a permitting
    reconciliation report (module docstring's stub), the consumer produces the zero-quantity
    non-execution proof itself, durably records it, re-loads it, and releases to ``RELEASED``.
    """
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.CANCEL_ACK,
    )
    _open_reservation(rcl_log)

    consumer = FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=_StubPermittingReconciliationService(),  # type: ignore[arg-type]
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.RELEASED
    assert _held_rows(evidence_store) == []
    proof_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
    ).fetchone()[0]
    assert proof_rows == 1
    obligation_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'ECONOMIC_OBLIGATION'"
    ).fetchone()[0]
    assert obligation_rows == 1
    intent_seqs = _kind_seq(evidence_store, CAPACITY_RELEASE_INTENT_KIND)
    rcl_seqs = _kind_seq(evidence_store, "RCL_RESERVATION_TRANSITION")
    assert len(intent_seqs) == 1
    assert intent_seqs[0] < rcl_seqs[-1]


def test_cancel_ack_never_releases_under_the_current_reconciliation_model(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """The honest, undoctored path (module docstring): a fresh ``CANCEL_ACK``, a fully
    independent witness reporting ``CANCELLED``, and NO pre-existing FQP token -- exactly what
    a genuine first encounter looks like under this consumer's own AFTER-corroboration proof
    design -- still holds via the REAL :class:`~tos_runtime.recon.service.ReconciliationService`
    and REAL evidence-receipt reader, because :func:`tos.recon.predicates
    .field_reconciled_proof_ok` refuses any capacity-releasing field with no FQP token AND the
    quantity fields can never reach ``CORROBORATED`` from a single (witness-only) numeric
    observation. Structural, not a bug (module docstring)."""
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.CANCEL_ACK,
    )
    _record_non_execution_receipt(
        evidence_store, kind="CANCEL_ACK", finality_proof_recorded=False
    )
    _open_reservation(rcl_log)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentCancelledWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    proof_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
    ).fetchone()[0]
    assert proof_rows == 0


# -- non-eligible kinds do nothing at all ---------------------------------------------


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
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
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
    _open_reservation(rcl_log)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    assert _held_rows(evidence_store) == []
    assert _kind_seq(evidence_store, CAPACITY_RELEASE_INTENT_KIND) == []


# -- obligation expiry (plan §10 row ④, record-only) -----------------------------------


def test_obligation_expiry_first_observation_only_records_wait_start(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.ACK
    )
    _open_reservation(rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)

    overdue = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert overdue == 0
    # H2 fix: the wait-start marker is in-memory ONLY, never a durable evidence row (module
    # docstring's "never persist a monotonic reading") -- assert directly on the in-memory map.
    assert len(consumer._wait_start_ms) == 1  # noqa: SLF001
    wait_start_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'RELEASE_PROOF_WAIT_START'"
    ).fetchone()[0]
    assert wait_start_rows == 0


def test_obligation_expiry_records_overdue_once_past_the_bound(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.ACK
    )
    _open_reservation(rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)  # first observation -- WAIT_START only

    monotonic_source.advance(1_001)
    consumer.consume(payload)  # now overdue

    overdue = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert overdue == 1

    consumer.consume(payload)  # a third call must not duplicate the OVERDUE row
    overdue_again = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert overdue_again == 1


def test_obligation_expiry_never_fires_for_a_non_overdue_eligible_state(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.ACK
    )
    _open_reservation(rcl_log, to_state=CapacityState.POTENTIALLY_LIVE)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)
    monotonic_source.advance(5_000)
    consumer.consume(payload)

    for kind in (RELEASE_PROOF_OVERDUE_KIND, "RELEASE_PROOF_WAIT_START"):
        count = evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
        ).fetchone()[0]
        assert count == 0


# -- H2 fix: obligation expiry evaluates/records nothing without TRUSTED time -----------


def test_obligation_expiry_evaluates_nothing_when_time_is_not_trusted(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding H2: with ``time_service.health_state`` not ``TRUSTED``,
    :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer
    ._check_obligation_expiry` must read nothing and record nothing at all -- not even the
    in-memory wait-start marker."""
    payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.ACK
    )
    _open_reservation(rcl_log, to_state=CapacityState.QUARANTINED_UNKNOWN)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
        release_proof_wait_ms=1_000,
        time_service=_UntrustedTimeService(),
    )
    consumer.consume(payload)
    monotonic_source.advance(5_000)
    consumer.consume(payload)

    assert consumer._wait_start_ms == {}  # noqa: SLF001
    for kind in (RELEASE_PROOF_OVERDUE_KIND, "RELEASE_PROOF_WAIT_START"):
        count = evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
        ).fetchone()[0]
        assert count == 0


# -- M1 fix: once per OCCUPANCY, not once per reservation forever -----------------------


def test_obligation_expiry_records_overdue_again_for_a_new_occupancy(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding M1: leaving the overdue-eligible state and re-entering it
    (a genuinely NEW occupancy, keyed by the reservation's own advanced ``reservation_last_seq``)
    must be able to record a SECOND ``RELEASE_PROOF_OVERDUE`` row -- the prior version's
    reservation-id-only key let at most one such row ever exist per reservation, for any number
    of separate occupancies."""
    payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.ACK
    )
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rcl_log.acquire_epoch(identity)
    rcl_log.apply_reservation_transition(
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
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
        release_proof_wait_ms=1_000,
    )
    consumer.consume(payload)  # occupancy 1, first observation
    monotonic_source.advance(1_001)
    consumer.consume(payload)  # occupancy 1 -- overdue, row #1

    first_overdue = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert first_overdue == 1

    # Leave the overdue-eligible state (occupancy 1 ends), then re-enter it (occupancy 2 begins
    # at a genuinely later reservation_last_seq).
    _commit_transition(
        rcl_log,
        epoch=epoch,
        from_state=CapacityState.QUARANTINED_UNKNOWN,
        to_state=CapacityState.POTENTIALLY_LIVE,
        command_id="cmd-relc-exit-occupancy-1",
    )
    _commit_transition(
        rcl_log,
        epoch=epoch,
        from_state=CapacityState.POTENTIALLY_LIVE,
        to_state=CapacityState.QUARANTINED_UNKNOWN,
        command_id="cmd-relc-enter-occupancy-2",
    )

    consumer.consume(payload)  # occupancy 2, first observation -- no new OVERDUE yet
    still_one = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert still_one == 1

    monotonic_source.advance(1_001)
    consumer.consume(payload)  # occupancy 2 -- overdue, row #2

    second_overdue = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (RELEASE_PROOF_OVERDUE_KIND,)
    ).fetchone()[0]
    assert second_overdue == 2


# -- H1 fix: gate 4 inputs are independent of the proof under test ----------------------


def test_gate4_holds_when_the_rcl_persisted_scope_diverges_from_the_proof(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding H1: ``target_leg_scope``'s account now comes from the RCL
    reservation's OWN persisted scope (a genuinely separate write path), not from
    ``self.account``/``FinalityConfig`` -- a proof minted for one account is refused for a
    reservation persisted under a DIFFERENT account, which the prior (vacuous) construction
    could never detect since both sides derived from the identical config constant."""
    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=False)
    # The reservation this attempt's own scope resolves to is persisted under a DIFFERENT
    # account than the one the proof's own leg_scope claims.
    _open_reservation_under_scope(
        rcl_log,
        scope=ReservationScope(account="divergent-account", instrument=_INSTRUMENT),
    )

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_TRANSFERABLE.value


def test_gate4_holds_when_a_newer_obligation_generation_supersedes_the_proof(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding H1: ``active_generation`` now comes from the NEWEST
    ``obligation_generation`` durably recorded across every ``ECONOMIC_OBLIGATION`` row sharing
    this reservation's scope -- an independent evidence-store scan, never
    ``proof.bound_generation`` read off the very artifact under test. A second, later-recorded
    obligation for the SAME scope with an ADVANCED generation (simulating a future correction
    lane) reopens finality for the earlier proof."""
    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=False)
    _open_reservation(rcl_log)
    # A later correction lane records a SECOND obligation for the SAME scope, generation
    # advanced past what the original proof (bound_generation=0) was issued under.
    evidence_store.append(
        {
            "account_scope": _ACCOUNT,
            "instrument_identity": _INSTRUMENT,
            "obligation_generation": 1,
        },
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_CURRENT.value


# -- M3 fix: the non-execution path also re-loads (never trusts the in-memory proof) ----


def test_non_execution_path_genuinely_reloads_rather_than_trusting_produced_proof(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent-review finding M3 (mutation (d), direct pin): forces
    :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer._reload_proof` to
    return ``None`` unconditionally (as if the just-appended row could not be found) while
    leaving the durable evidence rows genuinely present. If ``_consume_non_execution`` ever
    regressed to using the in-memory ``produced.proof`` object instead of this method's own
    return value, the release would proceed anyway and this test would see ``RELEASED`` instead
    of a ``PROOF_NOT_RELOADED`` hold -- an unambiguous, direct pin of the exact code path
    mutation (d) targeted (unlike a gate-4 divergence, which cannot distinguish "used the
    reload's value" from "used the in-memory object" when both carry identical content).
    """
    monkeypatch.setattr(
        FinalityReleaseConsumer,
        "_reload_proof",
        lambda *_args, **_kwargs: None,
    )
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.CANCEL_ACK,
    )
    _open_reservation(rcl_log)

    consumer = FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=_StubPermittingReconciliationService(),  # type: ignore[arg-type]
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_RELOADED.value
    # The proof WAS durably produced (the mutation only stops _reload_proof from finding it) --
    # confirms this test exercises "reload fails" specifically, not "production itself failed".
    proof_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
    ).fetchone()[0]
    assert proof_rows == 1


def test_non_execution_path_holds_when_gate4_diverges_too(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding M3 (routing through gate 4): the non-execution destination now
    runs the SAME :meth:`_apply_gate4_and_release` the ``FULL_FILL`` path runs -- a scope
    divergence holds it exactly like the ``FULL_FILL`` case
    (``test_gate4_holds_when_the_rcl_persisted_scope_diverges_from_the_proof``), which the
    pre-M3 code (a direct ``_release`` call, skipping gate 4 entirely) could never do.
    """
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.CANCEL_ACK,
    )
    _open_reservation_under_scope(
        rcl_log,
        scope=ReservationScope(account="divergent-account", instrument=_INSTRUMENT),
    )

    consumer = FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=_StubPermittingReconciliationService(),  # type: ignore[arg-type]
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.PROOF_NOT_TRANSFERABLE.value
    proof_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
    ).fetchone()[0]
    assert proof_rows == 1


# -- M4 fix: distinct idempotency-key prefixes prevent shadowing between the two proof kinds --


def test_non_execution_proof_never_shadows_an_earlier_full_fill_proof_for_the_same_attempt(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding M4: a ``FULL_FILL`` proof recorded for an attempt, followed by
    a (hypothetical) non-execution proof recorded LATER for the SAME attempt id, must NOT shadow
    each other in ``_reload_proof`` -- distinct id/idempotency-key prefixes
    (:data:`~tos_runtime.posttrade.finality.FULL_FILL_PROOF_ID_PREFIX` vs
    :data:`~tos_runtime.posttrade.finality.NON_EXECUTION_PROOF_ID_PREFIX`) make the two rows
    independently addressable by kind, not merely by attempt id + recency."""
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
    evidence_store.append(
        fill_result.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    evidence_store.append(
        fill_result.proof.model_dump(mode="json"),
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )

    non_exec_payload = EgressResultPayload(
        instrument_key=_KEY, attempt_id=_ATTEMPT_ID, kind=EgressResultKind.CANCEL_ACK
    )
    non_exec_result = producer.produce_non_execution(non_exec_payload)
    assert non_exec_result is not None
    evidence_store.append(
        non_exec_result.record.model_dump(mode="json"),
        kind="ECONOMIC_OBLIGATION",
        record_class="ECONOMIC_OBLIGATION",
    )
    evidence_store.append(
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

    _open_reservation(rcl_log)
    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )

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


# -- M7 fix: the MATCHED conjunct is load-bearing ----------------------------------------


def test_matched_conjunct_holds_when_no_classification_covers_the_attempt(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """Independent-review finding M7 (mutation (m)): a report that permits capacity release but
    carries NO classification for this exact attempt (an empty-scope or foreign-attempt report)
    must still hold -- the ``matched`` conjunct's real job."""

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

    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.CANCEL_ACK,
    )
    _open_reservation(rcl_log)

    consumer = FinalityReleaseConsumer(
        rcl_log=rcl_log,
        projection=SqliteReservationProjectionReader(rcl_log),
        evidence_store=evidence_store,
        inbox=inbox,
        recon_service=_StubPermittingButUnclassifiedReport(),  # type: ignore[arg-type]
        time_service=_TrustedTimeService(),
        finality_producer=_producer(),
        scheme=SCHEME,
        monotonic_source=monotonic_source,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        release_proof_wait_ms=60_000,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POTENTIALLY_LIVE
    held = _held_rows(evidence_store)
    assert len(held) == 1
    assert held[0]["reason"] == ReleaseHoldReason.NOT_CORROBORATED.value
    proof_rows = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
    ).fetchone()[0]
    assert proof_rows == 0


# -- L1: from_state is read dynamically, never a hardcoded constant ---------------------


def test_release_reads_from_state_dynamically_not_a_hardcoded_constant(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    monotonic_source: FakeMonotonicSource,
) -> None:
    """LOW L1: opens the reservation directly at ``ATTEMPT_BOUND`` (never touching
    ``POTENTIALLY_LIVE`` at all) and still expects a successful release -- if ``_release`` ever
    hardcoded ``from_state=CapacityState.POTENTIALLY_LIVE`` instead of reading the projection's
    actual current state, the RCL log's own ``check_reservation_from_state`` HIGH-1 gate would
    refuse the transition (claimed ``from_state`` must equal the held row's state exactly).
    """
    identity = RuntimeIdentity(
        cell_id="relc-test-cell", process_nonce="relc-test-nonce"
    )
    epoch = rcl_log.acquire_epoch(identity)
    rcl_log.apply_reservation_transition(
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
    assert _reservation_state(rcl_log) is CapacityState.ATTEMPT_BOUND

    producer = _producer()
    payload = EgressResultPayload(
        instrument_key=_KEY,
        attempt_id=_ATTEMPT_ID,
        kind=EgressResultKind.FULL_FILL,
        filled_quantity=Decimal("10"),
        remaining_quantity=Decimal("0"),
    )
    produced = producer.produce(payload)
    assert produced is not None
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
    inbox.record_finality_witness(_ATTEMPT_ID, True)
    _record_full_fill_receipt(evidence_store, finality_proof_recorded=False)

    consumer = _consumer(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        inbox=inbox,
        witness=_IndependentFullFillWitness(),
        monotonic_source=monotonic_source,
    )
    consumer.consume(payload)

    assert _reservation_state(rcl_log) is CapacityState.POSITION_CONSUMED
    assert _held_rows(evidence_store) == []
