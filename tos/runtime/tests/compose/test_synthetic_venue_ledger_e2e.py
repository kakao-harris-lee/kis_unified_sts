"""What the venue ledger actually changes on a synthetic tree, end to end (#1011 P2 §5 ⑤-⑦).

**The twin of ``test_synthetic_close_bound_inert.py``.** That file pins what a synthetic boot
does TODAY: the only witness it has re-reads the evidence store, so the release holds with
``WITNESS_NOT_INDEPENDENT``, the entry never reaches ``POSITION_CONSUMED``, #1015's durable
CLOSE bound stays inert and the scope seals at its first filled entry. It stays green, unchanged,
because it describes the key-OFF boot — which is every shipped tree.

This file is the same sequence with ``finality.yaml::witness: synthetic_venue_ledger`` set, and
every assertion is the OPPOSITE one. The pair differ in one YAML line and nothing else: the
control below (:func:`test_the_same_tree_with_the_key_off_still_seals`) runs on the SAME
``config_dir_with_risk_state`` fixture with the key absent, so the flip cannot be attributed to
the risk-state policies this fixture adds.

Hermetic: ``tmp_path`` only, no network, no ambient env (D1.4).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from tos.rcl import CapacityState
from tos_runtime.rcl.projection import (
    SqliteReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.risk.close_quantity import close_within_entry
from tos_runtime.risk.ledger_stages import verdict_for_scope
from tos_runtime.riskstate.close_bound import (
    CloseBoundRefusal,
    DurableEntryCloseBoundReader,
)
from tos_runtime.venue_ledger.synthetic import (
    VENUE_LEDGER_FILE_NAME,
    SyntheticVenueLedger,
    VenueLedgerReader,
)

from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted
from .test_synthetic_close_bound_inert import _hand_off_a_filled_entry
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _reservations(runtime) -> list[tuple[str, CapacityState]]:
    return [
        (reservation_id, state)
        for reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
    ]


def _rows(runtime, kind: str) -> list[dict]:
    return [
        json.loads(payload_json)["payload"]
        for (payload_json,) in runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        ).fetchall()
    ]


def _bound(runtime):
    """#1015's durable CLOSE bound, read against the very stores this boot owns."""
    instrument_key = runtime.context_resolver.instrument_key
    return DurableEntryCloseBoundReader(
        rcl_log=runtime.rcl_log,
        evidence_store=runtime.evidence_store,
        projection=SqliteReservationProjectionReader(runtime.rcl_log),
        account=instrument_key.account,
        instrument=instrument_key.instrument,
    ).read()


def _close_runtime(runtime) -> None:
    runtime.venue_ledger.close()
    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ===========================================================================
# ⑤ the flip — the same sequence, the opposite outcome
# ===========================================================================


def test_the_key_on_corroborates_the_synthetic_fill_and_opens_the_close(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """Approved OPEN -> hand-off -> idle, with the venue ledger on. Every inert assertion flips.

    Concrete input: the identical sequence
    ``test_synthetic_close_bound_inert.py::test_an_uncorroborated_synthetic_fill_...`` drives
    (one approved OPEN handed off, three idle passes), on a tree whose ``finality.yaml`` carries
    one more line. Concrete result:

    * the scope's ONE reservation is ``POSITION_CONSUMED``, not ``COMMITTED_UNBOUND``;
    * there is no ``WITNESS_NOT_INDEPENDENT`` hold — the release PROCEEDED, so a
      ``CAPACITY_RELEASE_INTENT`` to ``POSITION_CONSUMED`` is on record instead;
    * :meth:`DurableEntryCloseBoundReader.read` is PROVEN with the entry's own quantity, where
      it refused with ``ENTRY_NOT_SOLE_CONSUMED_POSITION``;
    * step 8 ADMITs a CLOSE over that one consumed position (and still DENIES a second OPEN,
      which is correct: the position is open).
    * the venue ledger holds exactly one row for the attempt, and the witness nets it.
    """
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)

        rows = _reservations(runtime)
        assert len(rows) == 1, rows
        assert rows[0][1] is CapacityState.POSITION_CONSUMED, rows

        held = _rows(runtime, "CAPACITY_RELEASE_HELD")
        assert [row["reason"] for row in held] == [], held
        intents = _rows(runtime, "CAPACITY_RELEASE_INTENT")
        assert [row["destination"] for row in intents] == ["POSITION_CONSUMED"], intents

        # The entry's own derived quantity — read off step 2, never a constant retyped here
        # (this fixture's band strategy sizes from its own risk inputs).
        construction = runtime.construction_stage.construction
        assert construction is not None
        entry_quantity = construction.derivation.quantity

        bound = _bound(runtime)
        assert bound.proven is True, bound.refusal
        assert bound.entry_quantity == entry_quantity
        assert bound.prior_closed == Decimal("0")

        instrument_key = runtime.context_resolver.instrument_key
        scope_rows = SqliteReservationProjectionReader(
            runtime.rcl_log
        ).scope_reservations(instrument_key)
        assert len(outstanding_reservations(scope_rows)) == 1
        assert verdict_for_scope("CLOSE", scope_rows).outcome.value == "ADMIT"
        assert verdict_for_scope("OPEN", scope_rows).outcome.value == "DENY"

        # The venue's own record, and what the witness makes of it.
        witness = runtime.venue_ledger.witness
        assert witness is not None
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert len(snapshot.orders) == 1
        assert snapshot.positions == ((instrument_key.instrument, entry_quantity),)
        assert snapshot.positions_complete is True
        assert snapshot.independent_of_evidence_store is True
    finally:
        _close_runtime(runtime)


