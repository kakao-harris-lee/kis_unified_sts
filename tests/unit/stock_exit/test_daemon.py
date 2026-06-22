"""StockExitDaemon: stop-loss -> SELL + HDEL + record_loss + exit fill; not-filled -> no close."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from services.stock_exit.daemon import StockExitDaemon
from shared.execution.fill_logger import FillLogger
from shared.paper.broker import VirtualBroker
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
from shared.streaming.stock_bear_override import (
    BearOverrideConfig,
    compute_override_payload,
)
from shared.streaming.stock_regime import StockRegimeConfig

_KST = ZoneInfo("Asia/Seoul")
_MID_SESSION = datetime(2025, 6, 9, 13, 0, tzinfo=_KST)


@pytest.fixture(autouse=True)
def _pin_mid_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the exit strategy clock to mid-session KST.

    ``ThreeStageExit.scan_positions`` reads wall-clock via ``now_kst()`` and the
    EOD cutoff is bounded by the exchange close (``effective_close_time`` caps any
    config to 15:30 KST), so a test config of ``eod_close_hour=23`` cannot disable
    EOD after 15:30 KST. Without this pin the suite fails every afternoon/evening
    KST when EOD flattens the seeded position. 13:00 KST keeps every cycle in
    session regardless of when CI runs.
    """
    monkeypatch.setattr(
        "shared.strategy.exit.three_stage.now_kst",
        lambda: _MID_SESSION,
    )


def _seed_record(code: str = "005930", entry: float = 71000.0) -> dict[str, object]:
    return {
        "code": code,
        "entry_price": entry,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "SURVIVAL",
        "signal_id": f"sig-{code}",
    }


class _FakeFeed:
    """Minimal price-feed stand-in: a settable price cache."""

    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}

    def update_symbols(self, symbols: list[str]) -> None:
        pass

    async def get_current_price(self, symbol: str) -> dict[str, float]:
        return dict(self.prices.get(symbol, {}))

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


def _build_daemon(
    redis,
    *,
    broker=None,
    fill_logger=None,
    exit_strategy=None,
    regime_config=None,
    runtime_ledger=None,
    bear_override_config=None,
) -> StockExitDaemon:
    return StockExitDaemon(
        redis=redis,
        feed=_FakeFeed(),
        exit_strategy=exit_strategy
        or ThreeStageExit(
            ThreeStageExitConfig(enable_bear_exit=False, eod_exempt_maximize=True)
        ),
        broker=broker or VirtualBroker(slippage_rate=0.0001),
        fill_logger=fill_logger
        or FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key="trading:stock:positions",
        interval_seconds=1.0,
        now_fn=lambda: _MID_SESSION,
        regime_config=regime_config,
        runtime_ledger=runtime_ledger,
        bear_override_config=bear_override_config,
    )


class _FakeLedger:
    """Captures record_trade calls (sync, as the real SQLite ledger is)."""

    def __init__(self) -> None:
        self.trades: list[dict] = []

    def record_trade(self, trade: dict) -> str:
        self.trades.append(trade)
        return str(trade.get("trade_id", ""))


@pytest.mark.asyncio
async def test_closed_trade_recorded_to_ledger_with_strategy() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    ledger = _FakeLedger()
    daemon = _build_daemon(redis, runtime_ledger=ledger)
    record = {**_seed_record(), "strategy": "pattern_pullback", "name": "삼성전자"}
    await redis.hset("trading:stock:positions", "005930", json.dumps(record))
    daemon.feed.prices["005930"] = {"close": 69580.0}  # -2% -> STOP_LOSS

    await daemon.run_cycle()

    # The decoupled close must land in the ledger trades table (the dashboard
    # /api/trades source) carrying the originating strategy.
    assert len(ledger.trades) == 1
    trade = ledger.trades[0]
    assert trade["strategy"] == "pattern_pullback"
    assert trade["symbol"] == "005930"
    assert trade["asset_class"] == "stock"
    assert trade["exit_reason"]
    assert trade["pnl"] < 0  # closed at a loss
    assert trade["idempotency_key"] == "sig-005930"


@pytest.mark.asyncio
async def test_no_ledger_does_not_crash_close() -> None:
    # runtime_ledger is optional; a close with no ledger configured still works.
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, runtime_ledger=None)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}
    await daemon.run_cycle()
    assert not await redis.hexists("trading:stock:positions", "005930")


@pytest.mark.asyncio
async def test_stop_loss_sells_closes_and_records_loss() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}  # -2% -> STOP_LOSS

    await daemon.run_cycle()

    assert not await redis.hexists("trading:stock:positions", "005930")
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert fills[0][1][b"side"] == b"SELL"
    assert fills[0][1][b"trade_role"] == b"exit"
    snap = await daemon.runtime_state.snapshot()
    assert snap.daily_pnl_krw < 0
    assert snap.consecutive_losses == 1


