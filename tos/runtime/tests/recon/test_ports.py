"""``tos_runtime.recon.ports`` tests — Protocol conformance + negative-greps."""

from __future__ import annotations

import inspect
from decimal import Decimal

from tos_runtime.recon import ports
from tos_runtime.recon.ports import (
    BrokerWitness,
    EgressReceiptObservation,
    EvidenceReceiptReader,
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness


class _FakeWitness:
    def observe(self, _scope: WitnessScope) -> WitnessSnapshot:
        return WitnessSnapshot(observed_at_generation=1, orders=(), provenance="fake")


class _FakeEvidenceReader:
    def receipts(self, _scope: WitnessScope) -> tuple[EgressReceiptObservation, ...]:
        return ()


def test_broker_witness_protocol_conformance() -> None:
    assert isinstance(_FakeWitness(), BrokerWitness)


def test_evidence_receipt_reader_protocol_conformance() -> None:
    assert isinstance(_FakeEvidenceReader(), EvidenceReceiptReader)


def test_synthetic_ledger_witness_satisfies_broker_witness_protocol(store) -> None:
    assert isinstance(SyntheticLedgerWitness(store), BrokerWitness)


def test_witness_unavailable_is_an_exception() -> None:
    assert issubclass(WitnessUnavailable, Exception)


def test_witness_order_state_vocabulary() -> None:
    assert {member.value for member in WitnessOrderState} == {
        "ACKED",
        "FILLED",
        "PARTIAL",
        "CANCELLED",
        "UNKNOWN",
    }


def test_witness_scope_is_frozen() -> None:
    scope = WitnessScope(account="acct-1", attempt_ids=("a1",))
    try:
        scope.account = "other"  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("WitnessScope must be frozen")


def test_witness_order_carries_quantities() -> None:
    order = WitnessOrder(
        attempt_id="a1",
        broker_execution_id="exec-1",
        quantity=Decimal("10"),
        remaining=Decimal("0"),
        state=WitnessOrderState.FILLED,
    )
    assert order.quantity == Decimal("10")
    assert order.remaining == Decimal("0")


def test_ports_module_imports_no_os_environ_or_time() -> None:
    """Negative-grep: this package's ports carry no ambient env/clock reads.

    Checks actual imports/usages, not the module docstring's own prose (which
    legitimately mentions ``os.environ`` while disclaiming it).
    """
    source = inspect.getsource(ports)
    assert "import os" not in source
    assert "import time" not in source
    assert "time.time(" not in source