def test_the_same_tree_with_the_key_off_still_seals(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """The control: the SAME fixture, the SAME sequence, the key absent — still sealed.

    Without this, the flip above could be attributed to the two governed risk-state policies
    ``config_dir_with_risk_state`` adds (which the inert test's own ``config_dir`` lacks). With
    it, the pair differ in exactly one YAML line.
    """
    runtime = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)

        rows = _reservations(runtime)
        assert len(rows) == 1, rows
        assert rows[0][1] is CapacityState.COMMITTED_UNBOUND, rows
        assert [row["reason"] for row in _rows(runtime, "CAPACITY_RELEASE_HELD")] == [
            "WITNESS_NOT_INDEPENDENT"
        ]
        assert _bound(runtime).refusal == (
            CloseBoundRefusal.ENTRY_NOT_SOLE_CONSUMED_POSITION.value
        )
        assert not (data_dir / VENUE_LEDGER_FILE_NAME).exists()
    finally:
        _close_runtime(runtime)


# ===========================================================================
# ⑥ the crash window — a venue row the evidence store never learned about
# ===========================================================================


def test_a_venue_row_with_no_receipt_holds_the_scope_across_a_restart(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """A crash between the ledger write and the evidence write leaves an ORPHAN, and it holds.

    This is §3.4's first catch, and the one the store-derived witness is structurally unable to
    see: it reads the evidence store, so a fill the evidence store never learned about simply
    does not exist for it.

    Concrete input: a corroborated entry (as above), then ONE more row appended through the
    real :meth:`SyntheticVenueLedger.record` — exactly the durable state
    ``RecordingSyntheticTransport`` leaves when the process dies after its write and before the
    gateway's evidence write. Then a RESTART on the same directories. Concrete result: the
    restarted boot's witness reports TWO orders and TWICE the entry's net for a scope whose
    evidence store knows one fill; the entry's reservation does not advance and no further
    release intent is
    recorded; and the ledger still holds exactly two rows — the boot replay re-sends nothing,
    so no duplicate fill is created.
    """
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    ledger_path = data_dir / VENUE_LEDGER_FILE_NAME

    first = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(first)
        _hand_off_a_filled_entry(first, custody_root)
        instrument_key = first.context_resolver.instrument_key
        assert [state for _id, state in _reservations(first)] == [
            CapacityState.POSITION_CONSUMED
        ]
        seal = _rows(first, "SEND_SEALED")[-1]["send_seal"]
        side = seal["outbound_side"]
        entry = VenueLedgerReader(ledger_path).fills()[0]
        trading_date = entry.trading_date
        entry_quantity = entry.filled_quantity
        assert entry_quantity is not None
        # The crash window, written through the very method the transport calls.
        first.venue_ledger.ledger.record(
            attempt_id="attempt-crashed-before-evidence",
            broker_execution_id="syn-exec:attempt-crashed-before-evidence:FULL_FILL",
            account=instrument_key.account,
            instrument=instrument_key.instrument,
            side=side,
            quantity=entry_quantity,
            filled_quantity=entry_quantity,
            remaining_quantity=Decimal("0"),
            result_kind="FULL_FILL",
            trading_date=trading_date,
        )
    finally:
        _close_runtime(first)

    second = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(second)
        instrument_key = second.context_resolver.instrument_key
        witness = second.venue_ledger.witness
        assert witness is not None
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert len(snapshot.orders) == 2
        # Twice the entry: the venue executed two fills, the evidence store recorded one.
        expected_net = VenueLedgerReader(ledger_path).fills()[0].filled_quantity
        assert expected_net is not None
        assert snapshot.positions == ((instrument_key.instrument, expected_net * 2),)

        intents_before = len(_rows(second, "CAPACITY_RELEASE_INTENT"))
        for _ in range(3):
            second.run_once(())

        # No duplicate fill: the restart re-sent nothing, so the venue still holds two rows.
        assert len(VenueLedgerReader(ledger_path).fills()) == 2
        # And nothing was released on the strength of an order nothing can account for.
        assert len(_rows(second, "CAPACITY_RELEASE_INTENT")) == intents_before
        assert [state for _id, state in _reservations(second)] == [
            CapacityState.POSITION_CONSUMED
        ]
    finally:
        _close_runtime(second)


def test_a_resent_attempt_leaves_one_row_and_one_fill(tmp_path: Path) -> None:
    """review-1017 N1, pinned: one venue order per attempt, on any day.

    ``ReconciliationService`` keeps only the LAST witness order per ``attempt_id`` and silently
    drops the rest, so a transport that produced two rows for one attempt would have one of them
    read and the other invisible. The venue ledger's identity is ``broker_execution_id`` ALONE
    (review-1017 L1), so a re-send of the same deterministic attempt — on the same trading date
    or a later one — recognizes the row rather than appending a second.

    Concrete input: the same ``(attempt, broker_execution_id)`` recorded twice with DIFFERENT
    ``trading_date`` values. Concrete result: ``record`` reports ``False`` (already there), the
    file holds one row, and the witness nets ONE fill rather than two.
    """
    path = tmp_path / VENUE_LEDGER_FILE_NAME
    ledger = SyntheticVenueLedger(path)
    try:

        def _record(trading_date: str) -> bool:
            return ledger.record(
                attempt_id="attempt-resent",
                broker_execution_id="syn-exec:attempt-resent:FULL_FILL",
                account="acct-vl",
                instrument="101W12",
                side="BUY",
                quantity=Decimal("1"),
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
                result_kind="FULL_FILL",
                trading_date=trading_date,
            )

        assert _record("20261030") is True
        assert _record("20261031") is False
    finally:
        ledger.close()

    fills = VenueLedgerReader(path).fills()
    assert len(fills) == 1
    assert [fill.attempt_id for fill in fills] == ["attempt-resent"]
    assert fills[0].trading_date == "20261030"  # the FIRST recorded date, append-only


# ===========================================================================
# ⑦ over-close — the bound the flip brings to life refuses a close larger than the entry
# ===========================================================================


def test_a_close_larger_than_the_proven_entry_is_refused(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """Entry q, CLOSE q+1 — refused by #1015's bound, which only the key ON ever reaches.

    The bound is what step 6 rests a synthetic CLOSE on
    (``CloseAuthoritySource.DURABLE_EVIDENCE``, wired from the transport kind by
    ``compose/root.py::_close_authority_for``). Read against the very stores this boot owns, it
    proves ``entry_quantity=1, prior_closed=0``; the predicate step 6 applies to it then admits
    a close of 1 and refuses a close of 2. On the key-OFF tree this never runs at all, because
    the bound refuses with ``ENTRY_NOT_SOLE_CONSUMED_POSITION`` before any quantity is read.

    The venue's own record agrees: its net position is exactly the entry, so a close of one
    unit more cannot be explained by anything the venue actually executed.
    """
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)

        construction = runtime.construction_stage.construction
        assert construction is not None
        entry_quantity = construction.derivation.quantity

        bound = _bound(runtime)
        assert bound.proven is True and bound.entry_quantity == entry_quantity
        # Closing the whole entry fits; one unit more does not.
        assert (
            close_within_entry(bound.entry_quantity, bound.prior_closed, entry_quantity)
            is True
        )
        assert (
            close_within_entry(
                bound.entry_quantity, bound.prior_closed, entry_quantity + 1
            )
            is False
        )

        instrument_key = runtime.context_resolver.instrument_key
        witness = runtime.venue_ledger.witness
        assert witness is not None
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert snapshot.positions == ((instrument_key.instrument, entry_quantity),)
    finally:
        _close_runtime(runtime)


def test_the_approval_helper_is_the_one_the_inert_twin_uses() -> None:
    """A guard on the twin relationship itself.

    Both files drive the entry through the SAME helper
    (``test_synthetic_close_bound_inert._hand_off_a_filled_entry``), so a change to how an
    entry is approved and handed off cannot make one of the pair describe a different sequence
    from the other without the import failing here first.
    """
    assert _hand_off_a_filled_entry.__module__.endswith(
        "test_synthetic_close_bound_inert"
    )
    assert callable(write_approval_file)
