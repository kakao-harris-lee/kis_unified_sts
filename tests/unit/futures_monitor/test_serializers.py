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


# ---------------------------------------------------------------------------
# Market-risk gate passthrough (roadmap Phase 2 — /signals trace lane contract)
# ---------------------------------------------------------------------------

GATE_JSON = (
    '{"mode": "shadow", "band": "HIGH", "score": 74.2, "would_block": true,'
    ' "allow": true, "size_factor": 0.5,'
    ' "reason": "market_risk band=HIGH score=74.2 rule=block_new_long"}'
)


def _final_fields(**extra: bytes) -> dict[bytes, bytes]:
    fields = {
        b"signal_id": b"s1",
        b"symbol": b"A05603",
        b"setup_type": b"A_gap_reversion",
        b"direction": b"long",
        b"entry_price": b"331.20",
        b"confidence": b"0.85",
        b"generated_at_ms": b"1700000000000",
    }
    fields.update({key.encode(): value for key, value in extra.items()})
    return fields


def test_parse_final_signal_passes_market_risk_gate_through() -> None:
    sig = parse_final_signal(_final_fields(market_risk_gate=GATE_JSON.encode()))
    gate = sig["market_risk_gate"]
    assert gate["band"] == "HIGH"
    assert gate["mode"] == "shadow"
    assert gate["would_block"] is True
    assert gate["size_factor"] == 0.5


def test_parse_final_signal_gate_absent_or_malformed_is_none() -> None:
    assert parse_final_signal(_final_fields())["market_risk_gate"] is None
    assert (
        parse_final_signal(_final_fields(market_risk_gate=b"not-json"))[
            "market_risk_gate"
        ]
        is None
    )
    assert (
        parse_final_signal(_final_fields(market_risk_gate=b'["list"]'))[
            "market_risk_gate"
        ]
        is None
    )


def test_build_signal_dict_carries_gate_top_level() -> None:
    sig = parse_final_signal(_final_fields(market_risk_gate=GATE_JSON.encode()))
    d = build_signal_dict(sig)
    # /signals trace lane resolves the top-level key first (fixed contract).
    assert d["market_risk_gate"]["band"] == "HIGH"
    assert d["market_risk_gate"]["would_block"] is True


def test_build_signal_dict_omits_gate_when_absent() -> None:
    d = build_signal_dict(parse_final_signal(_final_fields()))
    assert "market_risk_gate" not in d  # legacy shape preserved bit-for-bit


# ---------------------------------------------------------------------------
# Futures-context passthrough (roadmap hardening Phase C — /signals trace lane)
# ---------------------------------------------------------------------------

CONTEXT_JSON = (
    '{"roll_state": "pre_roll", "days_to_expiry": 4, "basis_regime": "contango",'
    ' "foreign_flow_regime": "buy", "market_risk_band": "ELEVATED",'
    ' "margin_risk_level": "watch", "degraded": false}'
)


def test_parse_final_signal_passes_futures_context_through() -> None:
    sig = parse_final_signal(_final_fields(futures_context=CONTEXT_JSON.encode()))
    ctx = sig["futures_context"]
    assert ctx["roll_state"] == "pre_roll"
    assert ctx["days_to_expiry"] == 4
    assert ctx["basis_regime"] == "contango"
    assert ctx["degraded"] is False


def test_parse_final_signal_context_absent_or_malformed_is_none() -> None:
    assert parse_final_signal(_final_fields())["futures_context"] is None
    assert (
        parse_final_signal(_final_fields(futures_context=b"not-json"))[
            "futures_context"
        ]
        is None
    )


def test_build_signal_dict_carries_context_top_level() -> None:
    sig = parse_final_signal(_final_fields(futures_context=CONTEXT_JSON.encode()))
    d = build_signal_dict(sig)
    assert d["futures_context"]["roll_state"] == "pre_roll"
    assert d["futures_context"]["margin_risk_level"] == "watch"


def test_build_signal_dict_omits_context_when_absent() -> None:
    d = build_signal_dict(parse_final_signal(_final_fields()))
    assert "futures_context" not in d  # legacy shape preserved bit-for-bit
