"""The real position projection over a real boot's durable evidence (plan P4 §2, stage S2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos.dsl import PositionContext, PositionSide
from tos.engine import DecisionTickPayload, EngineEvent, EventKind
from tos.rcl import CapacityState
from tos_runtime.compose._riskstate_wiring import build_position_context_reader
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.riskstate.close_bound import DurableEntryCloseBoundReader
from tos_runtime.riskstate.position_context import (
    ENTRY_PRICE_BASIS_ORDER,
    EvidencePositionContextReader,
)

from . import _fixtures as fx
from .test_compose_root import _reach_trusted
from .test_flat_exit_held_quantity import (
    _approve_and_run,
    _boot_synthetic,
    _derived_quantity,
)
from .test_synthetic_venue_ledger_e2e import _close_runtime, _reservations
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_BAR_MS = 1
_ENTRY_SEQ = 0
_LATER_SEQ = 3
_LATER_CLOSE = fx.CROSSING_CLOSE + 4_499


def _reader(
    runtime, config_dir: Path, *, bar_interval_ms: int = _BAR_MS
) -> EvidencePositionContextReader:
    construction = fx.construction_config()
    projection = SqliteReservationProjectionReader(runtime.rcl_log)
    price_field_key = construction.price_field_key
    assert price_field_key is not None
    return build_position_context_reader(
        config_dir=config_dir,
        scheme=fx.SCHEME,
        construction=construction,
        evidence_store=runtime.evidence_store,
        inbox=runtime.inbox,
        projection=projection,
        close_bound_reader=DurableEntryCloseBoundReader(
            rcl_log=runtime.rcl_log,
            evidence_store=runtime.evidence_store,
            projection=projection,
            account=construction.account,
            instrument=construction.instrument,
        ).read,
        price_field_key=price_field_key,
        bar_interval_ms=bar_interval_ms,
    )


def _view(*, seq: int, close: int):
    event = fx.crossing_event(seq=seq, close=close)
    assert event.decision_tick is not None
    return event.decision_tick.value_view


def _tick_carrying(context: PositionContext, *, seq: int, close: int) -> EngineEvent:
    base = fx.crossing_event(seq=seq, close=close)
    assert base.decision_tick is not None
    payload = base.decision_tick
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=payload.instrument_key,
            capsule=payload.capsule,
            time=payload.time,
            reference=payload.reference,
            value_view=payload.value_view,
            position_context=context,
        ),
    )


def _stored_position_contexts(runtime) -> list[dict]:
    """Every admitted inbox row's ``position_context``, read back off the durable queue."""
    payloads = [
        json.loads(payload_json).get("decision_tick") or {}
        for (payload_json,) in runtime.inbox._conn.execute(  # noqa: SLF001
            "SELECT payload_json FROM events ORDER BY seq"
        ).fetchall()
    ]
    return [
        payload["position_context"]
        for payload in payloads
        if "position_context" in payload
    ]


def _seal_an_extra_unresolved_send(runtime) -> None:
    """Append one in-scope sealed send with no terminal result — a real ledger change."""
    runtime.evidence_store.append(
        {
            "kind": "SEND_SEALED",
            "attempt_id": "attempt-after-the-recorded-tick",
            "send_seal": {
                "attempt_id": "attempt-after-the-recorded-tick",
                "instrument_key": {
                    "account": fx.ACCOUNT,
                    "instrument": fx.INSTRUMENT,
                },
                "outbound_side": "SELL",
                "outbound_quantity": "1",
                "outbound_price": _LATER_CLOSE,
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )


def test_a_fresh_boot_with_no_entry_reads_as_proven_flat(
    config_dir_with_risk_state: Path, data_dir: Path, custody_root: Path
) -> None:
    """Nothing sealed, nothing reserved — the real reader proves FLAT, not UNKNOWN."""
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        context = _reader(runtime, config_dir_with_risk_state).read(
            _view(seq=_LATER_SEQ, close=_LATER_CLOSE)
        )
        assert context is not None
        assert context.side is PositionSide.FLAT
        assert context.held_qty == 0
    finally:
        _close_runtime(runtime)


def test_an_uncorroborated_entry_fill_leaves_the_namespace_absent(
    config_dir_with_risk_state: Path, data_dir: Path, custody_root: Path
) -> None:
    """With no independent witness the holding is not PROVEN — so nothing is published."""
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _discovery, entry = _approve_and_run(
            runtime, custody_root, fx.crossing_event(seq=_ENTRY_SEQ)
        )
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.COMMITTED_UNBOUND
        ], _reservations(runtime)
        assert (
            _reader(runtime, config_dir_with_risk_state).read(
                _view(seq=_LATER_SEQ, close=_LATER_CLOSE)
            )
            is None
        )
    finally:
        _close_runtime(runtime)


def test_a_filled_entry_projects_a_held_context_the_recorded_tick_then_keeps(
    config_dir_with_risk_state: Path, data_dir: Path, custody_root: Path
) -> None:
    """Entry -> fill -> held LONG at the entry's own limit price, +10 bp, three bars held."""
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _discovery, entry = _approve_and_run(
            runtime, custody_root, fx.crossing_event(seq=_ENTRY_SEQ)
        )
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(runtime)

        entry_quantity = _derived_quantity(runtime)
        reader = _reader(runtime, config_dir_with_risk_state)
        context = reader.read(_view(seq=_LATER_SEQ, close=_LATER_CLOSE))
        assert context is not None
        assert context.side is PositionSide.LONG
        assert context.held_qty == entry_quantity
        assert context.entry_price == fx.CROSSING_CLOSE
        assert context.entry_price_basis == ENTRY_PRICE_BASIS_ORDER
        assert context.unrealized == _LATER_CLOSE - fx.CROSSING_CLOSE
        assert context.unrealized_bp == 10
        assert context.bars_held == _LATER_SEQ - _ENTRY_SEQ

        event = _tick_carrying(context, seq=_LATER_SEQ, close=_LATER_CLOSE)
        (carried,) = runtime.run_once((event,))
        assert carried.pipeline is not None
        (recorded,) = _stored_position_contexts(runtime)
        assert recorded["canonical_digest"] == context.canonical_digest

        # SAFETY: the live ledger changes AFTER the tick and the recorded payload must not — that is the whole reason the context is computed before enqueue
        _seal_an_extra_unresolved_send(runtime)
        assert reader.read(_view(seq=_LATER_SEQ + 1, close=_LATER_CLOSE)) is None
        assert _stored_position_contexts(runtime) == [recorded]
    finally:
        _close_runtime(runtime)
