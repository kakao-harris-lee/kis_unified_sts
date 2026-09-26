"""Lane C pin (W3 plan §4 W3 row C: "``ReconciliationService`` 경로 실증 — 실 증인일 때
``CORROBORATED`` 의 의미가 바뀌는 지점을 테스트로 고정 · 합성 증인과의 차이").

**Status (carryover plan W-C C-1, 2026-09-25): the orders-axis gap described below is closed.**
``ReconciliationService`` now cross-references ``broker_execution_id``
(``service._join_orders_by_execution_id``), so the same ODNO the evidence receipt recorded joins its
attempt. The (b) tests below were flipped from pinning the gap to pinning the join; the history is
kept because it is why the join exists. The one-to-one/ambiguity rules themselves are pinned in
``test_service_execution_id_join.py``.

**Why this file exists — read this before deleting any test in it.** The W3 plan's own §0.4
states the wave's entire justification: a genuinely independent witness turns a ``CORROBORATED``
verdict from a structural label into something substantive. This file's second half
(:func:`test_real_kis_witness_cannot_join_the_same_order_to_its_known_attempt` and
:func:`test_kis_witness_permits_stay_false_across_every_rcl_and_evidence_combination`) measures
that this is **FALSE on the orders axis specifically**, with the real, concrete
:class:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness` class — not a prediction, not a
double standing in for a hoped-for future shape.

**The mechanism, named exactly.** :class:`~tos_runtime.recon.ports.WitnessOrder.attempt_id` is
how :class:`~tos_runtime.recon.service.ReconciliationService.reconcile` joins a witness-observed
order to the attempt the RCL/evidence-receipt paths already know about
(``witness_by_attempt = {o.attempt_id: o for o in snapshot.orders if o.attempt_id is not None}``,
``service.py``'s own ``reconcile`` body). ``KisStockBrokerWitness._order_from_row`` has exactly
ONE construction site for :class:`WitnessOrder` in the whole module, and it hardcodes
``attempt_id=None`` unconditionally — KIS's own 주문체결조회 response
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1548-1575``) carries no
attempt-id concept at all; an ODNO identifies a broker order, never a runtime attempt. The
consequence follows deductively, not just from the two cases this file happens to run: since
``witness_by_attempt`` can therefore NEVER contain an entry keyed by any real attempt id,
``_classify_attempt`` (``service.py``) can never see ``has_witness=True`` for a known attempt, so
its ``classification is ReconciliationClass.MATCHED`` branch is UNREACHABLE whenever this witness
is the injected one — and both ``rearm_ok``/``capacity_ok`` in
``_attempt_field_confidences_and_gates`` are gated on exactly that ``classification is MATCHED``
check. Every order this witness returns instead lands in ``orphan_orders`` (``o.attempt_id is
None`` — true of literally every order it can ever produce), where ``reconcile`` hardcodes
``rearm_flags.append(False)`` / ``capacity_flags.append(False)`` unconditionally. **The double
counting this produces**: the SAME physical broker order (same ``broker_execution_id``/ODNO) the
evidence-receipt path already recorded against a known attempt (1) degrades that attempt's own
classification to ``STALE_RESERVATION`` (RCL present, no witness confirmation reaches it) AND (2)
is separately reported a second time as an unrelated ``ORPHAN_BROKER_ORDER`` — not corroboration,
a duplicate. Closing this (a ``broker_execution_id`` cross-reference between the witness and
:class:`~tos_runtime.recon.ports.EvidenceReceiptReader`, added to ``ReconciliationService`` itself)
is a service-level design decision this witness lane does not get to make on its way past — it is
reported here, pinned as a test, and left alone.

**The other half, stated with equal weight because it is also true.** This gap is specific to the
ORDERS axis (the ``attempt_id`` join). The POSITIONS/CASH axis needs no attempt join at all —
:attr:`~tos_runtime.recon.ports.WitnessSnapshot.positions`/``cash`` are account-level facts, not
per-attempt ones. An independent, continuation-complete positions/cash read from the real broker
is exactly what this witness delivers without qualification; see
``test_witness_kis.py::test_multi_page_balance_walk_assembles_all_25_positions`` and
``test_independent_of_evidence_store_is_true``. Nothing here contradicts that half.

Exercises the two CONCRETE ``BrokerWitness`` implementations — not Protocol doubles — inside a
real :class:`~tos_runtime.recon.service.ReconciliationService`, against a real
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore` shared with a real
:class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader`.
"""

from __future__ import annotations

