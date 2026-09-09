"""The orchestrator's futures tick republish must carry the top of book.

`_on_futures_tick` is the feed's TRADE-tick callback; the futures feed delivers
orderbook (H0IFASP0) ticks on a channel that never reaches it. Publishing that
payload verbatim puts quote-less entries on `raw_data`, and the only remaining
quote source for the decoupled order-router is a second KIS futures WebSocket
on the same account — which evicts one of the two connections (measured
2026-09-07/08). These tests pin the merge at the real wiring seam.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator

SYMBOL = "A05603"
QUOTE = {
    "code": SYMBOL,
    "bid_price_1": 331.18,
    "bid_qty_1": 12.0,
    "ask_price_1": 331.22,
    "ask_qty_1": 9.0,
    "spread": 0.04,
    "timestamp": 1_700_000_000.0,
}
TRADE = {"code": SYMBOL, "close": 331.20, "timestamp": 1_700_000_005.0}


class _Feed:
    def __init__(self, snapshot=None, *, has_accessor=True, raises=False):
        self._snapshot = snapshot
        self._has_accessor = has_accessor
        self._raises = raises
        self.callback = None
        if has_accessor:
            self.get_orderbook_snapshot = self._get_orderbook_snapshot

    def _get_orderbook_snapshot(self, symbol):  # noqa: ARG002
        if self._raises:
            raise RuntimeError("boom")
        return dict(self._snapshot or {})

    def set_tick_callback(self, cb):
        self.callback = cb


class _Publisher:
    def __init__(self):
        self.published: list[tuple[str, str, dict]] = []

    def publish(self, asset, symbol, payload):
        self.published.append((asset, symbol, payload))


def _orchestrator(feed, publisher) -> TradingOrchestrator:
    orch = object.__new__(TradingOrchestrator)
    orch.config = TradingConfig(
        asset_class="futures",
        strategy_name="setup_d_vwap_reversion",
        symbols=[SYMBOL],
        initial_capital=10_000_000,
        paper_trading=True,
    )
    orch._strategy_manager = None
    orch._indicator_engine = None
    orch._indicator_resolver = None
    orch._paper_broker = None
    orch._futures_slippage_controller = None
    orch._symbol_names = {}
    orch._futures_price_feed = feed
    orch._stock_price_feed = None
    orch._stream_consumer_feed = None
    orch._tick_stream_publisher = publisher
    orch._init_indicator_engine()
    assert feed.callback is not None, "futures tick callback was never registered"
    return orch


def _publish_one(feed, publisher) -> dict:
    _orchestrator(feed, publisher)
    feed.callback(SYMBOL, dict(TRADE), datetime.fromtimestamp(TRADE["timestamp"], UTC))
    assert publisher.published, "no tick was published"
    asset, symbol, payload = publisher.published[-1]
    assert (asset, symbol) == ("futures", SYMBOL)
    return payload


def test_futures_tick_publishes_the_cached_top_of_book():
    payload = _publish_one(_Feed(QUOTE), _Publisher())

    assert payload["bid_price_1"] == 331.18
    assert payload["bid_qty_1"] == 12.0
    assert payload["ask_price_1"] == 331.22
    assert payload["ask_qty_1"] == 9.0
    assert payload["spread"] == 0.04
    # The trade tick owns identity and time; a stale quote must not backdate it.
    assert payload["timestamp"] == TRADE["timestamp"]
    assert payload["close"] == 331.20


@pytest.mark.parametrize(
    "feed",
    [
        _Feed({}),
        _Feed({"bid_price_1": 331.18, "ask_price_1": 0.0}),
        _Feed(QUOTE, has_accessor=False),  # stream-cutover feed
        _Feed(QUOTE, raises=True),
    ],
    ids=["empty-book", "one-sided", "no-accessor", "raises"],
)
def test_futures_tick_publishes_unchanged_when_no_usable_quote(feed):
    payload = _publish_one(feed, _Publisher())
    assert payload == TRADE
