"""``RecordingSyntheticTransport`` + the venue ledger store (plan 2026-10-31 §5 ①).

Three clauses, each pinned mechanically rather than by reading the code:

1. the row is durably committed BEFORE the result is returned — a spy ledger opens a SECOND,
   independent read-only connection from inside ``record`` and sees the committed row there,
   and an AST pin keeps the ``record`` call ahead of the ``return``;
2. a write that fails returns no result at all — the exception leaves ``send_once`` and the
   inner transport is never asked a second time;
3. re-sending the same attempt leaves ONE row and creates no second fill.
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
import stat
import textwrap
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.brokeradapter import (
    SyntheticFillPolicy,
    SyntheticPaperTransport,
    Transport,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import gateway as gateway_module
from tos.engine import (
    AttemptRequest,
    EgressResultKind,
    InstrumentKey,
    build_attempt_request,
)
from tos.ordering import OrderingEvent
from tos_runtime.venue_ledger.synthetic import (
    RecordingSyntheticTransport,
    SyntheticVenueLedger,
    VenueLedgerReader,
    VenueLedgerWriteFailed,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
TODAY = "20261031"
BUY = "BUY"
SELL = "SELL"
ACCOUNT = "acct-1"
INSTRUMENT = "101W12"


def _attempt(sequence: int = 1) -> AttemptRequest:
    return build_attempt_request(
        conformance_proof_digest=f"proof-{sequence}",
        action_flow_permit_identity=f"permit-{sequence}",
        reference=OrderingEvent(
            event_id=f"ev-{sequence}", quorum_commit_index=sequence
        ),
        scheme=SCHEME,
    )


def _key() -> InstrumentKey:
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def _full_fill_transport() -> SyntheticPaperTransport:
    return SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=Decimal("1"))
    )


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "venue_ledger.sqlite3"


@pytest.fixture
def ledger(ledger_path: Path):
    instance = SyntheticVenueLedger(ledger_path)
    yield instance
    instance.close()


def _send(
    transport: RecordingSyntheticTransport,
    *,
    attempt: AttemptRequest | None = None,
    quantity: Decimal | None = Decimal("1"),
    side: str | None = BUY,
):
    return transport.send_once(
        attempt or _attempt(),
        instrument_key=_key(),
        coordinates=(("endpoint", "synthetic://paper"), ("account", ACCOUNT)),
        quantity=quantity,
        price=Decimal("300"),
        side=side,
    )


# ============================================================================
# Protocol conformance + the file itself
# ============================================================================


def test_the_wrapper_still_satisfies_the_kernel_transport_protocol(ledger) -> None:
    transport = RecordingSyntheticTransport(
        _full_fill_transport(), ledger, trading_date_now=lambda: TODAY
    )
    assert isinstance(transport, Transport)


def test_the_wrapper_signature_matches_the_kernel_transport_signature(ledger) -> None:
    """A wrapper that quietly grew a retry count or an idempotency key would be a different
    contract from the single-shot one the kernel Protocol seals (design #34 §5.4)."""
    assert inspect.signature(
        RecordingSyntheticTransport.send_once
    ) == inspect.signature(Transport.send_once)


def test_the_ledger_file_is_0600_and_in_wal(ledger, ledger_path: Path) -> None:
    assert stat.S_IMODE(ledger_path.stat().st_mode) == 0o600
    conn = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        (mode,) = conn.execute("PRAGMA journal_mode").fetchone()
    finally:
        conn.close()
    assert mode.lower() == "wal"


def test_the_ledger_is_a_different_file_from_the_evidence_and_rcl_stores(
    ledger_path: Path,
) -> None:
    """The whole independence claim is "a different file" (plan §3.1)."""
    assert ledger_path.name == "venue_ledger.sqlite3"
    assert ledger_path.name not in {"evidence.sqlite3", "rcl.sqlite3"}


def test_the_venue_results_table_rejects_update_and_delete(ledger, ledger_path) -> None:
    """Append-only, mechanically — a venue's record of what it executed is not editable."""
    _send(
        RecordingSyntheticTransport(
            _full_fill_transport(), ledger, trading_date_now=lambda: TODAY
        )
    )
    conn = sqlite3.connect(str(ledger_path), isolation_level=None)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE venue_results SET instrument = 'OTHER'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM venue_results")
    finally:
        conn.close()


# ============================================================================
# ① clause 1 — the row is committed before the result is returned
# ============================================================================


class _ObservingLedger(SyntheticVenueLedger):
    """Reads the ledger file back through an INDEPENDENT connection inside ``record``.

    Whatever this sees was already committed at the instant ``record`` returned — which is
    strictly before ``send_once`` can return, since ``send_once`` has not resumed yet.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.seen_from_another_connection: list[int] = []

    def record(self, **fields: Any) -> bool:
        written = super().record(**fields)
        self.seen_from_another_connection.append(
            len(VenueLedgerReader(self.path).fills())
        )
        return written


def test_the_row_is_committed_before_the_result_is_returned(ledger_path: Path) -> None:
    observing = _ObservingLedger(ledger_path)
    try:
        transport = RecordingSyntheticTransport(
            _full_fill_transport(), observing, trading_date_now=lambda: TODAY
        )
        result = _send(transport)
    finally:
        observing.close()

    assert observing.seen_from_another_connection == [1]
    assert result.kind is EgressResultKind.FULL_FILL
    rows = VenueLedgerReader(ledger_path).fills()
    assert len(rows) == 1
    row = rows[0]
    assert row.attempt_id == result.attempt_id
    assert row.broker_execution_id == result.broker_execution_id
    assert (row.account, row.instrument, row.side) == (ACCOUNT, INSTRUMENT, BUY)
    assert (row.quantity, row.filled_quantity, row.remaining_quantity) == (
        Decimal("1"),
        Decimal("1"),
        Decimal("0"),
    )
    assert (row.result_kind, row.trading_date) == ("FULL_FILL", TODAY)


def test_send_once_records_before_it_returns_the_result() -> None:
    """AST pin: the ledger write statement precedes the ``return`` in ``send_once``'s body.

    An ordering a reader has to infer from indentation is exactly the kind that regresses
    silently; this fails the instant the write moves after the return.
    """
    source = textwrap.dedent(inspect.getsource(RecordingSyntheticTransport.send_once))
    tree = ast.parse(source)
    (function,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    record_line = next(
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Attribute) and node.attr == "record"
    )
    return_line = next(
        node.lineno for node in function.body if isinstance(node, ast.Return)
    )
    assert record_line < return_line


# ============================================================================
# ① clause 2 — a write that fails returns no result
# ============================================================================


def test_a_refused_ledger_write_returns_no_result(ledger, ledger_path: Path) -> None:
    """A real sqlite failure (the store's connection is gone), not a stubbed exception."""
    inner = _full_fill_transport()
    transport = RecordingSyntheticTransport(
        inner, ledger, trading_date_now=lambda: TODAY
    )
    ledger.close()

    with pytest.raises(VenueLedgerWriteFailed):
        _send(transport)

    assert VenueLedgerReader(ledger_path).fills() == ()
    # The send itself happened exactly once — a failed record is never a reason to resend.
    assert len(inner.requests) == 1


def test_an_unestablished_trading_date_is_a_write_failure(ledger, ledger_path) -> None:
    """Unlike ``KisMockTransport._stamp_trading_date``, which degrades to ``None``: there the
    broker is the independent record, here the row IS the record and an undated one has no
    identity and no join key."""
    transport = RecordingSyntheticTransport(
        _full_fill_transport(), ledger, trading_date_now=lambda: None
    )
    with pytest.raises(VenueLedgerWriteFailed, match="trading_date"):
        _send(transport)
    assert VenueLedgerReader(ledger_path).fills() == ()


def test_a_malformed_trading_date_is_a_write_failure(ledger, ledger_path) -> None:
    transport = RecordingSyntheticTransport(
        _full_fill_transport(), ledger, trading_date_now=lambda: "20261131"
    )
    with pytest.raises(VenueLedgerWriteFailed, match="trading_date"):
        _send(transport)
    assert VenueLedgerReader(ledger_path).fills() == ()


def test_a_raising_trading_date_source_is_a_write_failure(ledger, ledger_path) -> None:
    def _boom() -> str:
        raise RuntimeError("time service down")

    transport = RecordingSyntheticTransport(
        _full_fill_transport(), ledger, trading_date_now=_boom
    )
    with pytest.raises(VenueLedgerWriteFailed, match="RuntimeError"):
        _send(transport)
    assert VenueLedgerReader(ledger_path).fills() == ()


def test_the_write_failure_reaches_the_gateways_transport_raised_path(ledger) -> None:
    """``VenueLedgerWriteFailed`` is an ordinary ``Exception``, which is what the egress
    gateway catches to record ``SendHaltReason.TRANSPORT_RAISED`` — this module invents no new
    halt reason, it raises into the existing "venue may have acted, no response" one."""
    assert issubclass(VenueLedgerWriteFailed, Exception)
    gateway_source = inspect.getsource(gateway_module)
    assert "SendHaltReason.TRANSPORT_RAISED" in gateway_source
    assert "a missing acknowledgement is NOT a non-acceptance" in gateway_source


# ============================================================================
# ① clause 3 — a re-send leaves one row and no second fill
# ============================================================================


def test_resending_the_same_attempt_leaves_one_row_and_returns_the_same_result(
    ledger, ledger_path: Path
) -> None:
    inner = _full_fill_transport()
    transport = RecordingSyntheticTransport(
        inner, ledger, trading_date_now=lambda: TODAY
    )
    attempt = _attempt()

    first = _send(transport, attempt=attempt)
    second = _send(transport, attempt=attempt)

    rows = VenueLedgerReader(ledger_path).fills()
    assert len(rows) == 1, "the venue holds ONE execution for one deterministic attempt"
    assert second == first
    # The byte-identical result is what the kernel's own DUPLICATE detection keys on
    # (ProvisionalReservationLedger.apply_egress_result), so the engine refuses to apply it a
    # second time. Returning a DIFFERENT result here would escape that guard.
    assert second.broker_execution_id == first.broker_execution_id
    assert second.filled_quantity == first.filled_quantity


def test_a_second_attempt_gets_its_own_row(ledger, ledger_path: Path) -> None:
    """The deduplication is per execution identity, never "one row per instrument"."""
    transport = RecordingSyntheticTransport(
        _full_fill_transport(), ledger, trading_date_now=lambda: TODAY
    )
    _send(transport, attempt=_attempt(1))
    _send(transport, attempt=_attempt(2))
    assert (
        len({row.broker_execution_id for row in VenueLedgerReader(ledger_path).fills()})
        == 2
    )


def test_a_different_result_under_the_same_identity_is_refused(ledger) -> None:
    """A UNIQUE hit means "already at the venue" only when the recorded row is the same row.

    A different magnitude under an identity the venue already used is not a re-send — this is
    §3.4's "driver re-injected a wrong result", caught at the venue boundary.
    """
    common = {
        "attempt_id": "a1",
        "broker_execution_id": "syn-exec:a1:FULL_FILL",
        "account": ACCOUNT,
        "instrument": INSTRUMENT,
        "side": BUY,
        "quantity": Decimal("1"),
        "remaining_quantity": Decimal("0"),
        "result_kind": "FULL_FILL",
        "trading_date": TODAY,
    }
    assert ledger.record(filled_quantity=Decimal("1"), **common) is True
    assert ledger.record(filled_quantity=Decimal("1"), **common) is False
    with pytest.raises(VenueLedgerWriteFailed, match="DIFFERENT recorded result"):
        ledger.record(filled_quantity=Decimal("2"), **common)


def test_the_same_execution_id_on_another_day_is_another_row(
    ledger, ledger_path
) -> None:
    """Identity is the PAIR — the same per-day-sequence discipline the KIS ODNO join uses."""
    common = {
        "attempt_id": "a1",
        "broker_execution_id": "syn-exec:a1:FULL_FILL",
        "account": ACCOUNT,
        "instrument": INSTRUMENT,
        "side": BUY,
        "quantity": Decimal("1"),
        "filled_quantity": Decimal("1"),
        "remaining_quantity": Decimal("0"),
        "result_kind": "FULL_FILL",
    }
    assert ledger.record(trading_date="20261030", **common) is True
    assert ledger.record(trading_date=TODAY, **common) is True
    assert len(VenueLedgerReader(ledger_path).fills()) == 2


# ============================================================================
# Row-level refusals
# ============================================================================


def test_a_result_without_an_execution_id_is_not_recordable(ledger) -> None:
    """The kernel's synthetic transport stamps one on every result, so this never fires in
    practice — but a row without an identity could be neither deduplicated nor joined.
    """
    with pytest.raises(VenueLedgerWriteFailed, match="broker_execution_id"):
        ledger.record(
            attempt_id="a1",
            broker_execution_id=None,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            side=BUY,
            quantity=Decimal("1"),
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
            result_kind="FULL_FILL",
            trading_date=TODAY,
        )


def test_a_non_fill_result_is_recorded_too(ledger, ledger_path: Path) -> None:
    """An ACK is equally a thing the venue did; leaving it out would make silence ambiguous."""
    inner = SyntheticPaperTransport(
        SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    )
    transport = RecordingSyntheticTransport(
        inner, ledger, trading_date_now=lambda: TODAY
    )
    _send(transport)
    (row,) = VenueLedgerReader(ledger_path).fills()
    assert row.result_kind == "ACK"
    assert row.filled_quantity is None


def test_a_symlinked_ledger_path_is_refused(tmp_path: Path) -> None:
    """``O_NOFOLLOW``: the ledger is a file this process owns at 0600, never a pointer
    somewhere else."""
    real = tmp_path / "elsewhere.sqlite3"
    real.touch()
    link = tmp_path / "venue_ledger.sqlite3"
    link.symlink_to(real)
    with pytest.raises(VenueLedgerWriteFailed, match="mode 0600"):
        SyntheticVenueLedger(link)