@pytest.mark.asyncio
async def test_no_price_no_action() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    await daemon.run_cycle()
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_unfilled_sell_does_not_close() -> None:
    redis = fakeredis.aioredis.FakeRedis()

    class _UnfilledBroker:
        async def submit_order(self, **_):
            class _O:
                filled = False
                rejection_reason = "no_fill"
                fill_price = None
                order_id = ""

            return _O()

    daemon = _build_daemon(redis, broker=_UnfilledBroker())
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 69580.0}
    await daemon.run_cycle()
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_high_water_persisted() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    # EOD is neutralised by the autouse mid-session clock pin (not by
    # eod_close_hour — effective_close_time caps it to the 15:30 KST close).
    daemon = StockExitDaemon(
        redis=redis,
        feed=_FakeFeed(),
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(
                enable_bear_exit=False,
                eod_exempt_maximize=True,
                eod_close_hour=23,
                eod_close_minute=59,
                time_cut_minutes=99999,
            )
        ),
        broker=VirtualBroker(slippage_rate=0.0001),
        fill_logger=FillLogger(
            redis=redis,
            stream="order.fill.stock.shadow",
            maxlen=1000,
            asset_class="stock",
        ),
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        positions_key="trading:stock:positions",
        interval_seconds=1.0,
    )
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 72000.0}  # +1.4% -> SURVIVAL, no exit
    await daemon.run_cycle()
    rec = json.loads(await redis.hget("trading:stock:positions", "005930"))
    assert rec["high_water"] == 72000.0


# ---------------------------------------------------------------------------
# Bear-exit regime wiring (M4-P publishes -> M4-X consumes)
# ---------------------------------------------------------------------------

_REGIME_CFG = StockRegimeConfig()  # defaults: max_age_seconds=300


def _bear_exit_daemon(redis, *, regime_config=_REGIME_CFG) -> StockExitDaemon:
    return _build_daemon(
        redis,
        exit_strategy=ThreeStageExit(
            ThreeStageExitConfig(enable_bear_exit=True, eod_exempt_maximize=True)
        ),
        regime_config=regime_config,
    )


def _regime_payload(regime: str, age_seconds: float) -> str:
    now_ms = int(_MID_SESSION.timestamp() * 1000)
    return json.dumps(
        {"regime": regime, "computed_at_ms": now_ms - int(age_seconds * 1000)}
    )


@pytest.mark.asyncio
async def test_fresh_bear_regime_liquidates_position() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    # +0.4% — no stop-loss, profit>0 so TIME_CUT can't fire; only BEAR_EXIT applies
    daemon.feed.prices["005930"] = {"close": 71300.0}
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", 10))

    await daemon.run_cycle()

    assert not await redis.hexists("trading:stock:positions", "005930")
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
    assert fills[0][1][b"side"] == b"SELL"


@pytest.mark.asyncio
async def test_stale_bear_regime_does_not_liquidate() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}
    stale_age = _REGIME_CFG.max_age_seconds + 60
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", stale_age))

    await daemon.run_cycle()

    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_non_bear_regime_does_not_liquidate() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("SIDEWAYS_DOWN", 10))

    await daemon.run_cycle()

    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_missing_regime_key_does_not_liquidate() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}

    await daemon.run_cycle()

    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_regime_read_failure_does_not_liquidate() -> None:
    """redis.get raising must yield no regime — never liquidate on read errors."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", 10))

    class _GetBoomRedis:
        """Delegates everything to fakeredis except ``get``, which raises."""

        def __init__(self, inner):
            self._inner = inner

        async def get(self, _key):
            raise RuntimeError("redis down")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    daemon.redis = _GetBoomRedis(redis)

    await daemon.run_cycle()  # must not raise

    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_no_regime_config_keeps_market_state_none() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _bear_exit_daemon(redis, regime_config=None)
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}
    # bear payload present but the daemon has no regime config -> ignored
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", 10))

    await daemon.run_cycle()

    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


# ---------------------------------------------------------------------------
# Bear override: _load_bear_override (M4-P publishes strong set -> M4-X reads)
# ---------------------------------------------------------------------------

_OVERRIDE_CFG = BearOverrideConfig(enabled=True, max_age_seconds=300.0)


def _override_payload(symbols: set[str], age_seconds: float) -> str:
    now_ms = int(_MID_SESSION.timestamp() * 1000)
    payload = compute_override_payload(symbols, now_ms=now_ms - int(age_seconds * 1000))
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_load_bear_override_fresh_returns_set() -> None:
    """Fresh payload within max_age_seconds returns the strong-symbol set."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, bear_override_config=_OVERRIDE_CFG)
    payload = _override_payload({"005930", "035420"}, age_seconds=10)
    await redis.set(_OVERRIDE_CFG.redis_key, payload)

    result = await daemon._load_bear_override()

    assert result == {"005930", "035420"}


