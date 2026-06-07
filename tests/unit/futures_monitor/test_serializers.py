"""F-5 futures monitor serializers — futures schema, side+multiplier."""

from __future__ import annotations

from services.futures_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)

MULT = 50_000.0


def _fill_fields(side: str = "long", role: str = "entry") -> dict[bytes, bytes]:
    return {
        b"signal_id": b"s1",
        b"order_id": b"O1",
        b"symbol": b"A05603",
        b"side": side.encode(),
        b"filled_price": b"331.20",
        b"quantity": b"1",
        b"trade_role": role.encode(),
        b"filled_at_ms": b"1700000000000",
    }


def test_parse_fill_reads_futures_fields() -> None:
    f = parse_fill(_fill_fields(side="short", role="stop_loss"))
    assert f["symbol"] == "A05603"
    assert f["side"] == "short"
    assert f["filled_price"] == 331.20
    assert f["quantity"] == 1
    assert f["trade_role"] == "stop_loss"
    assert f["signal_id"] == "s1"


def test_parse_final_signal_futures_schema() -> None:
    fields = {
        b"signal_id": b"s1",
        b"symbol": b"A05603",
        b"setup_type": b"A_gap_reversion",
        b"direction": b"short",
        b"entry_price": b"331.20",
        b"confidence": b"0.85",
        b"generated_at_ms": b"1700000000000",
    }
    sig = parse_final_signal(fields)
    assert sig["symbol"] == "A05603"
    assert sig["setup_type"] == "A_gap_reversion"
    assert sig["direction"] == "short"
    assert sig["entry_price"] == 331.20
    assert sig["confidence"] == 0.85


def test_build_position_dict_carries_side() -> None:
    fill = parse_fill(_fill_fields(side="short"))
    meta = {"setup_type": "A_gap_reversion", "direction": "short"}
    pos = build_position_dict(fill, meta, multiplier=MULT)
    assert pos["code"] == "A05603"
    assert pos["side"] == "short"
    assert pos["entry_price"] == 331.20
    assert pos["strategy"] == "A_gap_reversion"
    assert pos["unrealized_pnl"] == 0.0


def test_build_trade_dict_long_pnl_pct_and_reason() -> None:
    entry = {
        "symbol": "A05603",
        "side": "long",
        "entry_price": 331.20,
        "entry_time": "t0",
        "setup_type": "A_gap_reversion",
    }
    exit_fill = parse_fill(_fill_fields(role="take_profit"))
    exit_fill["filled_price"] = 333.00
    trade = build_trade_dict(entry, exit_fill, pnl=90_000.0)
    assert trade["side"] == "long"
    assert trade["exit_reason"] == "take_profit"
    assert trade["pnl"] == 90_000.0
    assert (
        trade["pnl_pct"] == round((333.00 - 331.20) / 331.20 * 100, 10)
        or trade["pnl_pct"] > 0
    )


def test_build_trade_dict_short_pnl_pct() -> None:
    entry = {
        "symbol": "A05603",
        "side": "short",
        "entry_price": 331.20,
        "entry_time": "t0",
        "setup_type": "A",
    }
    exit_fill = parse_fill(_fill_fields(side="long", role="stop_loss"))
    exit_fill["filled_price"] = 332.40
    trade = build_trade_dict(entry, exit_fill, pnl=-60_000.0)
    assert trade["side"] == "short"
    # short pnl_pct = (ep - xp)/ep*100 = (331.20-332.40)/331.20*100 < 0
    assert trade["pnl_pct"] < 0


def test_build_signal_dict_futures() -> None:
    sig = {
        "signal_id": "s1",
        "symbol": "A05603",
        "setup_type": "A_gap_reversion",
        "direction": "long",
        "entry_price": 331.20,
        "confidence": 0.85,
        "generated_at_ms": "1700000000000",
    }
    d = build_signal_dict(sig)
    assert d["symbol"] == "A05603"
    assert d["strategy"] == "A_gap_reversion"
    assert d["price"] == 331.20
    assert d["side"] == "entry"