import pytest
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityState, CapacityVector
from tos.recon import FieldConfidenceClass, FreshnessMarker, SafetyRelevantField
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import ReservationProjectionReader, WitnessScope
from tos_runtime.recon.service import ReconciliationClass, ReconciliationService
from tos_runtime.recon.witness_kis import KisStockBrokerWitness
from tos_runtime.recon.witness_kis_client import KisWitnessHttpClient
from tos_runtime.recon.witness_kis_config import KisWitnessConfig
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness

from ._fake_kis_get_server import FakeKisGetServer
from ._witness_kis_fakes import FakeKstDateSource, FakeTokenSession

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ACCOUNT = "1234567801"  # CANO=12345678, ACNT_PRDT_CD=01


class _MinimalRclReader:
    """A tiny :class:`~tos_runtime.recon.ports.ReservationProjectionReader` double — local to
    this file rather than imported from ``test_service.py``, matching this test suite's own
    convention of small per-file fakes (mirrors ``test_service.py``'s ``FakeRclReader``
    structurally, not by import)."""

    def __init__(self, states: dict[str, CapacityState]) -> None:
        self._states = dict(states)

    def reservation_state(self, reservation_id: str) -> CapacityState | None:
        return self._states.get(reservation_id)

    def reservation_last_seq(self, _reservation_id: str) -> int | None:
        return None

    def all_reservations(self) -> dict[str, CapacityState]:
        return dict(self._states)

    def instrument_state(self, _key: InstrumentKey) -> CapacityState | None:
        return None

    def instrument_last_seq(self, _key: InstrumentKey) -> int | None:
        return None

    def reservation_committed_vector(
        self, _reservation_id: str
    ) -> CapacityVector | None:
        return None

    def instrument_committed_vector(self, _key: InstrumentKey) -> CapacityVector | None:
        return None


@pytest.fixture
def fresh() -> FreshnessMarker:
    return FreshnessMarker(
        fresh_within_horizon=True,
        time_confidence_held=True,
        time_generation=1,
        anchored_generation=1,
    )


def test_rcl_double_satisfies_protocol() -> None:
    assert isinstance(_MinimalRclReader({}), ReservationProjectionReader)


def _append_egress_result(store, **overrides: object) -> None:
    fields: dict[str, object] = {
        "attempt_id": "a1",
        "instrument_key": {"account": ACCOUNT, "instrument": "005930"},
        "egress_result_kind": "FULL_FILL",
        "broker_execution_id": "0000004470",
        "filled_quantity": "1",
        "remaining_quantity": "0",
    }
    fields.update(overrides)
    store.append(fields, kind="EGRESS_RESULT_CONSUMED", record_class="RESULT_UNMATCHED")


# ---------------------------------------------------------------------------
# (a) the concrete SyntheticLedgerWitness — independence collapses (baseline,
#     now pinned against the CONCRETE classes rather than test_service.py's doubles)
# ---------------------------------------------------------------------------


def test_synthetic_witness_never_reaches_corroborated_even_when_matched(
    store, fresh
) -> None:
    _append_egress_result(store)
    rcl = _MinimalRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = SqliteEvidenceReceiptReader(store)
    witness = SyntheticLedgerWitness(
        store
    )  # independent_of_evidence_store=False, always
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    [record] = report.classifications
    assert record.attempt_id == "a1"
    assert record.classification == ReconciliationClass.MATCHED
    # Matched, but the two CAPACITY-RELEASING quantity fields are never CORROBORATED: their
    # only two observations (evidence-receipt + witness) carry the SAME independence class
    # (EVIDENCE_RECEIPT) because the synthetic witness reads the same store — RECON-EV-001's
    # "common-mode paths cannot corroborate each other" (mirrors test_service.py's own
    # ``test_synthetic_witness_never_permits_capacity_release`` exactly, against the CONCRETE
    # ``SyntheticLedgerWitness``/``SqliteEvidenceReceiptReader`` classes instead of doubles).
    # ORDER_EXISTENCE is excluded from this check on purpose: RCL + the evidence receipt are
    # ALREADY two distinct independence classes (RCL_RESERVATION_LOG / EVIDENCE_RECEIPT) for
    # that one field, independent of the witness path entirely — this test is not claiming
    # otherwise.
    assert not any(
        fc.confidence_class is FieldConfidenceClass.CORROBORATED
        and fc.field
        in (
            SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
            SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
        )
        for fc in report.field_confidences
    )
    assert report.permits_capacity_release is False


# ---------------------------------------------------------------------------
# (b) the concrete KisStockBrokerWitness — genuinely independent, but structurally
#     UNABLE to join to an attempt (the finding this file exists to pin)
# ---------------------------------------------------------------------------