@pytest.mark.asyncio
async def test_load_bear_override_stale_returns_empty() -> None:
    """Payload older than max_age_seconds returns empty set (fail-safe)."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, bear_override_config=_OVERRIDE_CFG)
    stale_age = _OVERRIDE_CFG.max_age_seconds + 60
    payload = _override_payload({"005930"}, age_seconds=stale_age)
    await redis.set(_OVERRIDE_CFG.redis_key, payload)

    result = await daemon._load_bear_override()

    assert result == set()


@pytest.mark.asyncio
async def test_load_bear_override_missing_key_returns_empty() -> None:
    """Missing Redis key returns empty set (fail-safe)."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, bear_override_config=_OVERRIDE_CFG)
    # no key set

    result = await daemon._load_bear_override()

    assert result == set()


@pytest.mark.asyncio
async def test_load_bear_override_disabled_config_returns_empty() -> None:
    """enabled=False config returns empty set regardless of Redis contents."""
    redis = fakeredis.aioredis.FakeRedis()
    disabled_cfg = BearOverrideConfig(enabled=False)
    daemon = _build_daemon(redis, bear_override_config=disabled_cfg)
    payload = _override_payload({"005930"}, age_seconds=10)
    await redis.set(disabled_cfg.redis_key, payload)

    result = await daemon._load_bear_override()

    assert result == set()


@pytest.mark.asyncio
async def test_load_bear_override_none_config_returns_empty() -> None:
    """None bear_override_config returns empty set (feature disabled)."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, bear_override_config=None)

    result = await daemon._load_bear_override()

    assert result == set()


@pytest.mark.asyncio
async def test_load_bear_override_redis_failure_returns_empty() -> None:
    """Redis read error returns empty set — never exempt on bad data."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, bear_override_config=_OVERRIDE_CFG)

    class _GetBoomRedis:
        def __init__(self, inner):
            self._inner = inner

        async def get(self, _key):
            raise RuntimeError("redis down")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    daemon.redis = _GetBoomRedis(redis)

    result = await daemon._load_bear_override()

    assert result == set()


@pytest.mark.asyncio
async def test_bear_override_exempts_strong_symbol_from_bear_exit() -> None:
    """Symbol in override set is NOT liquidated even in BEAR_STRONG regime."""
    redis = fakeredis.aioredis.FakeRedis()
    # Use bear-exit enabled strategy
    exit_strategy = ThreeStageExit(
        ThreeStageExitConfig(enable_bear_exit=True, eod_exempt_maximize=True)
    )
    daemon = _build_daemon(
        redis,
        exit_strategy=exit_strategy,
        regime_config=_REGIME_CFG,
        bear_override_config=_OVERRIDE_CFG,
    )
    # Seed a position that would otherwise be liquidated by BEAR_STRONG
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}  # +0.4%, above stop
    # Publish BEAR_STRONG regime
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", 10))
    # Publish override set including the symbol
    await redis.set(
        _OVERRIDE_CFG.redis_key, _override_payload({"005930"}, age_seconds=10)
    )

    await daemon.run_cycle()

    # Position must survive because it's in the override set
    assert await redis.hexists("trading:stock:positions", "005930")
    assert await redis.xrange("order.fill.stock.shadow") == []


@pytest.mark.asyncio
async def test_bear_override_does_not_protect_non_override_symbol() -> None:
    """Symbol NOT in override set is still liquidated in BEAR_STRONG regime."""
    redis = fakeredis.aioredis.FakeRedis()
    exit_strategy = ThreeStageExit(
        ThreeStageExitConfig(enable_bear_exit=True, eod_exempt_maximize=True)
    )
    daemon = _build_daemon(
        redis,
        exit_strategy=exit_strategy,
        regime_config=_REGIME_CFG,
        bear_override_config=_OVERRIDE_CFG,
    )
    await redis.hset("trading:stock:positions", "005930", json.dumps(_seed_record()))
    daemon.feed.prices["005930"] = {"close": 71300.0}
    await redis.set(_REGIME_CFG.redis_key, _regime_payload("BEAR_STRONG", 10))
    # Override set has a *different* symbol, not 005930
    await redis.set(
        _OVERRIDE_CFG.redis_key, _override_payload({"035420"}, age_seconds=10)
    )

    await daemon.run_cycle()

    # 005930 is NOT in override -> should be liquidated
    assert not await redis.hexists("trading:stock:positions", "005930")
    fills = await redis.xrange("order.fill.stock.shadow")
    assert len(fills) == 1
