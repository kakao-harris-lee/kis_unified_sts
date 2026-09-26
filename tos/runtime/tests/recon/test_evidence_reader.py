"""``SqliteEvidenceReceiptReader`` tests (TOS Phase 5 W1 close-out, GAP 1) — reads real durable
evidence-store rows, mirroring ``test_witness_synthetic.py``'s own technique for the same store.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from tos_runtime.recon import evidence_reader
from tos_runtime.recon.evidence_reader import SqliteEvidenceReceiptReader
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable


def _append_result(
    store,
    *,
    attempt_id,
    account="acct-1",
    instrument="005930",
    egress_result_kind,
    kind="RESULT_UNMATCHED",
    broker_execution_id=None,
    filled_quantity=None,
    remaining_quantity=None,
):
    store.append(
        {
            "attempt_id": attempt_id,
            "instrument_key": {"account": account, "instrument": instrument},
            "egress_result_kind": egress_result_kind,
            "broker_execution_id": broker_execution_id,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
        },
        kind=kind,
        record_class=kind,
    )


def _append_finality_proof(store, *, attempt_id):
    store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{attempt_id}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def test_receipts_reads_ack_and_unknown_from_the_evidence_store(store) -> None:
    """The task brief's own fixture: one ACK, one UNKNOWN, one with a finality proof."""
    _append_result(
        store,
        attempt_id="a1",
        egress_result_kind="ACK",
        kind="EGRESS_RESULT_CONSUMED",
        broker_execution_id="syn-exec:a1:ACK",
    )
    _append_result(store, attempt_id="a2", egress_result_kind="UNKNOWN")

    reader = SqliteEvidenceReceiptReader(store)
    receipts = reader.receipts(WitnessScope(account="acct-1"))

    by_attempt = {r.attempt_id: r for r in receipts}
    assert by_attempt["a1"].egress_result_kind == "ACK"
    assert by_attempt["a1"].broker_execution_id == "syn-exec:a1:ACK"
    assert by_attempt["a1"].finality_proof_recorded is False
    assert by_attempt["a2"].egress_result_kind == "UNKNOWN"
    assert by_attempt["a2"].finality_proof_recorded is False


def test_receipts_reports_finality_proof_recorded_only_for_the_proven_attempt(
    store,
) -> None:
    _append_result(
        store,
        attempt_id="a1",
        egress_result_kind="FULL_FILL",
        kind="EGRESS_RESULT_CONSUMED",
        filled_quantity="10",
        remaining_quantity="0",
    )
    _append_result(store, attempt_id="a2", egress_result_kind="ACK")
    _append_finality_proof(store, attempt_id="a1")

    reader = SqliteEvidenceReceiptReader(store)
    receipts = reader.receipts(WitnessScope(account="acct-1"))
    by_attempt = {r.attempt_id: r for r in receipts}

    assert by_attempt["a1"].finality_proof_recorded is True
    assert by_attempt["a1"].filled_quantity == Decimal("10")
    assert by_attempt["a1"].remaining_quantity == Decimal("0")
    assert by_attempt["a2"].finality_proof_recorded is False


def test_receipts_filters_by_account(store) -> None:
    _append_result(store, attempt_id="a1", account="acct-1", egress_result_kind="ACK")
    _append_result(store, attempt_id="a2", account="acct-2", egress_result_kind="ACK")

    reader = SqliteEvidenceReceiptReader(store)
    receipts = reader.receipts(WitnessScope(account="acct-1"))

    assert {r.attempt_id for r in receipts} == {"a1"}


def test_receipts_returns_empty_tuple_for_a_genuinely_empty_store(store) -> None:
    reader = SqliteEvidenceReceiptReader(store)
    assert reader.receipts(WitnessScope(account="acct-1")) == ()


def test_receipts_preserves_attempt_id_none(store) -> None:
    _append_result(store, attempt_id=None, egress_result_kind="ACK")
    reader = SqliteEvidenceReceiptReader(store)
    receipts = reader.receipts(WitnessScope(account="acct-1"))
    assert receipts[0].attempt_id is None
    assert receipts[0].finality_proof_recorded is False


def test_a_finality_proof_key_not_matching_the_known_prefix_is_ignored(store) -> None:
    """A malformed / unrelated idempotency_key never falsely credits an attempt with a proof
    it never received (module docstring's "disclosed coupling" — fail-closed, never a false
    positive)."""
    _append_result(
        store,
        attempt_id="a1",
        egress_result_kind="FULL_FILL",
        kind="EGRESS_RESULT_CONSUMED",
        filled_quantity="10",
        remaining_quantity="0",
    )
    store.append(
        {"idempotency_key": "some-other-producer:a1"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )
    reader = SqliteEvidenceReceiptReader(store)
    receipts = reader.receipts(WitnessScope(account="acct-1"))
    assert receipts[0].finality_proof_recorded is False


def test_receipts_raises_witness_unavailable_when_store_is_unreachable(store) -> None:
    store.close()
    reader = SqliteEvidenceReceiptReader(store)
    with pytest.raises(WitnessUnavailable):
        reader.receipts(WitnessScope(account="acct-1"))


def test_module_never_writes_to_the_evidence_store() -> None:
    """Negative-grep: this reader is read-only — it must never call ``store.append``."""
    source = inspect.getsource(evidence_reader)
    assert "_store.append(" not in source
    assert "store.append(" not in source
    assert "import os" not in source
    assert "time.time(" not in source


# ---------------------------------------------------------------------------
# trading_date (plan 2026-09-26 egress trading date, T-4)
# ---------------------------------------------------------------------------


def test_trading_date_is_read_through_the_real_engine_evidence_sink(store) -> None:
    """The date the kernel copied onto the evidence record reaches the receipt observation —
    written by the production sink, not a hand-built payload."""
    from tos.engine import (
        EgressResultKind,
        EngineEvidenceRecord,
        EvidenceKind,
        InstrumentKey,
    )
    from tos_runtime.evidence.sinks import EngineEvidenceSinkAdapter

    EngineEvidenceSinkAdapter(store).record(
        EngineEvidenceRecord(
            kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
            instrument_key=InstrumentKey(account="acct-1", instrument="005930"),
            egress_result_kind=EgressResultKind.ACK,
            attempt_id="a1",
            broker_execution_id="0000003663",
            trading_date="20260805",
        )
    )
    (receipt,) = SqliteEvidenceReceiptReader(store).receipts(
        WitnessScope(account="acct-1")
    )
    assert receipt.trading_date == "20260805"
    assert receipt.broker_execution_id == "0000003663"


@pytest.mark.parametrize(
    "recorded", [None, "", "2026-08-05", "2026085", 20260805], ids=repr
)
def test_absent_or_malformed_trading_date_reads_as_none(store, recorded) -> None:
    """Every receipt recorded before the date existed has no key; a malformed value is no date.
    Either way the join cannot use it."""
    store.append(
        {
            "attempt_id": "a1",
            "instrument_key": {"account": "acct-1", "instrument": "005930"},
            "egress_result_kind": "ACK",
            "broker_execution_id": "0000003663",
            **({} if recorded is None else {"trading_date": recorded}),
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    (receipt,) = SqliteEvidenceReceiptReader(store).receipts(
        WitnessScope(account="acct-1")
    )
    assert receipt.trading_date is None
