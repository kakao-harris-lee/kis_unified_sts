"""Pub/sub producer contract: TradingStatePublisher → ``trading:events:{topic}``.

Verifies the S1b fix. State writes now ALSO ``PUBLISH`` to the exact channels the
dashboard WebSocket subscriber
(``services/dashboard/websocket_publisher.py::_pubsub_loop``) reads, with a
payload the subscriber can parse. The subscriber derives the WS topic from the
channel name (``channel.rsplit(":", 1)[-1]``) and reads ``asset_class`` from the
JSON payload — both are asserted here so the two ends stay in contract.
"""

from __future__ import annotations

import json
from datetime import datetime

import fakeredis
import pytest

from shared.models.position import Position, PositionSide
from shared.streaming import trading_state
from shared.streaming.trading_state import TradingStatePublisher

_CHANNELS = (
    "trading:events:positions",
    "trading:events:signals",
    "trading:events:fills",
)


@pytest.fixture
def fake_redis(monkeypatch):
    """Isolated fakeredis (decode_responses mirrors RedisClient.get_client())."""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    monkeypatch.setattr(trading_state, "_get_redis", lambda: client)
    return client


def _subscribe(client):
    pubsub = client.pubsub()
    pubsub.subscribe(*_CHANNELS)
    # Drain the subscribe-confirmation frames.
    while pubsub.get_message(timeout=0.05) is not None:
        pass
    return pubsub


def _drain(pubsub) -> list[tuple[str, dict]]:
    """Return (topic, payload) pairs applying the subscriber's exact derivation."""
    out: list[tuple[str, dict]] = []
    while True:
        m = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
        if m is None:
            break
        if m.get("type") != "message":
            continue
        channel = m["channel"]
        topic = channel.rsplit(":", 1)[-1]  # exactly what _pubsub_loop does
        payload = json.loads(m["data"])
        assert isinstance(payload, dict)  # subscriber requires a dict for asset_class
        out.append((topic, payload))
    return out


def _make_position(position_id: str) -> Position:
    return Position(
        id=position_id,
        code="A05603",
        name="KOSPI200선물",
        side=PositionSide.SHORT,
        quantity=1,
        entry_price=800.0,
        entry_time=datetime.now(),
        current_price=798.0,
        strategy="setup_a_gap_reversion",
    )


def test_raw_position_publishes_positions_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("stock").publish_raw_position(
        "005930", {"id": "005930", "code": "005930"}
    )
    events = _drain(pubsub)
    assert [t for t, _ in events] == ["positions"]
    assert events[0][1]["asset_class"] == "stock"


def test_raw_signal_publishes_signals_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("stock").publish_raw_signal({"id": "s1", "symbol": "005930"})
    events = _drain(pubsub)
    assert [t for t, _ in events] == ["signals"]
    assert events[0][1]["asset_class"] == "stock"


def test_raw_trade_publishes_fills_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("stock").publish_raw_trade({"id": "t1", "symbol": "005930"})
    events = _drain(pubsub)
    assert [t for t, _ in events] == ["fills"]
    assert events[0][1]["asset_class"] == "stock"


def test_position_closed_publishes_positions_and_fills(fake_redis):
    """A close mutates open positions AND appends a fill → both topics fire."""
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("futures").publish_position_closed(_make_position("p1"))
    topics = sorted(t for t, _ in _drain(pubsub))
    assert topics == ["fills", "positions"]


def test_position_opened_publishes_positions_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("futures").publish_position_opened(_make_position("p1"))
    events = _drain(pubsub)
    assert [t for t, _ in events] == ["positions"]
    assert events[0][1]["asset_class"] == "futures"


def test_positions_update_publishes_positions_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    TradingStatePublisher("futures").publish_positions_update(
        [_make_position("p1")], throttle=0.0
    )
    events = _drain(pubsub)
    assert [t for t, _ in events] == ["positions"]


def test_remove_and_reset_publish_positions_topic(fake_redis):
    pubsub = _subscribe(fake_redis)
    pub = TradingStatePublisher("stock")
    pub.remove_position("005930")
    pub.reset_positions()
    topics = [t for t, _ in _drain(pubsub)]
    assert topics == ["positions", "positions"]


def test_asset_class_is_forced_to_publisher_asset(fake_redis):
    """asset_class in every message equals the publisher's asset (invalidation key)."""
    pubsub = _subscribe(fake_redis)
    pub = TradingStatePublisher("futures")
    pub.publish_raw_position("A05603", {"id": "A05603"})
    pub.publish_raw_signal({"id": "s1"})
    pub.publish_raw_trade({"id": "t1"})
    events = _drain(pubsub)
    assert len(events) == 3
    assert {payload["asset_class"] for _, payload in events} == {"futures"}


def test_pubsub_failure_never_breaks_the_write(monkeypatch):
    """A pub/sub error is swallowed; the primary Redis write still succeeds."""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)

    def _boom(*_a, **_k):
        raise RuntimeError("pubsub down")

    monkeypatch.setattr(client, "publish", _boom)
    monkeypatch.setattr(trading_state, "_get_redis", lambda: client)

    # Must not raise despite publish() blowing up.
    TradingStatePublisher("stock").publish_raw_trade({"id": "t1", "symbol": "005930"})

    # And the primary write (LPUSH into the trades LIST) still happened.
    assert client.llen("trading:stock:trades") == 1
