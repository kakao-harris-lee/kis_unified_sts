"""StockStrategyDaemon: per-symbol context build + publish; universe refresh."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from services.stock_strategy.daemon import StockStrategyDaemon
from shared.models.signal import Signal
from shared.streaming.stock_regime import StockRegimeConfig

_NOW = datetime(2026, 6, 5, 0, 30, tzinfo=UTC)


class _FakeEngine:
    def __init__(self, warm=("005930",), mfi_values=None, latest_tick_ts=None):
        self._warm = set(warm)
        self._mfi_values = mfi_values
        self._latest_tick_ts = latest_tick_ts

    def is_warm(self, symbol):
        return symbol in self._warm

    def get_market_mfi_values(self, _active_symbols=None):
        return dict(self._mfi_values or {})

    def get_market_latest_tick_ts(self, _active_symbols=None):
        return self._latest_tick_ts


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


def test_refresh_universe_updates_feed():
    feed = _FakeFeed()
    d = _daemon(feed=feed)
    import json

    d._apply_watchlist(json.dumps({"strategies": {"w": ["005930", "000660"]}}))
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
        regime_config=StockRegimeConfig(
            min_mfi_symbols=2, block_entries_in_bear=False
        ),
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


# ---------------------------------------------------------------------------
# Candle-freshness observability (issue #460)
# ---------------------------------------------------------------------------

_BULL_MFI = {"005930": 55.0, "000660": 60.0}


@pytest.mark.asyncio
async def test_payload_includes_last_tick_ts_from_engine():
    tick_ts = _NOW - timedelta(seconds=42)
    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        engine=_FakeEngine(mfi_values=_BULL_MFI, latest_tick_ts=tick_ts),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    await d.evaluate_once()

    payload = json.loads(redis.kv[_REGIME_CFG.redis_key])
    assert payload["last_tick_ts_ms"] == int(tick_ts.timestamp() * 1000)


@pytest.mark.asyncio
async def test_payload_last_tick_none_when_engine_lacks_support():
    class _MfiOnlyEngine:
        def is_warm(self, _symbol):
            return True

        def get_market_mfi_values(self, _active_symbols=None):
            return dict(_BULL_MFI)

    redis = _FakeRedis()
    d = _daemon(redis=redis, engine=_MfiOnlyEngine(), regime_config=_REGIME_CFG)
    d._universe = ["005930"]

    await d.evaluate_once()

    payload = json.loads(redis.kv[_REGIME_CFG.redis_key])
    assert payload["last_tick_ts_ms"] is None  # old-schema engines stay valid


@pytest.mark.asyncio
async def test_lag_warning_emitted_in_session(monkeypatch, caplog):
    monkeypatch.setattr(
        "services.stock_strategy.daemon.is_regular_session_open", lambda _dt: True
    )
    d = _daemon(
        engine=_FakeEngine(
            mfi_values=_BULL_MFI, latest_tick_ts=_NOW - timedelta(seconds=600)
        ),
        regime_config=_REGIME_CFG,  # warn_indicator_lag_seconds default 180
    )
    d._universe = ["005930"]

    with caplog.at_level(logging.WARNING, logger="services.stock_strategy.daemon"):
        await d.evaluate_once()

    assert "indicator lag" in caplog.text
    assert "600s" in caplog.text


@pytest.mark.asyncio
async def test_lag_warning_suppressed_off_session(monkeypatch, caplog):
    monkeypatch.setattr(
        "services.stock_strategy.daemon.is_regular_session_open", lambda _dt: False
    )
    d = _daemon(
        engine=_FakeEngine(
            mfi_values=_BULL_MFI, latest_tick_ts=_NOW - timedelta(seconds=600)
        ),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    with caplog.at_level(logging.WARNING, logger="services.stock_strategy.daemon"):
        await d.evaluate_once()

    assert "indicator lag" not in caplog.text  # off-hours: stream silent by design


@pytest.mark.asyncio
async def test_no_lag_warning_below_threshold(monkeypatch, caplog):
    monkeypatch.setattr(
        "services.stock_strategy.daemon.is_regular_session_open", lambda _dt: True
    )
    d = _daemon(
        engine=_FakeEngine(
            mfi_values=_BULL_MFI, latest_tick_ts=_NOW - timedelta(seconds=30)
        ),
        regime_config=_REGIME_CFG,
    )
    d._universe = ["005930"]

    with caplog.at_level(logging.WARNING, logger="services.stock_strategy.daemon"):
        await d.evaluate_once()

    assert "indicator lag" not in caplog.text


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
