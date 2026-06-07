"""F-5 futures monitor positions hash codec."""

from __future__ import annotations

from services.futures_monitor.positions import (
    build_position_record,
    parse_futures_position_record,
)


def test_round_trip() -> None:
    state = {
        "symbol": "A05603",
        "side": "short",
        "entry_price": 331.20,
        "quantity": 2,
        "opened_at_ms": 1700000000000,
        "setup_type": "A",
        "signal_id": "s1",
        "high_water": 332.0,
        "low_water": 330.0,
    }
    raw = build_position_record(state)
    rec = parse_futures_position_record(raw.encode())
    assert rec is not None
    assert rec["symbol"] == "A05603"
    assert rec["side"] == "short"
    assert rec["entry_price"] == 331.20
    assert rec["quantity"] == 2


def test_foreign_record_skipped_missing_opened_at() -> None:
    # orchestrator-style record (no opened_at_ms) → None
    assert (
        parse_futures_position_record(b'{"symbol": "A05603", "entry_time": "x"}')
        is None
    )


def test_missing_symbol_skipped() -> None:
    assert parse_futures_position_record(b'{"opened_at_ms": 1}') is None


def test_invalid_json_returns_none() -> None:
    assert parse_futures_position_record(b"not json") is None
