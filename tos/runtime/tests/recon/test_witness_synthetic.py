"""``SyntheticLedgerWitness`` tests — reconstructs orders from the real durable
evidence store (no separate ledger exists; see module docstring)."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from tos_runtime.recon import witness_synthetic
from tos_runtime.recon.ports import WitnessOrderState, WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness


def _append_result(
    store,
    *,
    attempt_id,
    account="acct-1",
    instrument="005930",
    egress_result_kind,
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
        kind="RESULT_UNMATCHED",
        record_class="RESULT_UNMATCHED",
    )


def test_observe_reconstructs_ack_and_unknown_orders_from_the_evidence_store(
    store,
) -> None:
    """One ACK + one UNKNOWN result, durably appended to a real evidence store (the
    'tiny evidence store' fixture the task brief asks for) — the witness must derive
    both orders from those rows, never from an invented ledger."""
    _append_result(
        store,
        attempt_id="a1",
        egress_result_kind="ACK",
        broker_execution_id="syn-exec:a1:ACK",
    )
    _append_result(store, attempt_id="a2", egress_result_kind="UNKNOWN")

    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))

    assert snapshot.provenance == "synthetic-ledger"
    by_attempt = {order.attempt_id: order for order in snapshot.orders}
    assert by_attempt["a1"].state is WitnessOrderState.ACKED
    assert by_attempt["a1"].broker_execution_id == "syn-exec:a1:ACK"
    assert by_attempt["a2"].state is WitnessOrderState.UNKNOWN


def test_observe_maps_full_fill_and_partial_fill(store) -> None:
    _append_result(
        store,
        attempt_id="a1",
        egress_result_kind="FULL_FILL",
        filled_quantity="10",
        remaining_quantity="0",
    )
    _append_result(
        store,
        attempt_id="a2",
        egress_result_kind="PARTIAL_FILL",
        filled_quantity="4",
        remaining_quantity="6",
    )

    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))
    by_attempt = {order.attempt_id: order for order in snapshot.orders}

    assert by_attempt["a1"].state is WitnessOrderState.FILLED
    assert by_attempt["a1"].quantity == Decimal("10")
    assert by_attempt["a1"].remaining == Decimal("0")
    assert by_attempt["a2"].state is WitnessOrderState.PARTIAL
    assert by_attempt["a2"].quantity == Decimal("4")


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("CANCEL_ACK", WitnessOrderState.CANCELLED),
        ("EXPIRED", WitnessOrderState.CANCELLED),
        ("REJECT", WitnessOrderState.CANCELLED),
        ("TIMEOUT", WitnessOrderState.UNKNOWN),
        ("SOME_UNMAPPED_FUTURE_KIND", WitnessOrderState.UNKNOWN),
    ],
)
def test_observe_maps_terminal_and_unmapped_kinds_fail_closed(
    store, kind, expected
) -> None:
    _append_result(store, attempt_id="a1", egress_result_kind=kind)
    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))
    assert snapshot.orders[0].state is expected


def test_observe_filters_by_account(store) -> None:
    _append_result(store, attempt_id="a1", account="acct-1", egress_result_kind="ACK")
    _append_result(store, attempt_id="a2", account="acct-2", egress_result_kind="ACK")

    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))

    assert {order.attempt_id for order in snapshot.orders} == {"a1"}


def test_observe_returns_empty_orders_when_nothing_recorded(store) -> None:
    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))
    assert snapshot.orders == ()
    assert snapshot.provenance == "synthetic-ledger"


def test_observe_preserves_attempt_id_none_for_orphan_detection(store) -> None:
    """An order with no attempt_id at all must survive as attempt_id=None — the
    service layer relies on this to detect orphan broker orders."""
    _append_result(store, attempt_id=None, egress_result_kind="ACK")
    witness = SyntheticLedgerWitness(store)
    snapshot = witness.observe(WitnessScope(account="acct-1"))
    assert snapshot.orders[0].attempt_id is None


def test_observe_raises_witness_unavailable_when_store_is_unreachable(store) -> None:
    store.close()
    witness = SyntheticLedgerWitness(store)
    with pytest.raises(WitnessUnavailable):
        witness.observe(WitnessScope(account="acct-1"))


def test_module_never_writes_to_the_evidence_store() -> None:
    """Negative-grep: this witness is read-only — it must never call ``store.append``
    (a plain ``list.append`` used to build the returned payload list is fine; only the
    evidence-store WRITE call is forbidden)."""
    source = inspect.getsource(witness_synthetic)
    assert "_store.append(" not in source
    assert "store.append(" not in source
    assert "import os" not in source
    assert "time.time(" not in source
