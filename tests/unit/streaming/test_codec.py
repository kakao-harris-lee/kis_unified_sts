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


# ---------------------------------------------------------------------------
# Optional orderbook fields (additive, no schema_version bump)
# ---------------------------------------------------------------------------


def test_market_tick_orderbook_fields_round_trip() -> None:
    msg = MarketTickMessage(
        asset="futures",
        symbol="A05603",
        price=331.20,
        timestamp=1771982309.0,
        bid_price_1=331.18,
        bid_qty_1=12.0,
        ask_price_1=331.22,
        ask_qty_1=9.0,
        spread=0.04,
        quote_ts=1771982304.0,
    )

    fields = encode(msg)

    assert fields["bid_price_1"] == "331.18"
    assert fields["ask_qty_1"] == "9.0"
    assert fields["spread"] == "0.04"
    assert fields["quote_ts"] == "1771982304.0"
    assert decode(MarketTickMessage, fields) == msg
    assert msg.to_price_dict()["bid_price_1"] == 331.18
    assert msg.to_price_dict()["spread"] == 0.04


def test_market_tick_without_orderbook_stays_wire_identical() -> None:
    """Back-compat: entries written before the fields existed still decode, and
    a trade-only tick still encodes exactly the fields it used to."""
    legacy_fields = {
        "schema_version": "1",
        "asset": "futures",
        "symbol": "A05603",
        "price": "331.20",
        "timestamp": "1771982309.0",
    }

    msg = decode(MarketTickMessage, legacy_fields)

    assert msg.bid_price_1 is None and msg.spread is None
    assert set(encode(msg)) == set(legacy_fields)
    assert "bid_price_1" not in msg.to_price_dict()


def test_market_tick_source_payload_carries_orderbook_when_present() -> None:
    """The publisher path: the merged feed snapshot the orchestrator emits."""
    msg = MarketTickMessage.from_source_payload(
        asset="futures",
        symbol="A05603",
        payload={
            "close": 331.20,
            "timestamp": 1771982309.0,
            "bid_price_1": 331.18,
            "bid_qty_1": 12,
            "ask_price_1": 331.22,
            "ask_qty_1": 9,
            "spread": 0.04,
            "quote_ts": 1771982304.0,
        },
        now=1771982310.0,
    )

    assert msg.bid_price_1 == 331.18 and msg.ask_qty_1 == 9.0
    assert msg.spread == 0.04
    assert msg.quote_ts == 1771982304.0


def test_market_tick_drops_negative_orderbook_values_without_losing_the_tick() -> None:
    """A crossed/garbled quote must cost the quote, not the trade tick.

    ``TickStreamPublisher._build_fields`` treats a ``ValueError`` from this
    constructor as "unpublishable", and pydantic's ``ValidationError`` is one —
    so a ``ge=0`` violation raised here would delete the whole tick from the
    stream instead of one field.
    """
    msg = MarketTickMessage.from_source_payload(
        asset="futures",
        symbol="A05603",
        payload={
            "close": 331.20,
            "bid_price_1": 331.18,
            "ask_price_1": 331.22,
            "spread": -0.04,
        },
        now=1771982310.0,
    )

    assert msg.price == 331.20
    assert msg.spread is None
    assert msg.bid_price_1 == 331.18


def test_market_tick_legacy_fields_carry_orderbook() -> None:
    msg = decode(
        MarketTickMessage,
        {
            b"code": b"A05603",
            b"current_price": b"331.20",
            b"bid_price_1": b"331.18",
            b"ask_price_1": b"331.22",
        },
        legacy_adapter=MarketTickMessage.from_legacy_fields,
    )

    assert msg.bid_price_1 == 331.18 and msg.ask_price_1 == 331.22


# ---------------------------------------------------------------------------
# orderbook_publish_fields — the merge rule both producers share
# ---------------------------------------------------------------------------


def test_orderbook_publish_fields_carries_the_quote_time_as_quote_ts() -> None:
    from services.monitoring.tick_stream_publisher import orderbook_publish_fields

    fields = orderbook_publish_fields(
        {
            "code": "A05603",
            "timestamp": 1771982309.0,
            "bid_price_1": 331.18,
            "bid_qty_1": 12.0,
            "ask_price_1": 331.22,
            "ask_qty_1": 9.0,
            "spread": 0.04,
        }
    )

    # `code` is excluded and the snapshot's `timestamp` is re-keyed: the
    # published entry's `timestamp` belongs to the trade tick, so the book's
    # own time has to travel separately or a freshness check bounds the wrong
    # thing.
    assert set(fields) == {
        "bid_price_1",
        "bid_qty_1",
        "ask_price_1",
        "ask_qty_1",
        "spread",
        "quote_ts",
    }
    assert fields["spread"] == 0.04
    assert fields["quote_ts"] == 1771982309.0


def test_orderbook_publish_fields_keeps_an_existing_quote_ts() -> None:
    """A snapshot that already came off the stream carries `quote_ts`; re-keying
    its `timestamp` again would launder a stale book into a fresh one."""
    from services.monitoring.tick_stream_publisher import orderbook_publish_fields

    fields = orderbook_publish_fields(
        {
            "bid_price_1": 331.18,
            "ask_price_1": 331.22,
            "quote_ts": 100.0,
            "timestamp": 900.0,
        }
    )

    assert fields["quote_ts"] == 100.0


def test_orderbook_publish_fields_omits_quote_ts_when_unreadable() -> None:
    from services.monitoring.tick_stream_publisher import orderbook_publish_fields

    fields = orderbook_publish_fields(
        {"bid_price_1": 331.18, "ask_price_1": 331.22, "timestamp": "nope"}
    )

    assert "quote_ts" not in fields
    assert fields["bid_price_1"] == 331.18


@pytest.mark.parametrize(
    "snapshot",
    [
        None,
        {},
        {"bid_price_1": 331.18},
        {"bid_price_1": 331.18, "ask_price_1": 0.0},
        {"bid_price_1": 0.0, "ask_price_1": 331.22},
        {"bid_price_1": "nope", "ask_price_1": "nope"},
    ],
    ids=["none", "empty", "bid-only", "zero-ask", "zero-bid", "garbage"],
)
def test_orderbook_publish_fields_rejects_anything_but_a_two_sided_book(
    snapshot,
) -> None:
    from services.monitoring.tick_stream_publisher import orderbook_publish_fields

    assert orderbook_publish_fields(snapshot) == {}


def test_market_tick_still_ignores_unknown_keys() -> None:
    """`extra="ignore"` is the existing contract — the publisher's rollout
    aliases (`code`/`close`/`current_price`) ride in the same field map. Adding
    the orderbook fields must not turn that into a rejection."""
    msg = decode(
        MarketTickMessage,
        {
            "schema_version": "1",
            "asset": "futures",
            "symbol": "A05603",
            "price": "331.20",
            "timestamp": "1771982309.0",
            "bid_price_1": "331.18",
            "ask_price_1": "331.22",
            "code": "A05603",
            "close": "331.20",
            "current_price": "331.20",
            "totally_unknown": "whatever",
        },
    )

    assert msg.bid_price_1 == 331.18
    assert not hasattr(msg, "totally_unknown")
