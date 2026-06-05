"""Integration: raw_data ticks -> futures strategy daemon -> shadow candidate.

Task 5 of the futures-strategy-daemon plan. Wires:
  StreamConsumerFeed(raw_data) -> StreamingIndicatorEngine
  -> FuturesContextProvider -> SetupCEventReaction
  -> DecisionEngineDaemon -> signal.candidate.futures.shadow

Uses fakeredis.aioredis with a FakeServer so two client instances share state
(feed client + assertion client) while avoiding the fakeredis connection-close
side-effect that makes xrange return None after the feed task is cancelled.

Price series: 25 flat 1-min candles (close=100.0, high=100.5, low=99.5) to
warm the engine and establish the 15-min high at 100.5 with ATR≈1.0, followed
by one breakout tick (close=100.75) that sits 0.25 above the 15-min high —
within the 0.5×ATR buffer (0.50) — so Setup C fires long.

A tier-1 FOMC event is placed 5 minutes before ``now`` so
``find_recent_event(window=15, min_tier=2)`` returns it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import pandas as pd
import pytest

from services.decision_engine.context_provider import FuturesContextProvider
from services.decision_engine.daily_reference import FuturesDailyReference
from services.decision_engine.main import DecisionEngineDaemon
from services.trading.indicator_engine import StreamingIndicatorEngine
from services.trading.stream_consumer_feed import StreamConsumerFeed
from shared.decision.context import ScheduledEvent
from shared.decision.setups.event_reaction import SetupCEventReaction

_SYMBOL = "A05"
_BASE = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
_SHADOW_STREAM = "signal.candidate.futures.shadow"


class _Macro:
    """Minimal MacroSnapshot stub with a positive sp500_change_pct."""

    sp500_change_pct = 1.0


class _Store:
    """Minimal parquet store stub providing a single historical daily bar."""

    def get_daily_bars(self, symbol, start=None, end=None, limit=None):  # noqa: ARG002
        return pd.DataFrame({"close": [99.0], "open": [98.0]})


def _make_tick(
    symbol: str, ts: datetime, close: float, high: float, low: float
) -> dict:
    return {
        "symbol": symbol,
        "code": symbol,
        "close": str(close),
        "high": str(high),
        "low": str(low),
        "volume": "1",
        "timestamp": str(ts.timestamp()),
    }


@pytest.mark.asyncio
async def test_event_breakout_produces_shadow_candidate():
    """End-to-end: rising tick series + near-event → Setup C fires → shadow stream."""
    server = fakeredis.aioredis.FakeServer()
    # Two clients on the same server: one drives the feed/daemon, one for assertions.
    # Using separate client objects avoids the fakeredis connection-close side-effect
    # (feed.stop() cancels the xread task which corrupts the originating client's
    # internal state, making subsequent xrange calls on that client return None).
    redis_ops = fakeredis.aioredis.FakeRedis(server=server, db=1)
    redis_assert = fakeredis.aioredis.FakeRedis(server=server, db=1)

    engine = StreamingIndicatorEngine()
    feed = StreamConsumerFeed(
        redis=redis_ops,
        stream="raw_data",
        indicator_engine=engine,
        xread_block_ms=50,
    )
    feed.update_symbols([_SYMBOL])
    await feed.start()

    # Phase 1 — 25 flat 1-min candles to warm the engine.
    # close=100.0, high=100.5, low=99.5 → ATR≈1.0, 15-min high≈100.5.
    for i in range(25):
        ts = _BASE + timedelta(minutes=i)
        await redis_assert.xadd(
            "raw_data", _make_tick(_SYMBOL, ts, close=100.0, high=100.5, low=99.5)
        )

    # Phase 2 — breakout tick: close=100.75 is 0.25 above 15-min high=100.5.
    # Buffer = 0.5 × ATR(≈1.0) = 0.5 → 0.25 < 0.5 → breakout condition met.
    ts_25 = _BASE + timedelta(minutes=25)
    await redis_assert.xadd(
        "raw_data", _make_tick(_SYMBOL, ts_25, close=100.75, high=100.75, low=100.0)
    )

    # Wait for the StreamConsumerFeed reader loop to drain the 26 entries.
    await asyncio.sleep(0.4)

    # Engine sanity assertions — helps diagnose flakiness if Setup C doesn't fire.
    assert engine.is_warm(_SYMBOL), (
        f"Engine not warm after 26 ticks; "
        f"candle count={len(engine._accumulators.get(_SYMBOL, type('X', (), {'candles': []})()).candles)}"
    )
    assert engine.get_last_price(_SYMBOL) == pytest.approx(100.75, abs=0.01)
    rng = engine.get_recent_range(_SYMBOL, 15)
    assert rng is not None
    assert rng[0] == pytest.approx(
        100.5, abs=0.01
    ), f"15-min high not as expected: {rng}"

    # A tier-1 FOMC event 5 minutes before now=base+25min.
    # window_minutes=15, so it is found by find_recent_event.
    ev = [
        ScheduledEvent(
            "e1",
            "FOMC",
            (_BASE + timedelta(minutes=20)).astimezone(),
            1,
        )
    ]

    now_fn_time = _BASE + timedelta(minutes=25)
    provider = FuturesContextProvider(
        engine=engine,
        daily_ref=FuturesDailyReference(store=_Store(), symbol=_SYMBOL),
        symbol=_SYMBOL,
        macro_reader=lambda: _Macro(),
        events_provider=lambda: ev,
        now_fn=lambda: now_fn_time,
    )

    daemon = DecisionEngineDaemon(
        redis=redis_ops,
        setups=[SetupCEventReaction()],
        context_provider=provider,
        candidate_stream=_SHADOW_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.01,
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.3)
    await daemon.stop()
    await asyncio.gather(task, return_exceptions=True)

    # Assert via the assertion client BEFORE stopping the feed
    # (feed.stop() cancels the xread task and disrupts redis_ops state).
    entries = await redis_assert.xrange(_SHADOW_STREAM)
    assert entries, "Expected at least one shadow candidate on the stream"

    fields = entries[0][1]
    assert (
        fields[b"setup_type"] == b"C_event_reaction"
    ), f"Expected setup_type=C_event_reaction, got {fields.get(b'setup_type')}"
    assert b"signal_id" in fields, "signal_id field missing from candidate entry"
    assert (
        fields[b"direction"] == b"long"
    ), f"Expected long breakout, got {fields.get(b'direction')}"

    await feed.stop()
