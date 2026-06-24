"""StockStrategyDaemon: per-symbol context build + publish; universe refresh."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from services.stock_strategy.daemon import StockStrategyDaemon
from shared.models.signal import Signal
from shared.streaming.stock_regime import StockRegimeConfig

_NOW = datetime(2026, 6, 5, 0, 30, tzinfo=UTC)


class _FakeEngine:
    def __init__(self, warm=("005930",), mfi_values=None, daily=None):
        self._warm = set(warm)
        self._mfi_values = mfi_values
        # Per-symbol daily indicator dicts (unprefixed keys, e.g. sma_200),
        # mirroring StreamingIndicatorEngine.get_daily_indicators output.
        self._daily = dict(daily or {})

    def is_warm(self, symbol):
        return symbol in self._warm

    def get_market_mfi_values(self, _active_symbols=None):
        return dict(self._mfi_values or {})

    def get_daily_indicators(self, symbol):
        return dict(self._daily.get(symbol, {}))


class _FakeResolver:
    def collect_entry_indicators(self, _symbol):
        return {"rsi": 30.0, "atr": 100.0}


class _FakeFeed:
    def __init__(self):
        self.symbols = []
        self.started = False
        self.stopped = False

    def update_symbols(self, codes):
        self.symbols = list(codes)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def get_current_price(self, _symbol):
        return {"code": _symbol, "close": 71000.0, "timestamp": 1.0}


class _FakeManager:
    def __init__(self, fire_for=("005930",)):
        self._fire = set(fire_for)

    async def check_entries(self, context):
        code = context.market_data.get("code")
        if code in self._fire:
            return [
                Signal(code=code, strategy="williams_r", price=71000.0, confidence=0.6)
            ]
        return []


class _CaptureManager:
    """Records the EntryContext seen for each symbol (no signals emitted)."""

    def __init__(self):
        self.contexts = {}

    async def check_entries(self, context):
        self.contexts[context.market_data.get("code")] = context
        return []


class _FakeRedis:
    def __init__(self):
        self.added = []
        self.kv = {}

    async def xadd(self, stream, fields, **_kw):
        self.added.append((stream, fields))

    async def expire(self, *_a, **_k):
        return True

    async def set(self, key, value, **_kw):
        self.kv[key] = value
        return True

    async def get(self, k):
        return self.kv.get(k)

    async def hkeys(self, k):
        return []


def _daemon(**kw):
    defaults = {
        "redis": _FakeRedis(),
        "feed": _FakeFeed(),
        "engine": _FakeEngine(),
        "resolver": _FakeResolver(),
        "manager": _FakeManager(),
        "candidate_stream": "signal.candidate.stock.shadow",
        "candidate_maxlen": 10_000,
        "now_fn": lambda: _NOW,
    }
    defaults.update(kw)
    return StockStrategyDaemon(**defaults)


@pytest.mark.asyncio
async def test_evaluate_once_publishes_candidate_for_warm_firing_symbol():
    redis = _FakeRedis()
    d = _daemon(redis=redis)
    d._universe = ["005930", "000660"]  # 000660 not warm
    await d.evaluate_once()
    assert len(redis.added) == 1
    stream, fields = redis.added[0]
    assert stream == "signal.candidate.stock.shadow"
    assert fields["code"] == "005930" and "signal_id" in fields


@pytest.mark.asyncio
async def test_not_warm_symbol_is_skipped():
    redis = _FakeRedis()
    d = _daemon(redis=redis, engine=_FakeEngine(warm=()))  # nothing warm
    d._universe = ["005930"]
    await d.evaluate_once()
    assert redis.added == []


@pytest.mark.asyncio
async def test_per_symbol_failure_isolated():
    class _BoomManager:
        async def check_entries(self, context):
            if context.market_data.get("code") == "005930":
                raise RuntimeError("boom")
            return [
                Signal(code=context.market_data.get("code"), strategy="s", price=1.0)
            ]

    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        manager=_BoomManager(),
        engine=_FakeEngine(warm=("005930", "000660")),
    )
    d._universe = ["005930", "000660"]
    await d.evaluate_once()  # must not raise
    # 000660 still published despite 005930 raising
    assert any(f["code"] == "000660" for _s, f in redis.added)


@pytest.mark.asyncio
async def test_refresh_universe_updates_feed():
    feed = _FakeFeed()
    d = _daemon(feed=feed)
    import json

    await d._apply_watchlist(json.dumps({"strategies": {"w": ["005930", "000660"]}}))
    assert set(feed.symbols) == {"005930", "000660"}
    assert set(d._universe) == {"005930", "000660"}


# ---------------------------------------------------------------------------
# Market-regime publisher + bear entry gate
# ---------------------------------------------------------------------------

_REGIME_CFG = StockRegimeConfig(min_mfi_symbols=2)


@pytest.mark.asyncio
async def test_bear_regime_published_and_blocks_entries():
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 28.0, "000660": 30.0}),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 0
    assert redis.added == []  # entry evaluation skipped
    payload = json.loads(redis.kv[_REGIME_CFG.redis_key])
    assert payload["regime"] == "BEAR_STRONG"
    assert payload["computed_at_ms"] == int(_NOW.timestamp() * 1000)


@pytest.mark.asyncio
async def test_non_bear_regime_published_and_entries_proceed():
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 55.0, "000660": 60.0}),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 1
    assert json.loads(redis.kv[_REGIME_CFG.redis_key])["regime"] == "BULL_STRONG"


@pytest.mark.asyncio
async def test_bear_gate_disabled_publishes_but_does_not_block():
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 28.0, "000660": 30.0}),
        regime_config=StockRegimeConfig(min_mfi_symbols=2, block_entries_in_bear=False),
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 1  # gate off: bear regime published but entries proceed
    assert json.loads(redis.kv[_REGIME_CFG.redis_key])["regime"] == "BEAR_STRONG"


@pytest.mark.asyncio
async def test_low_confidence_regime_does_not_block_entries():
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 28.0}),  # 1 < min_mfi_symbols=2
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 1
    payload = json.loads(redis.kv[_REGIME_CFG.redis_key])
    assert payload["regime"] == "UNKNOWN"
    assert payload["raw_regime"] == "BEAR_STRONG"


@pytest.mark.asyncio
async def test_no_regime_config_publishes_nothing():
    redis = _FakeRedis()
    d = _daemon(redis=redis)  # regime_config=None (default)
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 1
    assert redis.kv == {}


@pytest.mark.asyncio
async def test_engine_without_mfi_support_skips_publish():
    class _LegacyEngine:
        def is_warm(self, _symbol):
            return True

    redis = _FakeRedis()
    d = _daemon(redis=redis, engine=_LegacyEngine(), regime_config=_REGIME_CFG)
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 1  # entries ungated when the engine can't provide MFI
    assert redis.kv == {}


class _SetBoomRedis(_FakeRedis):
    async def set(self, *_a, **_k):
        raise RuntimeError("redis down")


@pytest.mark.asyncio
async def test_publish_failure_still_gates_entries_on_bear():
    # redis.set failing must not discard the locally computed BEAR payload:
    # M4-X may still act on the previous fresh publish, so entering long in
    # that window is exactly the fee churn the gate prevents.
    d = _daemon(
        redis=_SetBoomRedis(),
        engine=_FakeEngine(mfi_values={"005930": 28.0, "000660": 30.0}),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()  # must not raise

    assert published == 0  # gate works off the local payload


@pytest.mark.asyncio
async def test_publish_failure_does_not_block_entries_when_not_bear():
    d = _daemon(
        redis=_SetBoomRedis(),
        engine=_FakeEngine(mfi_values={"005930": 55.0, "000660": 60.0}),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()  # must not raise

    assert published == 1  # bull regime: publish failure changes nothing


@pytest.mark.asyncio
async def test_regime_compute_failure_does_not_block_entries():
    class _BoomEngine(_FakeEngine):
        def get_market_mfi_values(self, _active_symbols=None):
            raise RuntimeError("engine broken")

    d = _daemon(
        redis=_FakeRedis(),
        engine=_BoomEngine(),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()  # must not raise

    assert published == 1  # compute failed -> ungated evaluation proceeds


@pytest.mark.asyncio
async def test_run_start_stop_lifecycle():
    """run() calls feed.start(), runs the loops, exits promptly on stop(), calls feed.stop()."""
    import asyncio
    import json

    feed = _FakeFeed()
    d = _daemon(
        feed=feed,
        eval_interval_seconds=0.01,
        universe_refresh_seconds=0.01,
        watchlist_reader=lambda: json.dumps({"strategies": {"w": ["005930"]}}),
    )
    # empty universe so evaluate_once is a no-op (no manager calls needed)
    d._universe = []

    task = asyncio.create_task(d.run())
    await asyncio.sleep(0.05)  # let eval + refresh loops tick a couple times
    await d.stop()
    await asyncio.wait_for(
        task, timeout=1.0
    )  # must return promptly — proves interruptible sleeps

    assert feed.started is True, "run() must call feed.start()"
    assert feed.stopped is True, "run() finally block must call feed.stop()"


# ---------------------------------------------------------------------------
# Warmth-based prewarm on universe refresh (Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_watchlist_prewarms_only_cold_symbols(monkeypatch):
    calls = []

    async def _prewarm(symbol):
        calls.append(symbol)

    # engine warm for 005930 only; universe will add 000660 + 005930
    # pass a realistic production-shape dict (parse_watchlist_codes path)
    daemon = _daemon(
        engine=_FakeEngine(warm=("005930",)),
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=5,
    )
    await daemon._apply_watchlist({"strategies": {"w": ["005930", "000660"]}})
    assert calls == ["000660"]  # warm 005930 skipped; only cold prewarmed


@pytest.mark.asyncio
async def test_prewarm_respects_per_cycle_cap():
    calls = []

    async def _prewarm(symbol):
        calls.append(symbol)

    daemon = _daemon(
        engine=_FakeEngine(warm=()),  # all cold
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=2,
    )
    await daemon._apply_watchlist({"strategies": {"w": ["a", "b", "c", "d"]}})
    assert len(calls) == 2  # capped; remainder retried next refresh (still cold)


@pytest.mark.asyncio
async def test_apply_watchlist_without_prewarm_fn_is_noop():
    daemon = _daemon(engine=_FakeEngine(warm=()), prewarm_fn=None)
    await daemon._apply_watchlist({"strategies": {"w": ["a", "b"]}})  # must not raise
    assert daemon._universe == ["a", "b"]


# ---------------------------------------------------------------------------
# Bear-gate override: strong-set publish + strong-only evaluation (Task 3)
# ---------------------------------------------------------------------------


def _async_return(v):
    async def _f(*a, **k):
        return v

    return _f


def _bear_payload():
    return json.dumps(
        {
            "regime": "BEAR_STRONG",
            "mfi": 28.0,
            "mfi_symbols": 9,
            "computed_at_ms": 1,
            "low_confidence": False,
        }
    )


@pytest.mark.asyncio
async def test_bear_cycle_evaluates_only_strong_when_override_enabled(monkeypatch):
    """Bear + override enabled: only strong symbols evaluated; strong set published."""
    from shared.streaming.stock_bear_override import BearOverrideConfig

    # daily indicators: 005930 is strong (above SMA20, RSI rising, MACD+, RSI>55)
    #                   066570 is weak (close < SMA20, RSI<55, RSI falling, MACD-)
    daily = {
        "indicators": {
            "005930": {
                "daily_close": 100,
                "daily_sma_20": 90,
                "daily_rsi_14": 70,
                "daily_prev_rsi_14": 65,
                "daily_macd_hist": 5,
            },
            "066570": {
                "daily_close": 80,
                "daily_sma_20": 90,
                "daily_rsi_14": 40,
                "daily_prev_rsi_14": 45,
                "daily_macd_hist": -3,
            },
        }
    }
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = json.dumps(daily)
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930", "066570")),
        manager=_FakeManager(fire_for=("005930", "066570")),
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(enabled=True),
    )
    daemon._universe = ["005930", "066570"]
    # force bear regime (bypass MFI compute)
    monkeypatch.setattr(
        daemon, "_publish_regime", _async_return(json.loads(_bear_payload()))
    )
    published = await daemon.evaluate_once()
    # only the strong symbol (005930) was evaluated/published, not 066570
    assert published == 1
    codes = [f.get("code") for _s, f in redis.added]
    assert codes == ["005930"]
    # strong set published to Redis
    assert "stock:daemon:bear_override" in redis.kv


@pytest.mark.asyncio
async def test_bear_cycle_disabled_override_still_blocks(monkeypatch):
    """Bear + override disabled: blanket block unchanged."""
    from shared.streaming.stock_bear_override import BearOverrideConfig

    daemon = _daemon(
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(enabled=False),
    )
    daemon._universe = ["005930"]
    monkeypatch.setattr(
        daemon, "_publish_regime", _async_return(json.loads(_bear_payload()))
    )
    assert await daemon.evaluate_once() == 0  # unchanged blanket block


@pytest.mark.asyncio
async def test_bear_cycle_cap_reached_blocks_new_override_entries(monkeypatch):
    """Bear + override enabled + cap reached: no new entries admitted."""
    from shared.streaming.stock_bear_override import BearOverrideConfig

    # 005930 is strong; an open position already exists in 005930; cap=1 → no new entries
    daily = {
        "indicators": {
            "005930": {
                "daily_close": 100,
                "daily_sma_20": 90,
                "daily_rsi_14": 70,
                "daily_prev_rsi_14": 65,
                "daily_macd_hist": 5,
            },
        }
    }
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = json.dumps(daily)

    # mock hkeys to return an open position in the strong symbol
    async def _hkeys(_k):
        return [b"005930"]

    redis.hkeys = _hkeys  # type: ignore[assignment]
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",)),
        manager=_FakeManager(fire_for=("005930",)),
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(enabled=True, max_override_positions=1),
    )
    daemon._universe = ["005930"]
    monkeypatch.setattr(
        daemon, "_publish_regime", _async_return(json.loads(_bear_payload()))
    )
    published = await daemon.evaluate_once()
    assert published == 0  # cap reached → no new override entries


# ---------------------------------------------------------------------------
# Daily indicators injected into the decoupled EntryContext (Fix #1)
#
# The decoupled M4-P daemon must mirror the orchestrator: merge the engine's
# daily indicators (sma_200, daily_*) into the per-symbol indicator dict so
# daily-gated strategies (pattern_pullback needs sma_200; momentum_breakout
# needs daily EMA/quality) can fire. Without this every symbol is rejected
# with no_sma_200 and the daemon produces 0 valid signals.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_indicators_merged_into_entry_context():
    """get_daily_indicators output is merged (daily_ prefix) into ctx.indicators."""
    manager = _CaptureManager()
    daily = {
        "005930": {
            "sma_200": 60000.0,
            "sma_20": 70000.0,
            "ema_5": 71000.0,
            "rsi_5": 40.0,
        }
    }
    d = _daemon(
        engine=_FakeEngine(warm=("005930",), daily=daily),
        manager=manager,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = manager.contexts["005930"]
    # Daily fields are present under the daily_ prefix (orchestrator convention),
    # alongside the base streaming indicators from the resolver.
    assert ctx.indicators["daily_sma_200"] == 60000.0
    assert ctx.indicators["daily_sma_20"] == 70000.0
    assert ctx.indicators["daily_ema_5"] == 71000.0
    assert ctx.indicators["rsi"] == 30.0  # base resolver indicators preserved


@pytest.mark.asyncio
async def test_daily_watchlist_injected_into_context_metadata():
    """The raw watchlist dict is injected into ctx.metadata['daily_watchlist']."""
    manager = _CaptureManager()
    d = _daemon(engine=_FakeEngine(warm=("005930",)), manager=manager)
    await d._apply_watchlist(
        {"strategies": {"momentum_breakout": ["005930", "000660"]}}
    )

    await d.evaluate_once()

    ctx = manager.contexts["005930"]
    watchlist = ctx.metadata["daily_watchlist"]
    assert watchlist["strategies"]["momentum_breakout"] == ["005930", "000660"]


# ---------------------------------------------------------------------------
# DailyScanner payload parity (Fix #1 fold-in)
#
# The orchestrator merges TWO daily sources: the DailyScanner Redis payload
# (system:daily_indicators:latest, already daily_-prefixed: daily_volume_ratio,
# daily_closes, daily_rsi_14, ...) AND the engine's get_daily_indicators.
# Without the scanner source, momentum_breakout's daily_volume_ratio_min filter
# fails open (admits low-volume breakouts the orchestrator rejects).
# ---------------------------------------------------------------------------


def _scanner_payload(indicators):
    return json.dumps({"indicators": indicators})


@pytest.mark.asyncio
async def test_scanner_daily_payload_merged_into_context():
    """DailyScanner fields (daily_volume_ratio, daily_closes) land in ctx.indicators."""
    manager = _CaptureManager()
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {
            "005930": {
                "daily_volume_ratio": 2.1,
                "daily_closes": [100.0, 101.0, 102.0],
                "daily_sma_60_prev": 64000.0,
                "daily_rsi_14": 62.0,
            }
        }
    )
    d = _daemon(redis=redis, engine=_FakeEngine(warm=("005930",)), manager=manager)
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = manager.contexts["005930"]
    assert ctx.indicators["daily_volume_ratio"] == 2.1
    assert ctx.indicators["daily_closes"] == [100.0, 101.0, 102.0]
    assert ctx.indicators["daily_sma_60_prev"] == 64000.0
    assert ctx.indicators["daily_rsi_14"] == 62.0


@pytest.mark.asyncio
async def test_engine_daily_wins_over_scanner_on_overlap():
    """Engine get_daily_indicators is merged last (wins) — orchestrator order."""
    manager = _CaptureManager()
    redis = _FakeRedis()
    # Scanner says sma_200=50000; engine (live) says 60000 → engine must win.
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"005930": {"daily_sma_200": 50000.0, "daily_volume_ratio": 1.8}}
    )
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=manager,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = manager.contexts["005930"]
    assert ctx.indicators["daily_sma_200"] == 60000.0  # engine wins
    assert ctx.indicators["daily_volume_ratio"] == 1.8  # scanner-only field kept


@pytest.mark.asyncio
async def test_missing_scanner_key_is_graceful():
    """No scanner key → no scanner fields, no crash (engine path still works)."""
    manager = _CaptureManager()
    redis = _FakeRedis()  # no daily_indicators key set
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=manager,
    )
    d._universe = ["005930"]

    await d.evaluate_once()  # must not raise

    ctx = manager.contexts["005930"]
    assert ctx.indicators["daily_sma_200"] == 60000.0
    assert "daily_volume_ratio" not in ctx.indicators


@pytest.mark.asyncio
async def test_malformed_scanner_payload_is_graceful():
    """Non-JSON / wrong-shaped scanner payload → ignored, no crash."""
    manager = _CaptureManager()
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = "not-json{"
    d = _daemon(redis=redis, engine=_FakeEngine(warm=("005930",)), manager=manager)
    d._universe = ["005930"]

    await d.evaluate_once()  # must not raise

    ctx = manager.contexts["005930"]
    assert not any(k.startswith("daily_") for k in ctx.indicators)


@pytest.mark.asyncio
async def test_scanner_read_once_per_cycle_not_per_symbol():
    """The scanner payload is read once per evaluate_once, not per universe symbol."""
    manager = _CaptureManager()

    class _CountingRedis(_FakeRedis):
        def __init__(self):
            super().__init__()
            self.daily_reads = 0

        async def get(self, k):
            if k == "system:daily_indicators:latest":
                self.daily_reads += 1
            return self.kv.get(k)

    redis = _CountingRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"005930": {"daily_volume_ratio": 2.0}, "000660": {"daily_volume_ratio": 2.0}}
    )
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930", "000660")),
        manager=manager,
    )
    d._universe = ["005930", "000660"]

    await d.evaluate_once()

    assert redis.daily_reads == 1  # one read for the whole cycle, not per symbol


@pytest.mark.asyncio
async def test_momentum_breakout_daily_volume_filter_engages_with_scanner_payload():
    """End-to-end: the scanner's daily_volume_ratio actually drives the filter.

    momentum_breakout.daily_volume_ratio_min rejects when the daily volume ratio
    is below the threshold and passes it when at/above — proving the decoupled
    daemon no longer silently bypasses the configured risk filter (parity with
    the orchestrator).
    """
    from datetime import datetime as _dt

    from shared.strategy.base import EntryContext
    from shared.strategy.entry.momentum_breakout import (
        MomentumBreakoutConfig,
        MomentumBreakoutEntry,
    )

    strat = MomentumBreakoutEntry(MomentumBreakoutConfig(daily_volume_ratio_min=1.5))
    now = _dt(2026, 6, 24, 1, 0, tzinfo=UTC)  # 10:00 KST, mid-session
    market = {"code": "005930", "name": "SamsungElec", "close": 71000.0}

    # Below the configured min → filter must reject.
    ctx_low = EntryContext(
        market_data=market,
        indicators={"daily_volume_ratio": 1.0},
        current_positions=[],
        timestamp=now,
        metadata={},
    )
    assert strat._passes_daily_quality_filters(ctx_low, "005930") is False

    # At/above the min → filter passes (other gates may still apply downstream).
    ctx_ok = EntryContext(
        market_data=market,
        indicators={"daily_volume_ratio": 1.6},
        current_positions=[],
        timestamp=now,
        metadata={},
    )
    assert strat._passes_daily_quality_filters(ctx_ok, "005930") is True


@pytest.mark.asyncio
async def test_missing_daily_indicators_leaves_context_without_daily_fields():
    """When the engine has no daily candles, no daily_ keys are injected (graceful)."""
    manager = _CaptureManager()
    d = _daemon(
        engine=_FakeEngine(warm=("005930",), daily={}),  # no daily data
        manager=manager,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = manager.contexts["005930"]
    assert not any(k.startswith("daily_") for k in ctx.indicators)
    assert "sma_200" not in ctx.indicators  # genuinely absent → strategy rejects


@pytest.mark.asyncio
async def test_legacy_engine_without_daily_indicators_does_not_crash():
    """Engines lacking get_daily_indicators must not break entry evaluation."""

    class _LegacyEngine:
        def is_warm(self, _symbol):
            return True

    manager = _CaptureManager()
    d = _daemon(engine=_LegacyEngine(), manager=manager)
    d._universe = ["005930"]

    await d.evaluate_once()  # must not raise

    ctx = manager.contexts["005930"]
    assert not any(k.startswith("daily_") for k in ctx.indicators)


@pytest.mark.asyncio
async def test_pattern_pullback_fires_only_with_daily_sma_200_injected():
    """End-to-end: pattern_pullback rejects without sma_200, fires once daily injected.

    Reproduces the decoupled no-signal bug: the strategy needs a daily sma_200 to
    pass its base-trend gate (close > sma_200). With the daily merge it can fire;
    without it the symbol is rejected (no_sma_200) and never signals.
    """
    from datetime import datetime as _dt

    from shared.strategy.base import EntryContext
    from shared.strategy.entry.pattern_pullback import (
        PatternPullbackConfig,
        PatternPullbackEntry,
    )

    strat = PatternPullbackEntry(
        PatternPullbackConfig(
            min_confidence=0.0,
            signal_cooldown_days=0,
            patterns=[{"name": "p0", "rsi5_max": 100.0, "confidence": 0.9}],
        )
    )
    now = _dt(2026, 6, 5, 0, 30, tzinfo=UTC)
    market = {"code": "005930", "name": "SamsungElec", "close": 71000.0}
    base_ind = {
        "sma_20": 72000.0,  # close (71000) <= sma_20 → pullback condition holds
        "sma_60": 65000.0,
        "sma_60_prev": 64000.0,
        "rsi_5": 30.0,
        "atr": 700.0,
        "highest_high": 72000.0,
        "volume_ratio": 1.5,
    }

    # Without sma_200 the base-trend gate fails (sma_200 <= 0) → no signal.
    ctx_no_daily = EntryContext(
        market_data=market,
        indicators=dict(base_ind),
        current_positions=[],
        timestamp=now,
        metadata={},
    )
    assert await strat.generate(ctx_no_daily) is None

    # With the daily sma_200 injected (close 71000 > sma_200 60000) → fires.
    ctx_daily = EntryContext(
        market_data=market,
        indicators={**base_ind, "daily_sma_200": 60000.0},
        current_positions=[],
        timestamp=now,
        metadata={},
    )
    sig = await strat.generate(ctx_daily)
    assert sig is not None
    assert sig.code == "005930"
