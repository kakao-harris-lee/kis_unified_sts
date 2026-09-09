"""The orchestrator's futures tick republish must carry the top of book.

`_on_futures_tick` is the feed's TRADE-tick callback; the futures feed delivers
orderbook (H0IFASP0) ticks on a channel that never reaches it. Publishing that
payload verbatim puts quote-less entries on `raw_data`, and the only remaining
quote source for the decoupled order-router is a second KIS futures WebSocket
on the same account — which evicts one of the two connections (measured
2026-09-07/08). These tests pin the merge at the real wiring seam.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from services.monitoring.tick_stream_publisher import OrderbookMergeLog
from services.trading.orchestrator import TradingConfig, TradingOrchestrator

ORCH_LOGGER = "services.trading.orchestrator"

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
        self.raises = raises
        self.callback = None
        if has_accessor:
            self.get_orderbook_snapshot = self._get_orderbook_snapshot

    def _get_orderbook_snapshot(self, symbol):  # noqa: ARG002
        if self.raises:
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
    orch._orderbook_merge_log = OrderbookMergeLog(
        logging.getLogger(ORCH_LOGGER), "trader-futures"
    )
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


# ---------------------------------------------------------------------------
# Merge failures must be visible (a silent revert to trade-only ticks surfaces
# only as the router blocking every signal, which reads as a market condition)
# ---------------------------------------------------------------------------


def _tick(feed, orch):
    feed.callback(SYMBOL, dict(TRADE), datetime.fromtimestamp(TRADE["timestamp"], UTC))
    assert orch is not None


def test_a_feed_without_the_accessor_warns_exactly_once(caplog):
    feed = _Feed(QUOTE, has_accessor=False)
    publisher = _Publisher()
    orch = _orchestrator(feed, publisher)

    with caplog.at_level(logging.WARNING, logger=ORCH_LOGGER):
        _tick(feed, orch)
        _tick(feed, orch)

    warnings = [
        r for r in caplog.records if "orderbook merge unavailable" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "has no get_orderbook_snapshot" in warnings[0].getMessage()
    assert len(publisher.published) == 2  # ticks still flow


def test_a_raising_accessor_warns_once_and_logs_recovery(caplog):
    feed = _Feed(QUOTE, raises=True)
    publisher = _Publisher()
    orch = _orchestrator(feed, publisher)

    with caplog.at_level(logging.INFO, logger=ORCH_LOGGER):
        _tick(feed, orch)
        _tick(feed, orch)
        feed.raises = False
        _tick(feed, orch)
        _tick(feed, orch)

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "orderbook merge" in r.getMessage()
    ]
    recoveries = [r for r in caplog.records if "merge recovered" in r.getMessage()]
    assert len(warnings) == 1
    assert len(recoveries) == 1
    assert publisher.published[-1][2]["bid_price_1"] == 331.18


def test_a_one_sided_book_is_not_treated_as_a_failure(caplog):
    """Pre-open with no book is a market state, not a fault — warning on it
    would train the operator to ignore the line that matters."""
    feed = _Feed({"bid_price_1": 331.18, "ask_price_1": 0.0})
    orch = _orchestrator(feed, _Publisher())

    with caplog.at_level(logging.WARNING, logger=ORCH_LOGGER):
        _tick(feed, orch)

    assert [r for r in caplog.records if "orderbook merge" in r.getMessage()] == []


def test_an_empty_book_does_not_clear_the_failure_latch(caplog):
    """Same rule as the ingest producer: recovery means a book was actually
    merged, not that the accessor returned without raising."""
    feed = _Feed(QUOTE, raises=True)
    orch = _orchestrator(feed, _Publisher())

    with caplog.at_level(logging.INFO, logger=ORCH_LOGGER):
        _tick(feed, orch)  # WARNING
        feed.raises = False
        feed._snapshot = {}  # accessor works, book is empty
        _tick(feed, orch)

        assert orch._orderbook_merge_log.warned is True
        assert [r for r in caplog.records if "merge recovered" in r.getMessage()] == []

        feed._snapshot = QUOTE
        _tick(feed, orch)
        _tick(feed, orch)

    assert orch._orderbook_merge_log.warned is False
    assert len([r for r in caplog.records if "merge recovered" in r.getMessage()]) == 1


def test_an_undatable_two_sided_book_warns_instead_of_publishing_silently(caplog):
    """Same rule as the ingest producer: an undatable book is a fault."""
    feed = _Feed({**QUOTE, "timestamp": None})
    publisher = _Publisher()
    orch = _orchestrator(feed, publisher)

    with caplog.at_level(logging.WARNING, logger=ORCH_LOGGER):
        _tick(feed, orch)

    warnings = [
        r for r in caplog.records if "orderbook merge unavailable" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "no usable timestamp" in warnings[0].getMessage()
    assert publisher.published[0][2] == TRADE
