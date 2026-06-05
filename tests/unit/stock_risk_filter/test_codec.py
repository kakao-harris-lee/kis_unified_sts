"""Round-trip: M4-P stock_signal_to_stream_dict -> stock_signal_from_stream_fields."""

from __future__ import annotations

from datetime import UTC, datetime

from services.stock_risk_filter.codec import (
    StockRiskSignal,
    stock_signal_from_stream_fields,
)


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def test_parses_m4p_candidate_fields():
    raw = {
        "signal_id": "abc123",
        "code": "005930",
        "name": "삼성전자",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": str(
            int(datetime(2026, 6, 5, 4, 0, tzinfo=UTC).timestamp() * 1000)
        ),
        "metadata_json": "{}",
    }
    signal_id, sig = stock_signal_from_stream_fields(_encode(raw))
    assert signal_id == "abc123"
    assert isinstance(sig, StockRiskSignal)
    assert sig.symbol == "005930"
    assert sig.code == "005930"
    assert sig.generated_at is not None
    assert sig.generated_at.tzinfo is not None
    assert sig.direction == "long"
    assert sig.price == 71000.0
    assert sig.quantity == 10
    assert sig.confidence == 0.62


def test_missing_direction_defaults_long():
    raw = {
        "signal_id": "x",
        "code": "000660",
        "name": "",
        "strategy": "s",
        "direction": "",
        "price": "50000",
        "quantity": "1",
        "confidence": "0.5",
        "generated_at_ms": "",
        "metadata_json": "{}",
    }
    _id, sig = stock_signal_from_stream_fields(_encode(raw))
    assert sig.direction == "long"
    assert sig.generated_at is None  # empty ms -> None (TradingHours rejects None)
