"""Unit tests for the market ingest daemon (feed → tick-stream republish)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from services.market_ingest.main import MarketIngestDaemon, _parse_trade_targets


class FakeFeed:
    def __init__(self):
        self.callback = None
        self.symbol_calls: list[list[str]] = []
        self.started = 0
        self.stopped = 0
        self.healthy = True  # controls is_healthy() for REST-fallback tests

    def set_tick_callback(self, cb):
        self.callback = cb

    def update_symbols(self, symbols, *args, **kwargs):  # noqa: ARG002
        self.symbol_calls.append(list(symbols))

    async def start(self):
        self.started += 1

    async def stop(self):
        self.stopped += 1

    def is_healthy(self) -> bool:
        return self.healthy


class FakePublisher:
    def __init__(self):
        self.published: list[tuple[str, str, dict]] = []
        self.closed = 0

    def publish(self, asset, symbol, payload):
        self.published.append((asset, symbol, payload))

    def close(self, timeout: float = 2.0):  # noqa: ARG002
        self.closed += 1


def _provider(values: list[list[str]]):
    """Async symbol provider yielding each value once, then repeating the last."""
    state = {"i": 0}

    async def _p() -> list[str]:
        i = state["i"]
        if i < len(values):
            state["i"] = i + 1
            return values[i]
        return values[-1]

    return _p


def _daemon(feed, publisher, provider, *, asset="stock", restart=False, interval=0.02):
    return MarketIngestDaemon(
        asset=asset,
        feed=feed,
        publisher=publisher,
        symbol_provider=provider,
        refresh_interval_seconds=interval,
        restart_on_symbol_change=restart,
    )


async def _run_briefly(daemon, seconds=0.12):
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(seconds)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_wires_callback_and_starts_feed():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]])))
    assert feed.callback is not None
    assert feed.symbol_calls[0] == ["A"]  # initial subscription
    assert feed.started == 1


@pytest.mark.asyncio
async def test_tick_is_republished_to_publisher():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]]), asset="futures"))
    feed.callback("A", {"close": 100.0}, datetime.now(UTC))
    assert pub.published == [("futures", "A", {"close": 100.0})]


@pytest.mark.asyncio
async def test_universe_change_updates_symbols_live_for_stock():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(
        _daemon(feed, pub, _provider([["A"], ["A", "B"]]), restart=False)
    )
    assert ["A", "B"] in feed.symbol_calls  # live re-subscribe
    assert feed.stopped == 1  # only the final shutdown stop (no restart)


@pytest.mark.asyncio
async def test_universe_change_enqueues_new_stock_symbols_for_coverage(monkeypatch):
    """A stock universe addition queues only the *new* codes for deep backfill."""
    import shared.collector.historical.coverage as cov

    enqueued: list[list[str]] = []
    monkeypatch.setattr(
        cov, "enqueue_symbols", lambda codes, **_kw: enqueued.append(list(codes))
    )

    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(
        _daemon(feed, pub, _provider([["A"], ["A", "B"]]), restart=False)
    )
    # Only the added symbol "B" is enqueued (not the pre-existing "A").
    assert enqueued == [["B"]]


@pytest.mark.asyncio
async def test_universe_change_does_not_enqueue_for_futures(monkeypatch):
    """Coverage backfill is stock-only; futures universe changes must not enqueue."""
    import shared.collector.historical.coverage as cov

    enqueued: list[list[str]] = []
    monkeypatch.setattr(
        cov, "enqueue_symbols", lambda codes, **_kw: enqueued.append(list(codes))
    )

    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(
        _daemon(feed, pub, _provider([["A"], ["B"]]), asset="futures", restart=True)
    )
    assert enqueued == []


@pytest.mark.asyncio
async def test_universe_change_restarts_feed_for_futures():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(
        _daemon(feed, pub, _provider([["A"], ["B"]]), asset="futures", restart=True)
    )
    assert ["B"] in feed.symbol_calls
    assert feed.started == 2  # initial + restart-on-change
    assert feed.stopped >= 1  # restart stop (+ final stop)


@pytest.mark.asyncio
async def test_stop_stops_feed_and_closes_publisher():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]])))
    assert feed.stopped >= 1
    assert pub.closed == 1


@pytest.mark.asyncio
async def test_symbol_provider_failure_keeps_current_symbols():
    feed, pub = FakeFeed(), FakePublisher()

    calls = {"n": 0}

    async def flaky() -> list[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return ["A"]
        raise RuntimeError("redis down")

    await _run_briefly(_daemon(feed, pub, flaky))
    assert feed.symbol_calls == [["A"]]
    assert feed.started == 1


def _fetcher(calls: list[str]):
    """Async REST price fetcher recording calls; returns a WS-shaped tick."""

    async def f(symbol: str) -> dict:
        calls.append(symbol)
        return {
            "close": 100.0,
            "high": 100.5,
            "low": 99.5,
            "volume": 1,
            "timestamp": 1.0,
            "code": symbol,
        }

    return f


def _fallback_daemon(
    feed,
    pub,
    fetcher,
    *,
    grace=0.0,
    session=lambda: True,
    interval=0.02,
    rate_limited=None,
):
    return MarketIngestDaemon(
        asset="stock",
        feed=feed,
        publisher=pub,
        symbol_provider=_provider([["A", "B"]]),
        refresh_interval_seconds=0.05,
        rest_price_fetcher=fetcher,
        rest_poll_interval_seconds=interval,
        ws_unhealthy_grace_seconds=grace,
        session_gate=session,
        rest_rate_limited=rate_limited,
    )


@pytest.mark.asyncio
async def test_rest_fallback_polls_when_ws_stale():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    calls: list[str] = []
    await _run_briefly(_fallback_daemon(feed, pub, _fetcher(calls)), seconds=0.18)
    assert calls, "REST fetcher should be polled when the WS feed is stale"
    assert pub.published, "REST-sourced ticks should be republished"
    assert {s for (_, s, _) in pub.published} <= {"A", "B"}
    assert all(asset == "stock" for (asset, _, _) in pub.published)


@pytest.mark.asyncio
async def test_rest_fallback_dormant_when_ws_healthy():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = True
    calls: list[str] = []
    await _run_briefly(_fallback_daemon(feed, pub, _fetcher(calls)), seconds=0.18)
    assert calls == [], "healthy WS → REST must stay dormant"
    assert pub.published == []


@pytest.mark.asyncio
async def test_rest_fallback_gated_off_outside_session():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    calls: list[str] = []
    daemon = _fallback_daemon(feed, pub, _fetcher(calls), session=lambda: False)
    await _run_briefly(daemon, seconds=0.18)
    assert calls == [], "outside the session, REST must not poll (stale last-close)"


@pytest.mark.asyncio
async def test_rest_fallback_respects_grace_window():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    calls: list[str] = []
    # grace far longer than the run window → poll never triggers
    daemon = _fallback_daemon(feed, pub, _fetcher(calls), grace=100.0)
    await _run_briefly(daemon, seconds=0.18)
    assert calls == [], "REST must wait out the grace window before polling"


@pytest.mark.asyncio
async def test_rest_fallback_disabled_without_fetcher_is_noop():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False  # stale, but no fetcher wired → no REST, no crash
    await _run_briefly(_daemon(feed, pub, _provider([["A"]])), seconds=0.12)
    assert pub.published == []


@pytest.mark.asyncio
async def test_rest_fallback_stops_after_ws_recovers():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    calls: list[str] = []
    daemon = _fallback_daemon(feed, pub, _fetcher(calls))
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.1)
    assert calls, "should be polling while WS is stale"
    feed.healthy = True  # WS recovers
    await asyncio.sleep(0.05)
    frozen = len(calls)
    await asyncio.sleep(0.08)  # several more poll intervals
    assert len(calls) == frozen, "REST polling must stop once the WS recovers"
    await daemon.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_rest_fallback_skips_publish_when_fetcher_returns_none():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    fetched: list[str] = []

    async def none_fetcher(symbol: str) -> dict | None:
        fetched.append(symbol)
        return None

    await _run_briefly(_fallback_daemon(feed, pub, none_fetcher), seconds=0.18)
    assert fetched, "fetcher should be called"
    assert pub.published == [], "a None price must not be republished"


@pytest.mark.asyncio
async def test_rest_fallback_skips_when_rate_limited():
    feed, pub = FakeFeed(), FakePublisher()
    feed.healthy = False
    calls: list[str] = []
    daemon = _fallback_daemon(feed, pub, _fetcher(calls), rate_limited=lambda: True)
    await _run_briefly(daemon, seconds=0.18)
    assert calls == [], "rate-limited KIS client → skip the poll, don't block"
    assert pub.published == []


def test_parse_trade_targets_extracts_codes_capped():
    raw = '{"codes": ["005930", " 000660 ", "", "035720"], "names": {}}'
    assert _parse_trade_targets(raw, max_symbols=2) == ["005930", "000660"]


def test_parse_trade_targets_handles_none_and_bad_json():
    assert _parse_trade_targets(None, max_symbols=40) == []
    assert _parse_trade_targets("not json", max_symbols=40) == []
    assert _parse_trade_targets("{}", max_symbols=40) == []
