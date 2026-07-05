from __future__ import annotations

import pytest

from shared.models.stream_models import MarketTickMessage, StreamMessage
from shared.streaming.codec import StreamDecodeError, decode, encode


def test_encode_decode_market_tick_message_round_trip() -> None:
    msg = MarketTickMessage(
        asset="stock",
        symbol="005930",
        price=71500.0,
        timestamp=1771982309.0,
        name="SamsungElec",
        volume=123456.0,
        volume_is_cumulative=True,
    )

    fields = encode(msg)

    assert fields == {
        "schema_version": "1",
        "asset": "stock",
        "symbol": "005930",
        "price": "71500.0",
        "timestamp": "1771982309.0",
        "name": "SamsungElec",
        "volume": "123456.0",
        "volume_is_cumulative": "true",
    }
    assert decode(MarketTickMessage, fields) == msg


def test_decode_rejects_schema_version_mismatch() -> None:
    fields = {
        "schema_version": "2",
        "asset": "stock",
        "symbol": "005930",
        "price": "71500.0",
        "timestamp": "1771982309.0",
    }

    with pytest.raises(StreamDecodeError, match="schema_version"):
        decode(MarketTickMessage, fields)


def test_decode_supports_legacy_tick_aliases_with_explicit_adapter() -> None:
    fields = {
        b"code": b"005930",
        b"current_price": b"71500.0",
        b"timestamp": b"1771982309.0",
        b"volume": b"123456",
    }

    msg = decode(
        MarketTickMessage,
        fields,
        legacy_adapter=MarketTickMessage.from_legacy_fields,
    )

    assert msg.asset == "stock"
    assert msg.symbol == "005930"
    assert msg.price == 71500.0
    assert msg.volume == 123456.0


def test_decode_rejects_missing_schema_version_without_legacy_adapter() -> None:
    fields = {
        "asset": "stock",
        "symbol": "005930",
        "price": "71500.0",
        "timestamp": "1771982309.0",
    }

    with pytest.raises(StreamDecodeError, match="schema_version"):
        decode(MarketTickMessage, fields)


class _ComplexMessage(StreamMessage):
    stream: str
    payload: dict[str, float]


def test_encode_nested_payload_uses_data_field() -> None:
    msg = _ComplexMessage(stream="stream:test", payload={"score": 0.7})

    fields = encode(msg)

    assert fields["schema_version"] == "1"
    assert set(fields) == {"schema_version", "data"}
    assert decode(_ComplexMessage, fields) == msg


def test_encode_decode_json_field_mapping_keeps_flat_stream_contract() -> None:
    msg = _ComplexMessage(stream="stream:test", payload={"score": 0.7})

    fields = encode(msg, json_fields={"payload": "payload_json"})

    assert fields == {
        "schema_version": "1",
        "stream": "stream:test",
        "payload_json": '{"score":0.7}',
    }
    assert (
        decode(
            _ComplexMessage,
            fields,
            json_fields={"payload": "payload_json"},
        )
        == msg
    )


def test_decode_json_field_mapping_rejects_malformed_json() -> None:
    fields = {
        "schema_version": "1",
        "stream": "stream:test",
        "payload_json": "{bad",
    }

    with pytest.raises(StreamDecodeError, match="payload_json"):
        decode(_ComplexMessage, fields, json_fields={"payload": "payload_json"})
