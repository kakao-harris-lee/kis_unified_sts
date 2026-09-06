"""O13 (2026-09-06 operator decision): monolithic futures paper/live path must
feed the same ``risk:state:futures`` Redis hash that ``services/order_router``
writes and ``services/kill_switch`` reads.

Before this wiring, ``TradingOrchestrator._record_risk_realized_pnl`` only
updated the in-process ``RiskManager`` entry gate — a closed futures trade in
the monolithic runtime never reached the durable Redis state, so
``services/kill_switch`` (a separate process, Redis-only) could never observe
it and its daily/weekly/monthly-loss and consecutive-loss conditions were
dead code against this runtime.

These tests pin:
  1. ``_init_futures_runtime_risk_state`` wires a ``RuntimeRiskState`` against
     ``self._guard_redis`` (no second connection) when
     ``risk_management.yaml::risk_state.monolithic_writer_enabled`` is on
     (default), resolving the KRW-per-point multiplier from
     ``config/execution.yaml``'s ``futures_contract_spec`` — the same source
     ``shared.execution.pseudo_oco.PseudoOCO`` uses for the decoupled path.
  2. The config flag can turn the writer off (falls back to pre-O13 behavior).
  3. It is never wired for ``asset_class="stock"``.
  4. ``_record_risk_realized_pnl`` converts the orchestrator's native
     points-based P&L (``Position.unrealized_pnl`` for futures) to KRW before
     writing, and drives win/loss exactly like
     ``PseudoOCO._record_pnl``/``shared.risk.runtime_state.RuntimeRiskState``.
  5. Parity: a monolithic-orchestrator-recorded losing trade produces the
     identical ``risk:state:futures`` hash contents as the same trade recorded
     through the decoupled order_router's writer, and
     ``services/kill_switch`` conditions trip identically against either.
  6. Multiplier guard: a resolved ``multiplier_krw_per_point <= 0`` must not
     wire the writer (``_init_futures_runtime_risk_state``) and
     ``_record_risk_realized_pnl`` must not touch a writer that is somehow
     wired with a non-positive multiplier — a zeroed multiplier makes every
     trade's ``pnl_krw`` come out ``0.0``, which is always ``record_win()``
     and silently resets ``consecutive_losses`` on every trade, disabling the
     kill_switch's 6-consecutive-loss condition (independent-review finding,
     2026-09-06).
  7. Daily reset: ``_reset_futures_daily_risk_state_at_session_start`` resets
     ``risk:state:futures`` once per new KST calendar day and is a no-op
     (idempotent, no double-reset) on a same-day re-call — mirroring the M5c
     cron (``scripts/maintenance/daily_risk_reset.py``) and
     ``stock_risk_filter``'s per-cycle guard (independent-review finding,
     2026-09-06).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

from services.kill_switch.main import ConsecutiveLossesCondition, DailyLossCondition
from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.risk.runtime_state import RuntimeRiskState

_KST = ZoneInfo("Asia/Seoul")


def _futures_orchestrator() -> TradingOrchestrator:
    config = TradingConfig.futures(initial_capital=10_000_000)
    return TradingOrchestrator(config)


def _stock_orchestrator() -> TradingOrchestrator:
    config = TradingConfig.stock(initial_capital=10_000_000)
    return TradingOrchestrator(config)


class TestInitFuturesRuntimeRiskState:
    def test_wires_writer_when_enabled_default(self):
        """Default config (no override) wires the writer against _guard_redis."""
        orch = _futures_orchestrator()
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._init_futures_runtime_risk_state()

        assert isinstance(orch._futures_risk_state, RuntimeRiskState)
        # mini product (FUTURES_TRADING_PRODUCT unset -> default) = 50,000 KRW/pt.
        assert orch._futures_risk_state_multiplier_krw == 50_000.0
        # Reuses the guard connection — no second Redis client.
        assert orch._futures_risk_state._redis is orch._guard_redis

    def test_disabled_via_config_stays_none(self, monkeypatch):
        from shared.config.loader import ConfigLoader

        real_load = ConfigLoader.load

        def fake_load(name, *args, **kwargs):
            data = real_load(name, *args, **kwargs)
            if name == "risk_management.yaml":
                data = dict(data)
                rm = dict(data["risk_management"])
                rm["risk_state"] = {"monolithic_writer_enabled": "false"}
                data["risk_management"] = rm
            return data

        monkeypatch.setattr(ConfigLoader, "load", staticmethod(fake_load))

        orch = _futures_orchestrator()
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._init_futures_runtime_risk_state()

        assert orch._futures_risk_state is None
        assert orch._futures_risk_state_multiplier_krw == 0.0

    def test_bad_symbol_degrades_to_none_without_raising(self, monkeypatch):
        orch = _futures_orchestrator()
        orch.config.symbols = ["NOT_A_REAL_SYMBOL"]
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._init_futures_runtime_risk_state()  # must not raise

        assert orch._futures_risk_state is None
        assert orch._futures_risk_state_multiplier_krw == 0.0


class TestRecordRiskRealizedPnlFuturesRiskState:
    @pytest.mark.asyncio
    async def test_converts_points_to_krw_and_writes_loss(self):
        orch = _futures_orchestrator()
        orch._risk_manager = None  # isolate the new sink
        orch._futures_risk_state = RuntimeRiskState(
            redis=fakeredis.aioredis.FakeRedis(db=1), asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = 50_000.0

        await orch._record_risk_realized_pnl(-2.0)  # -2 index points

        snap = await orch._futures_risk_state.snapshot()
        assert snap.daily_pnl_krw == -100_000.0
        assert snap.weekly_pnl_krw == -100_000.0
        assert snap.consecutive_losses == 1
        assert snap.daily_trade_count == 1

    @pytest.mark.asyncio
    async def test_win_resets_consecutive_losses(self):
        orch = _futures_orchestrator()
        orch._risk_manager = None
        orch._futures_risk_state = RuntimeRiskState(
            redis=fakeredis.aioredis.FakeRedis(db=1), asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = 50_000.0

        await orch._record_risk_realized_pnl(-1.0)
        await orch._record_risk_realized_pnl(3.0)

        snap = await orch._futures_risk_state.snapshot()
        assert snap.consecutive_losses == 0
        assert snap.daily_pnl_krw == 100_000.0  # (-1 + 3) * 50,000

    @pytest.mark.asyncio
    async def test_noop_when_not_wired(self):
        """asset_class=stock (or any un-wired orchestrator) must not error."""
        orch = _stock_orchestrator()
        orch._risk_manager = None
        assert orch._futures_risk_state is None

        await orch._record_risk_realized_pnl(-500_000)  # must not raise

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise_or_block_risk_manager(self):
        """A broken kill-switch sink must not lose the in-process risk update."""
        from unittest.mock import AsyncMock

        from shared.risk.config import RiskConfig
        from shared.risk.manager import RiskManager

        orch = _futures_orchestrator()
        orch._risk_manager = RiskManager(
            RiskConfig(initial_capital=10_000_000, max_total_positions=20)
        )
        orch._risk_manager.save_to_redis = AsyncMock()

        broken_state = AsyncMock()
        broken_state.record_trade.side_effect = ConnectionError("redis down")
        orch._futures_risk_state = broken_state
        orch._futures_risk_state_multiplier_krw = 50_000.0

        await orch._record_risk_realized_pnl(-2.0)  # must not raise

        assert orch._risk_manager.get_risk_state().daily_realized_pnl == -2.0
        orch._risk_manager.save_to_redis.assert_awaited_once()


class TestKillSwitchParityWithOrderRouterWriter:
    """Same trade recorded via the monolithic path and the order_router path
    must land in an identical ``risk:state:futures`` hash, and kill_switch
    conditions must trip identically against either.
    """

    @pytest.mark.asyncio
    async def test_same_trade_same_hash_same_kill_switch_verdict(self):
        equity_krw = 100_000_000.0
        multiplier = 50_000.0
        loss_points = -70.0  # -3,500,000 KRW -> trips a 3% daily-loss condition

        # -- Monolithic orchestrator path --------------------------------
        redis_a = fakeredis.aioredis.FakeRedis(db=1)
        orch = _futures_orchestrator()
        orch._risk_manager = None
        orch._futures_risk_state = RuntimeRiskState(
            redis=redis_a, asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = multiplier
        await orch._record_risk_realized_pnl(loss_points)

        # -- Decoupled order_router / PseudoOCO path (same shared writer) --
        redis_b = fakeredis.aioredis.FakeRedis(db=1)
        router_state = RuntimeRiskState(redis=redis_b, asset_class="futures")
        pnl_krw = loss_points * multiplier
        await router_state.record_trade(pnl_krw=pnl_krw)
        await router_state.record_loss()

        hash_a = await redis_a.hgetall("risk:state:futures")
        hash_b = await redis_b.hgetall("risk:state:futures")
        assert hash_a == hash_b

        snap_a = await orch._futures_risk_state.snapshot()
        snap_b = await router_state.snapshot()
        assert snap_a == snap_b

        daily_cond = DailyLossCondition(limit_pct=0.03, equity_krw=equity_krw)
        consec_cond = ConsecutiveLossesCondition(threshold=10)

        assert daily_cond.check(snapshot=snap_a) is True
        assert daily_cond.check(snapshot=snap_b) is True
        assert consec_cond.check(snapshot=snap_a) is False
        assert consec_cond.check(snapshot=snap_b) is False


class TestMultiplierGuard:
    """A non-positive multiplier_krw_per_point must never wire, or be used
    by, the O13 writer — see module docstring pin 6.
    """

    def test_zero_multiplier_symbol_stays_unwired(self, monkeypatch, caplog):
        from shared.instruments.contract_spec import ContractSpec

        zero_spec = ContractSpec(
            name="zero_mult_test",
            multiplier_krw_per_point=0,
            tick_size_points=0.02,
            tick_value_krw=0,
            commission_rate=0.00003,
            symbol_prefix="A05",
        )
        monkeypatch.setattr(
            "shared.execution.contract_spec.resolve_contract_spec",
            lambda symbol, registry: zero_spec,
        )

        orch = _futures_orchestrator()
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        with caplog.at_level("WARNING"):
            orch._init_futures_runtime_risk_state()

        assert orch._futures_risk_state is None
        assert orch._futures_risk_state_multiplier_krw == 0.0
        assert any(
            "NOT wired" in r.getMessage() and "not positive" in r.getMessage()
            for r in caplog.records
        )

    def test_negative_multiplier_symbol_stays_unwired(self, monkeypatch):
        from shared.instruments.contract_spec import ContractSpec

        negative_spec = ContractSpec(
            name="negative_mult_test",
            multiplier_krw_per_point=-50_000,
            tick_size_points=0.02,
            tick_value_krw=1000,
            commission_rate=0.00003,
            symbol_prefix="A05",
        )
        monkeypatch.setattr(
            "shared.execution.contract_spec.resolve_contract_spec",
            lambda symbol, registry: negative_spec,
        )

        orch = _futures_orchestrator()
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._init_futures_runtime_risk_state()  # must not raise

        assert orch._futures_risk_state is None
        assert orch._futures_risk_state_multiplier_krw == 0.0

    @pytest.mark.asyncio
    async def test_record_risk_realized_pnl_skips_zero_multiplier_writer(self):
        """Defensive branch: even if a writer somehow got wired with a
        non-positive multiplier, _record_risk_realized_pnl must not call
        record_trade/record_loss/record_win against it (would post
        pnl_krw=0.0 -> record_win() -> masks consecutive losses).
        """
        orch = _futures_orchestrator()
        orch._risk_manager = None
        broken_writer = AsyncMock()
        orch._futures_risk_state = broken_writer
        orch._futures_risk_state_multiplier_krw = 0.0

        await orch._record_risk_realized_pnl(-5.0)

        broken_writer.record_trade.assert_not_called()
        broken_writer.record_loss.assert_not_called()
        broken_writer.record_win.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_risk_realized_pnl_unchanged_for_positive_multiplier(self):
        """Sanity check: a positive multiplier keeps writing (unchanged
        behavior vs. before this guard was added).
        """
        orch = _futures_orchestrator()
        orch._risk_manager = None
        orch._futures_risk_state = RuntimeRiskState(
            redis=fakeredis.aioredis.FakeRedis(db=1), asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = 50_000.0

        await orch._record_risk_realized_pnl(-2.0)

        snap = await orch._futures_risk_state.snapshot()
        assert snap.daily_pnl_krw == -100_000.0
        assert snap.consecutive_losses == 1


class TestFuturesDailyRiskStateResetAtSessionStart:
    """``_reset_futures_daily_risk_state_at_session_start`` — see module
    docstring pin 7.
    """

    @pytest.mark.asyncio
    async def test_noop_when_writer_not_wired(self):
        orch = _futures_orchestrator()
        assert orch._futures_risk_state is None

        # Must not raise even though there is nothing to reset against.
        await orch._reset_futures_daily_risk_state_at_session_start()

    @pytest.mark.asyncio
    async def test_new_kst_day_resets_daily_counters(self):
        redis_client = fakeredis.aioredis.FakeRedis(db=1)
        orch = _futures_orchestrator()
        orch._risk_manager = None
        orch._futures_risk_state = RuntimeRiskState(
            redis=redis_client, asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = 50_000.0

        day1 = datetime(2026, 9, 5, 8, 45, tzinfo=_KST)
        # Simulate yesterday's session already having traded.
        await orch._futures_risk_state.record_trade(pnl_krw=-1_000_000.0)
        snap_before = await orch._futures_risk_state.snapshot()
        assert snap_before.daily_pnl_krw == -1_000_000.0
        # Stamp yesterday's reset explicitly (as if day1's own session-start
        # reset had already run).
        await orch._futures_risk_state.reset_daily(now_kst=day1)
        await orch._futures_risk_state.record_trade(pnl_krw=-1_000_000.0)

        day2 = datetime(2026, 9, 6, 8, 45, tzinfo=_KST)
        await orch._reset_futures_daily_risk_state_at_session_start(now_kst=day2)

        snap_after = await orch._futures_risk_state.snapshot()
        assert snap_after.daily_pnl_krw == 0.0
        assert snap_after.daily_trade_count == 0
        # Cumulative fields must survive the daily reset.
        assert snap_after.weekly_pnl_krw == -2_000_000.0

    @pytest.mark.asyncio
    async def test_same_kst_day_recall_is_noop(self):
        redis_client = fakeredis.aioredis.FakeRedis(db=1)
        orch = _futures_orchestrator()
        orch._risk_manager = None
        orch._futures_risk_state = RuntimeRiskState(
            redis=redis_client, asset_class="futures"
        )
        orch._futures_risk_state_multiplier_krw = 50_000.0

        today = datetime(2026, 9, 6, 8, 45, tzinfo=_KST)
        await orch._reset_futures_daily_risk_state_at_session_start(now_kst=today)
        await orch._futures_risk_state.record_trade(pnl_krw=-500_000.0)

        # A same-day re-call (e.g. a mid-day process restart) must not wipe
        # the counters _record_trade just accumulated.
        later_same_day = datetime(2026, 9, 6, 13, 0, tzinfo=_KST)
        await orch._reset_futures_daily_risk_state_at_session_start(
            now_kst=later_same_day
        )

        snap = await orch._futures_risk_state.snapshot()
        assert snap.daily_pnl_krw == -500_000.0
        assert snap.daily_trade_count == 1

    @pytest.mark.asyncio
    async def test_redis_failure_is_swallowed(self):
        orch = _futures_orchestrator()
        orch._risk_manager = None
        broken_state = AsyncMock()
        broken_state.should_reset_daily.side_effect = ConnectionError("redis down")
        orch._futures_risk_state = broken_state

        # Must not raise — best-effort, same discipline as
        # _record_risk_realized_pnl's O13 sink.
        await orch._reset_futures_daily_risk_state_at_session_start(
            now_kst=datetime(2026, 9, 6, 8, 45, tzinfo=_KST)
        )
