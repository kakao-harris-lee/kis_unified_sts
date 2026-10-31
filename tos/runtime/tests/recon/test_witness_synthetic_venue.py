"""``SyntheticVenueLedgerWitness`` (plan 2026-10-31 §5 ②).

Four clauses: it is constructible with no evidence-store handle at all, it declares
``independent_of_evidence_store=True``, it ignores rows outside its scope, and a row it cannot
read makes it UNAVAILABLE rather than quietly smaller.

Every test reads a REAL ``venue_ledger.sqlite3`` written by the real store — a witness tested
against an in-memory double would prove nothing about the one property this class exists for
(which file it reads).
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from tos.engine import InstrumentKey
from tos_runtime.recon import witness_synthetic_venue as witness_module
from tos_runtime.recon.ports import (
    BrokerWitness,
    WitnessOrderState,
    WitnessScope,
    WitnessUnavailable,
)
from tos_runtime.recon.witness_synthetic_venue import SyntheticVenueLedgerWitness
from tos_runtime.venue_ledger.synthetic import SyntheticVenueLedger, VenueLedgerReader

TODAY = "20261031"
BUY = "BUY"
SELL = "SELL"
ACCOUNT = "acct-1"
INSTRUMENT = "101W12"
OTHER_INSTRUMENT = "101W03"


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "venue_ledger.sqlite3"


@pytest.fixture
def ledger(ledger_path: Path):
    instance = SyntheticVenueLedger(ledger_path)
    yield instance
    instance.close()


def _record(
    ledger: SyntheticVenueLedger,
    *,
    attempt_id: str,
    side: str,
    filled: str,
    account: str = ACCOUNT,
    instrument: str = INSTRUMENT,
    result_kind: str = "FULL_FILL",
    trading_date: str = TODAY,
) -> None:
    ledger.record(
        attempt_id=attempt_id,
        broker_execution_id=f"syn-exec:{attempt_id}:{result_kind}",
        account=account,
        instrument=instrument,
        side=side,
        quantity=Decimal(filled),
        filled_quantity=Decimal(filled),
        remaining_quantity=Decimal("0"),
        result_kind=result_kind,
        trading_date=trading_date,
    )


def _witness(path: Path, *, today: str | None = TODAY) -> SyntheticVenueLedgerWitness:
    return SyntheticVenueLedgerWitness(
        VenueLedgerReader(path),
        buy_side_token=BUY,
        sell_side_token=SELL,
        trading_date_now=lambda: today,
    )


def _scope(
    *, instruments: tuple[str, ...] = (INSTRUMENT,), attempts: tuple[str, ...] = ()
):
    return WitnessScope(
        account=ACCOUNT,
        instrument_keys=tuple(
            InstrumentKey(account=ACCOUNT, instrument=name) for name in instruments
        ),
        attempt_ids=attempts,
        as_of_generation=7,
    )


# ============================================================================
# ② clause 1 — no evidence-store handle, structurally
# ============================================================================


def test_the_constructor_accepts_no_evidence_store(ledger_path: Path) -> None:
    """Independent-review finding F2 made ``independent_of_evidence_store`` a field because the
    disclosure alone was not mechanical. Here the absence is in the signature: there is no
    parameter an evidence store could be passed through."""
    parameters = inspect.signature(SyntheticVenueLedgerWitness.__init__).parameters
    assert set(parameters) == {
        "self",
        "ledger",
        "buy_side_token",
        "sell_side_token",
        "trading_date_now",
        "provenance",
    }
    annotation = parameters["ledger"].annotation
    assert annotation in {VenueLedgerReader, "VenueLedgerReader"}


def test_the_module_never_imports_the_evidence_store() -> None:
    """Structural: a later edit cannot reach the evidence store through an import either.

    Reads the module's own import statements out of its AST rather than grepping the text, so
    the docstring may keep naming the package it deliberately does not import.
    """
    tree = ast.parse(inspect.getsource(witness_module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
    assert not any(
        name.startswith("tos_runtime.evidence") for name in imported
    ), imported
    assert not any("SqliteEvidenceStore" in name for name in imported), imported


def test_it_satisfies_the_broker_witness_port(ledger_path: Path) -> None:
    assert isinstance(_witness(ledger_path), BrokerWitness)


def test_equal_or_blank_side_tokens_are_refused(ledger_path: Path) -> None:
    for buy, sell in ((BUY, BUY), ("", SELL), (BUY, "   ")):
        with pytest.raises(ValueError):
            SyntheticVenueLedgerWitness(
                VenueLedgerReader(ledger_path),
                buy_side_token=buy,
                sell_side_token=sell,
                trading_date_now=lambda: TODAY,
            )


# ============================================================================
# ② clause 2 — independence + the snapshot's own axes
# ============================================================================


def test_the_snapshot_declares_independence_and_names_its_provenance(
    ledger, ledger_path: Path
) -> None:
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    snapshot = _witness(ledger_path).observe(_scope())

    assert snapshot.independent_of_evidence_store is True
    assert snapshot.provenance == "synthetic-venue-ledger"
    assert (
        snapshot.provenance != "synthetic-ledger"
    ), "never the store-derived witness's label"
    assert snapshot.positions_complete is True
    assert snapshot.positions == (("101W12", Decimal("1")),)
    assert snapshot.order_inquiry_date == TODAY
    assert snapshot.observed_at_generation == 7
    (order,) = snapshot.orders
    assert order.attempt_id == "a1"
    assert order.order_date == TODAY
    assert order.state is WitnessOrderState.FILLED
    assert (order.quantity, order.remaining) == (Decimal("1"), Decimal("0"))


def test_a_short_fill_nets_negative(ledger, ledger_path: Path) -> None:
    """Long/short symmetry: a SHORT entry fills the reducing side first and is still a held
    position — ``broker_position_flat`` checks ``quantity != 0``, not ``quantity > 0``.
    """
    _record(ledger, attempt_id="s1", side=SELL, filled="2")
    snapshot = _witness(ledger_path).observe(_scope())
    assert snapshot.positions == (("101W12", Decimal("-2")),)


def test_a_round_trip_nets_flat(ledger, ledger_path: Path) -> None:
    """Entry then exit: the net is zero, so the instrument is simply absent — which, with
    ``positions_complete=True``, is what proves flatness after a close (§3.3)."""
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _record(ledger, attempt_id="a2", side=SELL, filled="1")
    snapshot = _witness(ledger_path).observe(_scope())
    assert snapshot.positions == ()
    assert snapshot.positions_complete is True
    assert len(snapshot.orders) == 2


def test_non_fill_rows_do_not_move_the_net(ledger, ledger_path: Path) -> None:
    ledger.record(
        attempt_id="a1",
        broker_execution_id="syn-exec:a1:ACK",
        account=ACCOUNT,
        instrument=INSTRUMENT,
        side=BUY,
        quantity=Decimal("1"),
        filled_quantity=None,
        remaining_quantity=None,
        result_kind="ACK",
        trading_date=TODAY,
    )
    snapshot = _witness(ledger_path).observe(_scope())
    assert snapshot.positions == ()
    (order,) = snapshot.orders
    assert order.state is WitnessOrderState.ACKED


def test_an_unestablished_inquiry_date_does_not_make_the_witness_unavailable(
    ledger, ledger_path: Path
) -> None:
    """The join reads each order's own ``order_date``; ``order_inquiry_date`` is a record of the
    inquiry, and its own contract already allows ``None``."""
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    snapshot = _witness(ledger_path, today=None).observe(_scope())
    assert snapshot.order_inquiry_date is None
    assert snapshot.positions == (("101W12", Decimal("1")),)


# ============================================================================
# ② clause 3 — scope
# ============================================================================


def test_rows_for_another_instrument_are_ignored(ledger, ledger_path: Path) -> None:
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _record(ledger, attempt_id="b1", side=BUY, filled="5", instrument=OTHER_INSTRUMENT)
    snapshot = _witness(ledger_path).observe(_scope())
    assert snapshot.positions == (("101W12", Decimal("1")),)
    assert [order.attempt_id for order in snapshot.orders] == ["a1"]


def test_rows_for_another_account_are_ignored(ledger, ledger_path: Path) -> None:
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _record(ledger, attempt_id="z1", side=BUY, filled="9", account="acct-2")
    snapshot = _witness(ledger_path).observe(_scope())
    assert [order.attempt_id for order in snapshot.orders] == ["a1"]


def test_orders_are_never_filtered_down_to_the_scopes_attempt_ids(
    ledger, ledger_path: Path
) -> None:
    """A witness order the caller does not know about is the orphan the reconciliation is
    looking for (``WitnessScope``'s own contract) — filtering it away would make orphan
    detection structurally impossible."""
    _record(ledger, attempt_id="known", side=BUY, filled="1")
    _record(ledger, attempt_id="unknown", side=BUY, filled="1")
    snapshot = _witness(ledger_path).observe(_scope(attempts=("known",)))
    assert sorted(order.attempt_id or "" for order in snapshot.orders) == [
        "known",
        "unknown",
    ]


def test_an_empty_instrument_scope_covers_every_instrument_of_the_account(
    ledger, ledger_path: Path
) -> None:
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _record(ledger, attempt_id="b1", side=BUY, filled="2", instrument=OTHER_INSTRUMENT)
    snapshot = _witness(ledger_path).observe(_scope(instruments=()))
    assert snapshot.positions == (
        ("101W03", Decimal("2")),
        ("101W12", Decimal("1")),
    )


# ============================================================================
# ② clause 4 — a row it cannot read is UNAVAILABLE, never a smaller answer
# ============================================================================


def _raw_insert(path: Path, **columns: object) -> None:
    """Write a row straight through sqlite, bypassing the store's own validation.

    The only way to produce a malformed row: the table rejects UPDATE/DELETE outright, and
    :meth:`SyntheticVenueLedger.record` refuses every shape below by name.
    """
    row: dict[str, object] = {
        "trading_date": TODAY,
        "broker_execution_id": "syn-exec:x:FULL_FILL",
        "attempt_id": "x",
        "account": ACCOUNT,
        "instrument": INSTRUMENT,
        "side": BUY,
        "quantity": "1",
        "filled_quantity": "1",
        "remaining_quantity": "0",
        "result_kind": "FULL_FILL",
    }
    row.update(columns)
    conn = sqlite3.connect(str(path), isolation_level=None)
    try:
        conn.execute(
            f"INSERT INTO venue_results ({', '.join(row)}) "
            f"VALUES ({', '.join('?' for _ in row)})",
            tuple(row.values()),
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("filled_quantity", "not-a-decimal"),
        ("quantity", "1,000"),
        ("trading_date", "20261131"),
        ("attempt_id", ""),
        ("broker_execution_id", "   "),
        ("result_kind", ""),
        ("account", ""),
    ],
)
def test_a_row_this_witness_cannot_read_makes_it_unavailable(
    ledger, ledger_path: Path, column: str, value: object
) -> None:
    """Never a dropped row: a dropped fill reads as a SMALLER net than the venue holds, and a
    smaller net reads as flat — which is exactly what releases capacity."""
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _raw_insert(ledger_path, **{column: value})
    with pytest.raises(WitnessUnavailable):
        _witness(ledger_path).observe(_scope())


def test_a_fill_with_an_unknown_side_token_makes_the_witness_unavailable(
    ledger, ledger_path: Path
) -> None:
    """A fill whose direction cannot be signed cannot be netted — and an unsigned fill silently
    treated as zero would understate the position."""
    _raw_insert(ledger_path, side="LONG_OPEN")
    with pytest.raises(WitnessUnavailable, match="neither configured side token"):
        _witness(ledger_path).observe(_scope())


def test_a_fill_row_with_no_magnitude_makes_the_witness_unavailable(
    ledger_path,
) -> None:
    SyntheticVenueLedger(ledger_path).close()
    _raw_insert(ledger_path, filled_quantity=None)
    with pytest.raises(WitnessUnavailable, match="fill with no filled_quantity"):
        _witness(ledger_path).observe(_scope())


def test_a_missing_ledger_file_makes_the_witness_unavailable(tmp_path: Path) -> None:
    with pytest.raises(WitnessUnavailable):
        _witness(tmp_path / "absent.sqlite3").observe(_scope())


def test_a_corrupt_ledger_file_makes_the_witness_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "venue_ledger.sqlite3"
    path.write_bytes(b"this is not a sqlite database" * 32)
    with pytest.raises(WitnessUnavailable):
        _witness(path).observe(_scope())


def test_the_witness_never_writes(ledger, ledger_path: Path) -> None:
    """Read-only by construction: the reader opens ``mode=ro``."""
    _record(ledger, attempt_id="a1", side=BUY, filled="1")
    _witness(ledger_path).observe(_scope())
    conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO venue_results "
                "(trading_date, broker_execution_id, attempt_id, account, instrument, "
                "result_kind) VALUES ('20261031', 'x', 'x', 'x', 'x', 'ACK')"
            )
    finally:
        conn.close()