@pytest.fixture
def kis_server():
    srv = FakeKisGetServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _kis_witness(server: FakeKisGetServer) -> KisStockBrokerWitness:
    config = KisWitnessConfig(
        endpoint_rest_base=server.rest_base,
        balance_path=BALANCE_PATH,
        balance_tr_id="VTTC8434R",
        order_inquiry_path=ORDER_PATH,
        order_inquiry_tr_id="VTTC0081R",
        request_timeout_s=2.0,
        max_pages=10,
        allow_plaintext_for_tests=True,
    )
    client = KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=True,
    )
    return KisStockBrokerWitness(
        config=config,
        client=client,
        token_session=FakeTokenSession(),
        date_source=FakeKstDateSource(),
    )


def test_real_kis_witness_joins_the_same_order_to_its_known_attempt(
    store, fresh, kis_server: FakeKisGetServer
) -> None:
    """C-1: the SAME broker order (same ODNO) the evidence-receipt path recorded for attempt ``a1``
    comes back from the REAL witness with ``attempt_id=None`` and now joins ``a1`` through the
    ``broker_execution_id`` cross-reference — MATCHED, and no duplicate orphan. Before C-1 this
    exact setup degraded ``a1`` to ``STALE_RESERVATION`` and re-reported the order as an
    ``ORPHAN_BROKER_ORDER`` (module docstring).

    Re-arm follows: three independence classes (RCL, receipt, the independent KIS witness) agree on
    existence and the quantities agree. Capacity release does NOT — no separately recorded
    finality proof exists for ``a1``, and a fill receipt alone is not a Final Quantity Proof.
    """
    _append_egress_result(store)
    kis_server.queue_response(
        BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []}
    )
    kis_server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "odno": "0000004470",  # matches the evidence receipt's broker_execution_id
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
        },
    )
    rcl = _MinimalRclReader({"a1": CapacityState.POSITION_CONSUMED})
    evidence = SqliteEvidenceReceiptReader(store)
    witness = _kis_witness(kis_server)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    [record] = report.classifications
    assert record.attempt_id == "a1"
    assert record.classification == ReconciliationClass.MATCHED
    assert record.broker_execution_id == "0000004470"
    assert report.permits_rearm is True
    assert report.permits_capacity_release is False


@pytest.mark.parametrize(
    "rcl_present,evidence_present",
    [
        (True, True),  # RCL knows the attempt, evidence-receipt recorded it too
        (True, False),  # RCL knows the attempt, no receipt at all
        (False, True),  # no RCL reservation, but a receipt exists
        (False, False),  # neither RCL nor a receipt — attempt named only by scope
    ],
)
def test_kis_witness_permits_stay_false_across_every_rcl_and_evidence_combination(
    store,
    fresh,
    kis_server: FakeKisGetServer,
    rcl_present: bool,
    evidence_present: bool,
) -> None:
    """All four combinations of RCL-reservation-present x evidence-receipt-present with the real
    KIS witness. After C-1 the witness order joins ``a1`` only through a receipt that recorded its
    ODNO, so ``MATCHED`` — and with it re-arm — is reached in exactly the (RCL, receipt) case and
    in no other; capacity release stays ``False`` in all four (no finality proof is recorded).
    Before C-1 ``MATCHED`` was unreachable in all four (module docstring). The case this loop
    does NOT reach is "no attempt named at all", covered by ``ReconciliationReport``'s own
    empty-``rearm_flags`` guard (module docstring's "fail-closed throughout").
    """
    if evidence_present:
        _append_egress_result(store)
    kis_server.queue_response(
        BALANCE_PATH, status=200, body={"rt_cd": "0", "output1": []}
    )
    kis_server.queue_response(
        ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [
                {
                    "odno": "0000004470",
                    "tot_ccld_qty": "1",
                    "rmn_qty": "0",
                    "cncl_yn": "N",
                }
            ],
        },
    )
    rcl_states = {"a1": CapacityState.POSITION_CONSUMED} if rcl_present else {}
    rcl = _MinimalRclReader(rcl_states)
    evidence = SqliteEvidenceReceiptReader(store)
    witness = _kis_witness(kis_server)
    service = ReconciliationService(rcl, evidence, witness)

    report = service.reconcile(
        WitnessScope(account=ACCOUNT, attempt_ids=("a1",)), freshness=fresh
    )

    by_attempt = {c.attempt_id: c for c in report.classifications}
    joined = rcl_present and evidence_present
    assert (by_attempt["a1"].classification is ReconciliationClass.MATCHED) is joined
    assert report.permits_rearm is joined
    assert report.permits_capacity_release is False
