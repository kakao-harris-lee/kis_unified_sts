"""StockStrategyDaemon: per-symbol context build + publish; universe refresh."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from services.stock_strategy.daemon import LLMDiscoverySignalConfig, StockStrategyDaemon
from services.stock_strategy.universe import _SCREENER_PAYLOAD_KEY
from shared.models.signal import Signal
from shared.streaming.audit import decode_stream_id
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
        self.xadd_kwargs = []
        self.expires = []
        self.next_id = b"1719876543210-0"
        self.fail_expire = False
        self.kv = {}
        self.hashes: dict[str, dict[str, str]] = {}

    async def xadd(self, stream, fields, **kw):
        self.added.append((stream, fields))
        self.xadd_kwargs.append(kw)
        return self.next_id

    async def expire(self, *args, **kwargs):
        if self.fail_expire:
            raise ConnectionError("expire failed")
        self.expires.append((args, kwargs))
        return True

    async def set(self, key, value, **_kw):
        self.kv[key] = value
        return True

    async def get(self, k):
        return self.kv.get(k)

    async def hkeys(self, k):
        return []

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def hset(self, key, field=None, value=None, mapping=None, **_kw):
        bucket = self.hashes.setdefault(key, {})
        if mapping:
            bucket.update({str(k): str(v) for k, v in mapping.items()})
        elif field is not None:
            bucket[str(field)] = str(value) if value is not None else ""
        return 1


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
async def test_publish_logs_signal_published_audit_record(caplog):
    redis = _FakeRedis()
    d = _daemon(redis=redis)
    signal = Signal(
        code="005930",
        strategy="williams_r",
        price=71000.0,
        confidence=0.6,
        metadata={"signal_direction": "short"},
    )

    with caplog.at_level(logging.INFO, logger="services.stock_strategy.daemon"):
        await d._publish(signal)

    assert len(redis.added) == 1
    stream, fields = redis.added[0]
    assert redis.xadd_kwargs == [{"maxlen": 10_000, "approximate": True}]
    assert redis.expires == [(("signal.candidate.stock.shadow", 86400), {})]
    signal_id = fields["signal_id"]
    msg_id = decode_stream_id(redis.next_id)

    records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO
        and "event=signal_published" in record.getMessage()
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert f"stream={stream}" in message
    assert f"msg_id={msg_id}" in message
    assert f"signal_id={signal_id}" in message
    assert "code=005930" in message
    assert "strategy=williams_r" in message
    assert "direction=short" in message


@pytest.mark.asyncio
async def test_publish_does_not_log_success_when_ttl_refresh_fails(caplog):
    redis = _FakeRedis()
    redis.fail_expire = True
    d = _daemon(redis=redis)
    signal = Signal(
        code="005930",
        strategy="williams_r",
        price=71000.0,
        confidence=0.6,
    )

    with caplog.at_level(logging.INFO, logger="services.stock_strategy.daemon"):
        with pytest.raises(ConnectionError):
            await d._publish(signal)

    assert redis.xadd_kwargs == [{"maxlen": 10_000, "approximate": True}]
    assert not any(
        "event=signal_published" in record.getMessage() for record in caplog.records
    )


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


@pytest.mark.asyncio
async def test_empty_strategy_list_is_not_daily_gated():
    """An empty per-strategy list → dynamic (not gated), so an empty-list peer
    never yields spurious no_daily_watchlist rejects in the eval classifier.

    Regression for the decoupled-stock no-trade root cause: the live payload
    {trend_pullback: [1], momentum_breakout: []} gated momentum_breakout to
    no_daily_watchlist on every symbol.
    """
    d = _daemon()
    await d._apply_watchlist(
        {"strategies": {"trend_pullback": ["005930"], "momentum_breakout": []}}
    )
    gated = d._daily_gated_strategies()
    assert gated == {"trend_pullback": {"005930"}}
    assert "momentum_breakout" not in gated  # empty → dynamic, not gated


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
async def test_llm_discovered_target_publishes_without_technical_warmth():
    """LLM-only trade targets can emit candidates without strategy warmup data."""
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 111700.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True,
            min_llm_quality=0.5,
            min_llm_confidence=0.8,
            max_per_cycle=5,
            cooldown_seconds=86400.0,
        ),
    )

    await daemon._apply_watchlist(
        {
            "strategies": {"_screener_trade_targets": ["080220"]},
            _SCREENER_PAYLOAD_KEY: {
                "codes": ["080220"],
                "names": {"080220": "제주반도체"},
                "scores": {"080220": 0.62},
                "metadata": {
                    "080220": {
                        "llm_quality": 0.61859,
                        "llm_confidence": 1.0,
                        "llm_effective_quality": 0.61859,
                        "llm_only": True,
                        "entry_price": 112900.0,
                        "stop_loss": 104997.0,
                        "take_profit": 126448.0,
                    }
                },
            },
        }
    )

    published = await daemon.evaluate_once()

    assert published == 1
    stream, fields = redis.added[0]
    assert stream == "signal.candidate.stock.shadow"
    assert fields["code"] == "080220"
    assert fields["name"] == "제주반도체"
    assert fields["strategy"] == "llm_discovered"
    # Execution price anchors to the live tick (71000.0 from the fake feed);
    # the LLM plan's entry/stop/target are still preserved in metadata.
    assert fields["price"] == "71000.0"
    assert fields["confidence"] == "1.0"
    metadata = json.loads(fields["metadata_json"])
    assert metadata["source"] == "trade_targets_llm"
    assert metadata["reference_price_source"] == "live_tick"
    assert metadata["entry_price"] == 112900.0
    assert metadata["llm_quality"] == 0.61859
    assert metadata["llm_only"] is True
    assert metadata["stop_loss"] == 104997.0
    assert metadata["take_profit"] == 126448.0


@pytest.mark.asyncio
async def test_llm_discovered_target_respects_cooldown():
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 111700.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True, cooldown_seconds=86400.0
        ),
    )
    await daemon._apply_watchlist(
        {
            "strategies": {"_screener_trade_targets": ["080220"]},
            _SCREENER_PAYLOAD_KEY: {
                "codes": ["080220"],
                "names": {"080220": "제주반도체"},
                "metadata": {
                    "080220": {
                        "llm_quality": 0.9,
                        "llm_confidence": 1.0,
                    }
                },
            },
        }
    )

    assert await daemon.evaluate_once() == 1
    assert await daemon.evaluate_once() == 0
    assert len(redis.added) == 1


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


# ---------------------------------------------------------------------------
# Per-(symbol, strategy) signal-eval observability (stock:daemon:signal_eval)
#
# Mirrors the futures trading:futures:setup_eval reject-reason pattern. The
# daemon records, per evaluated (symbol, strategy), whether it fired or rejected
# (and why), then publishes an aggregate hash so the operator can read
# "for each strategy, how many symbols rejected and the dominant reason" — the
# instrument missing from the 2026-06-24 no-trade diagnosis. Read-only telemetry:
# it must not change the candidate stream the daemon already publishes.
# ---------------------------------------------------------------------------

from shared.streaming.stock_signal_eval import (  # noqa: E402
    REJECT_BEAR_CAP_REACHED,
    REJECT_BEAR_REGIME,
    REJECT_BEAR_RS_GATE,
    REJECT_COLD,
    REJECT_CONDITIONS_NOT_MET,
    REJECT_NO_DAILY_WATCHLIST,
    REJECT_NO_MARKET_DATA,
    REJECT_NO_SMA_200,
    StockSignalEvalConfig,
)

_EVAL_CFG = StockSignalEvalConfig()


class _RosterManager:
    """Fake manager with a strategy roster (mirrors StrategyManager.strategies).

    ``fire_map`` maps {strategy_name: set(symbols_that_fire)}; any roster
    strategy not firing for a symbol is a reject the daemon must classify.
    """

    def __init__(self, fire_map=None, daily_gated=()):
        self._fire_map = {k: set(v) for k, v in (fire_map or {}).items()}
        roster = set(self._fire_map) | {"momentum_breakout", "pattern_pullback"}
        # The daemon iterates manager.strategies (name -> object) and reads each
        # object's required_indicators to decide sma_200 dependence. Only
        # pattern_pullback gates on sma_200 (mirrors production); momentum_breakout
        # and williams_r do not — so only pattern_pullback can reject no_sma_200.
        self.strategies = {
            name: _StratStub(
                name,
                required=(("sma_200",) if name == "pattern_pullback" else ()),
            )
            for name in roster
        }
        self._daily_gated = set(daily_gated)

    async def check_entries(self, context):
        code = context.market_data.get("code")
        out = []
        for name, fires in self._fire_map.items():
            if code in fires:
                out.append(Signal(code=code, strategy=name, price=71000.0))
        return out


class _StratStub:
    def __init__(self, name, required=()):
        self.name = name
        self.required_indicators = list(required)


def _eval_summary(redis):
    """Decode the published stock:daemon:signal_eval hash → {strategy: dict}."""
    raw = redis.hashes.get(_EVAL_CFG.redis_key, {})
    return {k: json.loads(v) for k, v in raw.items()}


class _HashRedis(_FakeRedis):
    """_FakeRedis + hset/hget/hgetall + expire tracking for the eval hash."""

    def __init__(self):
        super().__init__()
        # Override parent's hashes dict with same name — both paths share it.
        self.hashes: dict[str, dict[str, str]] = {}
        self.expires: dict[str, int] = {}

    async def hset(self, key, field=None, value=None, mapping=None, **_kw):
        bucket = self.hashes.setdefault(key, {})
        if mapping:
            bucket.update({str(k): str(v) for k, v in mapping.items()})
        elif field is not None:
            bucket[str(field)] = str(value) if value is not None else ""
        return len(mapping or ({"x": "x"} if field is not None else {}))

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(str(field))

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def expire(self, key, ttl):
        self.expires[key] = ttl
        return True


def _eval_daemon(**kw):
    defaults = {
        "redis": _HashRedis(),
        "feed": _FakeFeed(),
        "engine": _FakeEngine(),
        "resolver": _FakeResolver(),
        "manager": _RosterManager(),
        "candidate_stream": "signal.candidate.stock.shadow",
        "candidate_maxlen": 10_000,
        "now_fn": lambda: _NOW,
        "signal_eval_config": _EVAL_CFG,
    }
    defaults.update(kw)
    return StockStrategyDaemon(**defaults)


@pytest.mark.asyncio
async def test_signal_eval_records_signal_for_firing_strategy():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    assert summary["williams_r"]["outcome"] == "signal"
    assert summary["williams_r"]["signals"] == 1


@pytest.mark.asyncio
async def test_signal_eval_records_reject_reason_for_non_firing_strategy():
    redis = _HashRedis()
    # daily sma_200 present → reject reason is the residual "conditions_not_met",
    # NOT no_sma_200 (proves the daemon distinguishes them).
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    # pattern_pullback is in the roster but did not fire → reject recorded.
    assert summary["pattern_pullback"]["outcome"] == "reject"
    assert summary["pattern_pullback"]["rejects"] == 1
    assert summary["pattern_pullback"]["reason"] == REJECT_CONDITIONS_NOT_MET


@pytest.mark.asyncio
async def test_signal_eval_records_no_sma_200_only_for_sma200_dependent_strategy():
    redis = _HashRedis()
    # No daily indicators at all. Only sma_200-dependent strategies (here
    # pattern_pullback) reject no_sma_200; strategies that ignore SMA(200)
    # (momentum_breakout) fall through to conditions_not_met — so the diagnosis's
    # headline reject is never over-counted for non-SMA strategies.
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={}),
        manager=_RosterManager(fire_map={}),  # nothing fires
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_NO_SMA_200
    assert summary["momentum_breakout"]["reason"] == REJECT_CONDITIONS_NOT_MET


@pytest.mark.asyncio
async def test_signal_eval_records_cold_for_not_warm_symbol():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),  # cold
        manager=_RosterManager(fire_map={}),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    # Cold symbols are skipped before generators run; recorded per roster strategy.
    assert summary["pattern_pullback"]["reason"] == REJECT_COLD
    assert summary["pattern_pullback"]["rejects"] == 1


@pytest.mark.asyncio
async def test_signal_eval_records_no_market_data():
    class _NoPriceFeed(_FakeFeed):
        async def get_current_price(self, _symbol):
            return None

    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        feed=_NoPriceFeed(),
        engine=_FakeEngine(warm=("005930",)),
        manager=_RosterManager(fire_map={}),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_NO_MARKET_DATA


@pytest.mark.asyncio
async def test_signal_eval_records_not_in_daily_watchlist():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={}),
    )
    # momentum_breakout daily-gated to a DIFFERENT symbol → 005930 not in its list.
    await d._apply_watchlist({"strategies": {"momentum_breakout": ["000660"]}})
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    assert summary["momentum_breakout"]["reason"] == REJECT_NO_DAILY_WATCHLIST
    # pattern_pullback is NOT in the watchlist's strategies map → not daily-gated
    # → it falls through to the generator-condition reason, not the watchlist one.
    assert summary["pattern_pullback"]["reason"] == REJECT_CONDITIONS_NOT_MET


@pytest.mark.asyncio
async def test_signal_eval_records_bear_regime_skip():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 28.0, "000660": 30.0}),
        regime_config=_REGIME_CFG,
        manager=_RosterManager(fire_map={}),
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()

    assert published == 0  # bear gate still blocks entries (unchanged decision)
    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_BEAR_REGIME


@pytest.mark.asyncio
async def test_signal_eval_records_bear_cap_reached(monkeypatch):
    """Bear + override cap reached records bear_cap_reached (distinct from selectivity)."""
    from shared.streaming.stock_bear_override import BearOverrideConfig

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
    redis = _HashRedis()
    redis.kv["system:daily_indicators:latest"] = json.dumps(daily)

    async def _hkeys(_k):
        return [b"005930"]  # an open position already in the strong symbol

    redis.hkeys = _hkeys  # type: ignore[assignment]
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",)),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(enabled=True, max_override_positions=1),
    )
    d._universe = ["005930"]
    monkeypatch.setattr(
        d, "_publish_regime", _async_return(json.loads(_bear_payload()))
    )

    published = await d.evaluate_once()

    assert published == 0  # cap reached → no new override entries (unchanged decision)
    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_BEAR_CAP_REACHED


@pytest.mark.asyncio
async def test_signal_eval_publishes_with_ttl():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    assert redis.expires.get(_EVAL_CFG.redis_key) == _EVAL_CFG.publish_ttl_seconds


@pytest.mark.asyncio
async def test_signal_eval_disabled_publishes_nothing():
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
        signal_eval_config=StockSignalEvalConfig(enabled=False),
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    assert _EVAL_CFG.redis_key not in redis.hashes


@pytest.mark.asyncio
async def test_signal_eval_no_config_is_inert():
    """Without a signal_eval_config (None) the daemon publishes no eval hash."""
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
        signal_eval_config=None,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    assert _EVAL_CFG.redis_key not in redis.hashes


@pytest.mark.asyncio
async def test_signal_eval_does_not_change_candidate_publishing():
    """Telemetry is read-only: the candidate stream is unaffected by eval on/off."""
    engine = _FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}})
    manager = _RosterManager(fire_map={"williams_r": {"005930"}})

    redis_on = _HashRedis()
    d_on = _eval_daemon(redis=redis_on, engine=engine, manager=manager)
    d_on._universe = ["005930"]
    await d_on.evaluate_once()

    redis_off = _HashRedis()
    d_off = _eval_daemon(
        redis=redis_off,
        engine=engine,
        manager=manager,
        signal_eval_config=None,
    )
    d_off._universe = ["005930"]
    await d_off.evaluate_once()

    on_codes = sorted(f["code"] for _s, f in redis_on.added)
    off_codes = sorted(f["code"] for _s, f in redis_off.added)
    assert on_codes == off_codes == ["005930"]


@pytest.mark.asyncio
async def test_signal_eval_publish_failure_does_not_break_evaluation():
    """A Redis failure in the eval publish must not affect signal publishing."""

    class _HsetBoomRedis(_HashRedis):
        async def hset(self, *_a, **_k):
            raise RuntimeError("redis down")

    redis = _HsetBoomRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_RosterManager(fire_map={"williams_r": {"005930"}}),
    )
    d._universe = ["005930"]

    published = await d.evaluate_once()  # must not raise

    assert published == 1  # candidate still published despite eval publish failure


@pytest.mark.asyncio
async def test_signal_eval_legacy_manager_without_roster_still_records_fired():
    """A manager lacking .strategies still records fired strategies (graceful)."""
    redis = _HashRedis()
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",), daily={"005930": {"sma_200": 60000.0}}),
        manager=_FakeManager(fire_for=("005930",)),  # no .strategies attribute
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    summary = _eval_summary(redis)
    # _FakeManager fires a williams_r signal → recorded as a signal outcome.
    assert summary["williams_r"]["outcome"] == "signal"


# ---------------------------------------------------------------------------
# Prewarm-on-eval: evaluate_once calls _prewarm_cold for cold symbols
#
# Root cause (2026-06-25 surge day): _prewarm_cold was called only from
# _apply_watchlist (universe refresh, ~30s).  evaluate_once just skipped cold
# symbols and recorded REJECT_COLD without retrying prewarm.  Intraday screener
# adds with no parquet data stayed cold for many eval cycles while REST prewarm
# was only attempted once per 30s refresh, not on every 60s eval pass.
#
# Fix: evaluate_once calls _prewarm_cold at the start of every cycle so cold
# symbols get a prewarm attempt each time they are encountered.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_once_prewarmsold_cold_symbols_before_eval():
    """evaluate_once triggers prewarm for cold symbols, not just universe refresh."""
    prewarm_calls = []

    async def _prewarm(symbol: str):
        prewarm_calls.append(symbol)

    d = _daemon(
        engine=_FakeEngine(warm=()),  # all cold
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=5,
    )
    d._universe = ["005930", "000660"]

    await d.evaluate_once()

    # Both cold symbols must have been prewarmed during the eval cycle.
    assert "005930" in prewarm_calls
    assert "000660" in prewarm_calls


@pytest.mark.asyncio
async def test_evaluate_once_prewarm_respects_cap():
    """Per-cycle cap on prewarm is respected inside evaluate_once."""
    prewarm_calls = []

    async def _prewarm(symbol: str):
        prewarm_calls.append(symbol)

    d = _daemon(
        engine=_FakeEngine(warm=()),  # all cold
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=2,
    )
    d._universe = ["a", "b", "c", "d"]

    await d.evaluate_once()

    assert len(prewarm_calls) == 2  # capped at max_prewarm_per_cycle


@pytest.mark.asyncio
async def test_evaluate_once_skips_prewarm_when_all_warm():
    """No prewarm calls when every universe symbol is already warm."""
    prewarm_calls = []

    async def _prewarm(symbol: str):
        prewarm_calls.append(symbol)

    d = _daemon(
        engine=_FakeEngine(warm=("005930", "000660")),
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=5,
    )
    d._universe = ["005930", "000660"]

    await d.evaluate_once()

    assert prewarm_calls == []  # all warm → prewarm not invoked


@pytest.mark.asyncio
async def test_evaluate_once_prewarm_failure_does_not_abort_eval():
    """A prewarm failure inside evaluate_once must not stop entry evaluation."""

    async def _boom(symbol: str):
        raise RuntimeError("prewarm exploded")

    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        # 005930 warm (can produce signals), 000660 cold → prewarm attempted
        engine=_FakeEngine(warm=("005930",)),
        prewarm_fn=_boom,
        max_prewarm_per_cycle=5,
    )
    d._universe = ["005930", "000660"]

    # Must not raise; 005930 (warm) still fires its signal.
    published = await d.evaluate_once()
    assert published == 1
    assert any(f["code"] == "005930" for _s, f in redis.added)


@pytest.mark.asyncio
async def test_evaluate_once_prewarm_called_even_when_no_prewarm_fn():
    """When prewarm_fn is None, evaluate_once completes without error."""
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",)),
        prewarm_fn=None,
    )
    d._universe = ["005930", "000660"]

    published = await d.evaluate_once()

    # 005930 warm → signal published; 000660 cold → skipped (no prewarm_fn, silent)
    assert published == 1


# ---------------------------------------------------------------------------
# C1: LLM-discovery ships dormant (enabled=False is the new default)
# ---------------------------------------------------------------------------


def _llm_watchlist_payload():
    return {
        "strategies": {"_screener_trade_targets": ["080220"]},
        _SCREENER_PAYLOAD_KEY: {
            "codes": ["080220"],
            "names": {"080220": "TestCo"},
            "metadata": {
                "080220": {
                    "llm_quality": 0.9,
                    "llm_confidence": 1.0,
                    "llm_only": True,
                    "entry_price": 10000.0,
                }
            },
        },
    }


@pytest.mark.asyncio
async def test_llm_discovery_disabled_by_default_emits_nothing():
    """LLMDiscoverySignalConfig.enabled defaults to False — no signals emitted.

    Matches the project convention that new features ship dormant and require
    explicit operator opt-in (same as Setup D / bear-override).
    """
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        # Default LLMDiscoverySignalConfig() — enabled is False
        llm_signal_config=LLMDiscoverySignalConfig(),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    published = await daemon.evaluate_once()

    assert published == 0
    assert redis.added == []  # no candidate stream messages


@pytest.mark.asyncio
async def test_llm_discovery_enabled_true_emits_signal():
    """Sanity: enabled=True opts back in and emits the expected signal."""
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(enabled=True),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    published = await daemon.evaluate_once()

    assert published == 1
    assert redis.added[0][1]["code"] == "080220"


# ---------------------------------------------------------------------------
# C2: LLM-discovery cooldown persisted to Redis (survives daemon restart)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_cooldown_written_to_redis_on_emit():
    """After emitting a signal the cooldown timestamp is written to the Redis hash."""
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True, cooldown_seconds=86400.0
        ),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    published = await daemon.evaluate_once()

    assert published == 1
    # Cooldown hash must contain the symbol with a float-parseable timestamp.
    stored = redis.hashes.get("stock:daemon:llm_cooldown", {}).get("080220")
    assert stored is not None
    assert float(stored) == _NOW.timestamp()


@pytest.mark.asyncio
async def test_llm_cooldown_read_from_redis_pre_seeded():
    """Pre-seeding the cooldown hash blocks emission for that symbol.

    Simulates the case where Redis already holds a recent timestamp from a
    previous daemon run — the cooldown is honoured across restarts.
    """
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    # Pre-seed: 1 hour ago — still within 24h cooldown
    recent_ts = _NOW.timestamp() - 3600.0
    redis.hashes["stock:daemon:llm_cooldown"] = {"080220": str(recent_ts)}

    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True, cooldown_seconds=86400.0
        ),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    published = await daemon.evaluate_once()

    assert published == 0  # cooldown from Redis prevents emission
    assert redis.added == []


@pytest.mark.asyncio
async def test_llm_cooldown_survives_daemon_restart():
    """A fresh daemon sharing the same Redis still honours the cooldown.

    The first daemon emits and writes to Redis.  A second daemon (simulating a
    restart) is constructed with the same Redis instance but a fresh in-memory
    state — it must still skip the symbol due to the persisted Redis entry.
    """
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    cfg = LLMDiscoverySignalConfig(enabled=True, cooldown_seconds=86400.0)

    # First daemon: emits signal, writes cooldown to Redis.
    d1 = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=cfg,
    )
    await d1._apply_watchlist(_llm_watchlist_payload())
    assert await d1.evaluate_once() == 1

    # Second daemon: fresh in-memory state, same Redis → cooldown persisted.
    d2 = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=cfg,
    )
    await d2._apply_watchlist(_llm_watchlist_payload())
    assert await d2.evaluate_once() == 0  # cooldown from Redis blocks re-emit


@pytest.mark.asyncio
async def test_llm_cooldown_redis_read_failure_falls_back_gracefully():
    """A Redis HGET failure degrades to allow-on-error (best-effort), no crash."""

    class _HgetBoomRedis(_FakeRedis):
        async def hget(self, _key, _field):
            raise RuntimeError("redis down")

    redis = _HgetBoomRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True, cooldown_seconds=86400.0
        ),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    # Must not raise; best-effort allows emission when Redis is unreachable.
    published = await daemon.evaluate_once()
    assert published == 1  # degraded to allow-on-error


# ---------------------------------------------------------------------------
# Regime injected into EntryContext (revives momentum_breakout / williams_r)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regime_injected_into_entry_context_metadata():
    """The computed regime is exposed to strategies as metadata.regime /
    metadata.market_state — without it, regime-gated strategies fail closed."""
    capture = _CaptureManager()
    d = _daemon(
        engine=_FakeEngine(mfi_values={"005930": 55.0, "000660": 60.0}),
        manager=capture,
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = capture.contexts["005930"]
    assert ctx.metadata["regime"] == "BULL_STRONG"
    assert ctx.metadata["market_state"] == "BULL_STRONG"


@pytest.mark.asyncio
async def test_regime_metadata_is_none_when_regime_disabled():
    """No regime config → regime keys present but None (strategies self-gate)."""
    capture = _CaptureManager()
    d = _daemon(manager=capture, regime_config=None)
    d._universe = ["005930"]

    await d.evaluate_once()

    ctx = capture.contexts["005930"]
    assert ctx.metadata["regime"] is None
    assert ctx.metadata["market_state"] is None


@pytest.mark.asyncio
async def test_llm_discovery_prefers_live_tick_over_reference_price():
    """The LLM-discovery buy anchors to a live tick when available rather than
    the (possibly stale) plan entry_price / daily_close reference."""
    redis = _FakeRedis()
    redis.kv["system:daily_indicators:latest"] = _scanner_payload(
        {"080220": {"daily_close": 10000.0}}
    )
    daemon = _daemon(
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_FakeManager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(enabled=True),
    )
    await daemon._apply_watchlist(_llm_watchlist_payload())

    published = await daemon.evaluate_once()

    assert published == 1
    fields = redis.added[0][1]
    assert fields["code"] == "080220"
    # _FakeFeed returns a live close of 71000.0; it must win over entry_price 10000.0.
    assert float(fields["price"]) == 71000.0
    assert "live_tick" in fields["metadata_json"]


# ---------------------------------------------------------------------------
# RS gate (bear_rs_gate) — bear override symbol below min_change_pct_for_rs
# ---------------------------------------------------------------------------


def _bear_daily():
    """Daily indicators for 005930 that pass the strong-set filter."""
    return {
        "indicators": {
            "005930": {
                "daily_close": 100,
                "daily_sma_20": 90,
                "daily_rsi_14": 70,
                "daily_prev_rsi_14": 65,
                "daily_macd_hist": 5,
            }
        }
    }


def _trade_targets_with_change_pct(change_pct):
    """Minimal trade_targets payload with change_pct for 005930."""
    return json.dumps({"metadata": {"005930": {"change_pct": change_pct}}})


def _make_rs_daemon(redis, change_pct, threshold, monkeypatch):
    """Helper: bear override daemon with RS gate, change_pct injected via _trade_targets_payload."""
    from shared.streaming.stock_bear_override import BearOverrideConfig

    redis.kv["system:daily_indicators:latest"] = json.dumps(_bear_daily())
    d = _eval_daemon(
        redis=redis,
        engine=_FakeEngine(warm=("005930",)),
        manager=_RosterManager(fire_map={"pattern_pullback": {"005930"}}),
        regime_config=StockRegimeConfig(),
        bear_override_config=BearOverrideConfig(
            enabled=True, min_change_pct_for_rs=threshold
        ),
    )
    d._universe = ["005930"]
    # Inject trade_targets payload directly (bypasses _apply_watchlist).
    if change_pct is not None:
        d._trade_targets_payload = {"metadata": {"005930": {"change_pct": change_pct}}}
    else:
        d._trade_targets_payload = {"metadata": {}}
    monkeypatch.setattr(d, "_publish_regime", _async_return(json.loads(_bear_payload())))
    return d


@pytest.mark.asyncio
async def test_bear_rs_gate_rejects_symbol_below_threshold(monkeypatch):
    """Bear override symbol with change_pct below threshold → REJECT_BEAR_RS_GATE."""
    redis = _HashRedis()
    d = _make_rs_daemon(redis, change_pct=0.1, threshold=0.3, monkeypatch=monkeypatch)

    published = await d.evaluate_once()

    assert published == 0
    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_BEAR_RS_GATE


@pytest.mark.asyncio
async def test_bear_rs_gate_passes_symbol_above_threshold(monkeypatch):
    """Bear override symbol with change_pct above threshold → evaluated normally."""
    redis = _HashRedis()
    d = _make_rs_daemon(redis, change_pct=0.5, threshold=0.3, monkeypatch=monkeypatch)

    await d.evaluate_once()

    summary = _eval_summary(redis)
    # Symbol passes RS gate — rejection reason is strategy selectivity, not RS gate.
    assert summary["pattern_pullback"]["reason"] != REJECT_BEAR_RS_GATE


@pytest.mark.asyncio
async def test_bear_rs_gate_noop_when_threshold_zero(monkeypatch):
    """min_change_pct_for_rs=0.0 (default) — gate block not entered, symbol evaluated."""
    redis = _HashRedis()
    # change_pct=0.0 would fail a 0.3 threshold, but gate is disabled here.
    d = _make_rs_daemon(redis, change_pct=0.0, threshold=0.0, monkeypatch=monkeypatch)

    await d.evaluate_once()

    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] != REJECT_BEAR_RS_GATE


@pytest.mark.asyncio
async def test_bear_rs_gate_missing_change_pct_defaults_to_zero(monkeypatch):
    """Symbol absent from trade_targets metadata → change_pct=0.0 → rejected by gate."""
    redis = _HashRedis()
    d = _make_rs_daemon(redis, change_pct=None, threshold=0.3, monkeypatch=monkeypatch)

    published = await d.evaluate_once()

    assert published == 0
    summary = _eval_summary(redis)
    assert summary["pattern_pullback"]["reason"] == REJECT_BEAR_RS_GATE
