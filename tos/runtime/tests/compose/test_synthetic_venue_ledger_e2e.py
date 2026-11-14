"""What the venue ledger actually changes on a synthetic tree, end to end (#1011 P2 §5 ⑤-⑦)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
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

from . import _fixtures as fx
from .conftest import approve_constructed_intent, write_approval_file
from .test_compose_root import _compose, _reach_trusted
from .test_synthetic_close_bound_inert import _hand_off_a_filled_entry
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

_BAND_ONLY_MAPPING = fx.band_reversion_strategy_mapping

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


def test_the_key_on_corroborates_the_synthetic_fill_and_opens_the_close(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """Approved OPEN -> hand-off -> idle, with the venue ledger on. Every inert assertion flips."""
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
    """The control: the SAME fixture, the SAME sequence, the key absent — still sealed."""
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


def test_a_venue_row_with_no_receipt_holds_the_scope_across_a_restart(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """A crash between the ledger write and the evidence write leaves an ORPHAN, and it holds."""
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
        expected_net = VenueLedgerReader(ledger_path).fills()[0].filled_quantity
        assert expected_net is not None
        assert snapshot.positions == ((instrument_key.instrument, expected_net * 2),)

        intents_before = len(_rows(second, "CAPACITY_RELEASE_INTENT"))
        for _ in range(3):
            second.run_once(())

        assert len(VenueLedgerReader(ledger_path).fills()) == 2
        assert len(_rows(second, "CAPACITY_RELEASE_INTENT")) == intents_before
        assert [state for _id, state in _reservations(second)] == [
            CapacityState.POSITION_CONSUMED
        ]
    finally:
        _close_runtime(second)


def test_a_resent_attempt_leaves_one_row_and_one_fill(tmp_path: Path) -> None:
    """review-1017 N1, pinned: one venue order per attempt, on any day."""
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
    assert fills[0].trading_date == "20261030"


def test_a_close_larger_than_the_proven_entry_is_refused(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """Entry q, CLOSE q+1 — refused by #1015's bound, which only the key ON ever reaches."""
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
    """A guard on the twin relationship itself."""
    assert _hand_off_a_filled_entry.__module__.endswith(
        "test_synthetic_close_bound_inert"
    )
    assert callable(write_approval_file)


def _entry_exit_mapping() -> dict[str, object]:
    """The suite's band-reversion strategy PLUS the exit rule below."""
    mapping = _BAND_ONLY_MAPPING()
    mapping["policy"]["rules"].append(_exit_rule())  # type: ignore[index]
    return mapping


def _exit_rule() -> dict[str, object]:
    """``close > upper_band`` -> close the long (the shipped setup-D trees' own shape)."""
    rationale = "close pierced the upper band — synthetic venue-ledger exit"
    return {
        "all_of": [
            {
                "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                "op": "GT",
                "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
            }
        ],
        "decision": {
            "kind": "ACTION",
            "rationale": rationale,
            "target": {
                "kind": "ACTION",
                "account": fx.ACCOUNT,
                "instrument": fx.INSTRUMENT,
                "direction": "SHORT",
                "position_effect": "CLOSE",
                "quantity_basis": "RISK",
                "edge_or_confidence": "venue-ledger-e2e",
                "rationale": rationale,
            },
        },
    }


def _boot_with_the_production_risk_service(
    config_dir: Path, data_dir: Path, custody_root: Path
):
    """Boot with the REAL step 6/7 risk-state service, not this suite's test providers."""
    fx.write_band_strategy_file(config_dir)
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )


def _approve_and_run(runtime, custody_root: Path, event):
    """Discover, write the operator approval for that exact proposal, then run it for real."""
    (discovery,) = runtime.run_once((event,))
    assert discovery.pipeline is not None and discovery.pipeline.proposal is not None
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=discovery.pipeline.proposal.canonical_digest,
    )
    (result,) = runtime.run_once((event,))
    return discovery, result


def test_the_whole_cycle_entry_close_and_a_fresh_entry_in_one_process(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The plan's completion condition on a synthetic tree: entry -> close -> next entry."""
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _boot_with_the_production_risk_service(
        config_dir_with_risk_state, data_dir, custody_root
    )
    assert runtime.risk_state is not None
    try:
        _reach_trusted(runtime)

        _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
        assert entry.flow is not None and entry.flow.handed_off is True
        for _ in range(3):
            runtime.run_once(())
        entry_rows = _reservations(runtime)
        assert [state for _id, state in entry_rows] == [
            CapacityState.POSITION_CONSUMED
        ], entry_rows
        entry_reservation_id = entry_rows[0][0]

        exit_tick = fx.crossing_event(seq=1, close=fx.UPPER_BAND + 1_000)
        discovery, exit_ = _approve_and_run(runtime, custody_root, exit_tick)
        proposal = discovery.pipeline.proposal
        assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
        assert exit_.flow is not None and exit_.flow.handed_off is True
        for _ in range(3):
            runtime.run_once(())

        instrument_key = runtime.context_resolver.instrument_key
        witness = runtime.venue_ledger.witness
        assert witness is not None
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert snapshot.positions == (), snapshot.positions
        assert snapshot.positions_complete is True

        after = dict(_reservations(runtime))
        assert set(after.values()) == {CapacityState.RELEASED}, after
        assert after[entry_reservation_id] is CapacityState.RELEASED

        scope_rows = SqliteReservationProjectionReader(
            runtime.rcl_log
        ).scope_reservations(instrument_key)
        assert outstanding_reservations(scope_rows) == ()
        assert verdict_for_scope("OPEN", scope_rows).outcome.value == "ADMIT"
        _, again = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=2))
        assert again.flow is not None and again.flow.handed_off is True
    finally:
        _close_runtime(runtime)
