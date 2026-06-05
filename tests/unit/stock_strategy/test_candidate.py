"""Stock candidate serializer: orchestrator Signal -> stream field dict."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from shared.models.signal import Signal, SignalType


def test_serializes_all_fields():
    sig = Signal(
        code="005930",
        name="Samsung",
        signal_type=SignalType.ENTRY,
        strategy="williams_r",
        price=71000.0,
        quantity=10,
        confidence=0.62,
        timestamp=datetime(2026, 6, 5, 0, 30, tzinfo=UTC),
        metadata={"signal_direction": "long", "atr": 120.0},
    )
    fields = stock_signal_to_stream_dict(sig, signal_id="abc123")
    assert fields["signal_id"] == "abc123"
    assert fields["code"] == "005930"
    assert fields["name"] == "Samsung"
    assert fields["strategy"] == "williams_r"
    assert fields["direction"] == "long"
    assert fields["price"] == "71000.0"
    assert fields["quantity"] == "10"
    assert fields["confidence"] == "0.62"
    assert fields["generated_at_ms"] == str(
        int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000)
    )
    assert json.loads(fields["metadata_json"])["atr"] == 120.0


def test_direction_defaults_to_long_when_absent():
    sig = Signal(code="000660", strategy="pattern_pullback", price=100.0, metadata={})
    fields = stock_signal_to_stream_dict(sig, signal_id="x")
    assert fields["direction"] == "long"


def test_naive_timestamp_treated_as_utc():
    sig = Signal(code="A", price=1.0, timestamp=datetime(2026, 6, 5, 0, 0))  # naive
    fields = stock_signal_to_stream_dict(sig, signal_id="x")
    assert fields["generated_at_ms"]  # non-empty, no crash
