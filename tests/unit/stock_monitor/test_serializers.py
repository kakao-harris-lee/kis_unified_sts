"""Pure parse + dashboard dict builders for the stock monitor bridge."""

from __future__ import annotations

from services.stock_monitor.serializers import (
    build_position_dict,
    build_signal_dict,
    build_trade_dict,
    parse_fill,
    parse_final_signal,
)


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _fill(
    role: str = "entry", side: str = "BUY", price: str = "71000.0"
) -> dict[bytes, bytes]:
    return _enc(
        {
            "signal_id": "sig-1",
            "order_id": "VO-1",
            "symbol": "005930",
            "side": side,
            "order_type": "market",
            "requested_price": price,
            "filled_price": price,
            "tick_size_points": "0.0",
            "slippage_ticks": "0.0",
            "quantity": "10",
            "requested_at_ms": "1700000000000",
            "filled_at_ms": "1700000000000",
            "latency_ms": "0",
            "venue": "KRX",
            "trade_role": role,
            "broker_error_code": "",
        }
    )


def _final() -> dict[bytes, bytes]:
    return _enc(
        {
            "signal_id": "sig-1",
            "code": "005930",
            "name": "삼성전자",
            "strategy": "vr_composite",
            "direction": "long",
            "price": "71000.0",
            "quantity": "10",
            "confidence": "0.62",
            "generated_at_ms": "1700000000000",
            "metadata_json": "{}",
            "size_multiplier": "1.0",
            "filtered_at_ms": "1700000000000",
        }
    )


def test_parse_fill() -> None:
    f = parse_fill(_fill(role="entry"))
    assert f["code"] == "005930" and f["trade_role"] == "entry"
    assert f["filled_price"] == 71000.0 and f["quantity"] == 10
    assert f["signal_id"] == "sig-1"


def test_parse_final_signal() -> None:
    s = parse_final_signal(_final())
    assert s["code"] == "005930" and s["strategy"] == "vr_composite"
    assert s["name"] == "삼성전자" and s["direction"] == "long"


def test_build_position_dict_enriches_from_meta() -> None:
    f = parse_fill(_fill(role="entry"))
    meta = {"strategy": "vr_composite", "name": "삼성전자"}
    p = build_position_dict(f, meta, fee_rate=0.003)
    assert p["id"] == "005930" and p["code"] == "005930"
    assert p["strategy"] == "vr_composite" and p["name"] == "삼성전자"
    assert p["side"] == "long" and p["quantity"] == 10
    assert p["entry_price"] == 71000.0 and p["current_price"] == 71000.0
    assert p["unrealized_pnl"] == 0.0 and p["state"] == "survival"
    assert p["fee_rate"] == 0.003
    assert isinstance(p["entry_time"], str) and p["entry_time"]


def test_build_position_dict_missing_meta_graceful() -> None:
    f = parse_fill(_fill(role="entry"))
    p = build_position_dict(f, {}, fee_rate=0.003)
    assert p["strategy"] == "" and p["name"] == ""


def test_build_trade_dict_pnl() -> None:
    entry = {
        "code": "005930",
        "name": "삼성전자",
        "strategy": "vr_composite",
        "entry_price": 71000.0,
        "entry_time": "2023-11-14T22:13:20+00:00",
    }
    exit_fill = parse_fill(_fill(role="exit", side="SELL", price="73000.0"))
    t = build_trade_dict(entry, exit_fill, pnl=17840.0)
    assert t["symbol"] == "005930" and t["side"] == "long"
    assert t["entry_price"] == 71000.0 and t["exit_price"] == 73000.0
    assert t["pnl"] == 17840.0
    assert round(t["pnl_pct"], 4) == round((73000 - 71000) / 71000 * 100, 4)
    assert t["strategy"] == "vr_composite" and t["exit_reason"] == "exit"


def test_build_signal_dict() -> None:
    s = build_signal_dict(parse_final_signal(_final()))
    assert s["symbol"] == "005930" and s["strategy"] == "vr_composite"
    assert s["side"] == "entry" and s["signal_type"] == "entry"
    assert s["confidence"] == 0.62 and s["executed"] is True
    assert isinstance(s["timestamp"], str) and s["timestamp"]


def test_parse_fill_empty_defaults() -> None:
    f = parse_fill({})
    assert f["code"] == "" and f["filled_price"] == 0.0 and f["quantity"] == 0
