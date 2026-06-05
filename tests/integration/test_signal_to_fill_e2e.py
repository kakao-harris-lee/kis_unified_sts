"""End-to-end integration test: decision_engine → risk_filter → order_router → fill.

Phase 4 Task 18 — wires Group {10-13} daemons together with fakeredis +
AsyncMock KIS, drives one signal through the full pipeline, and asserts the
contract at each boundary:

  1. decision_engine emits Signal → stream:signal.candidate
  2. risk_filter accepts → stream:signal.final
  3. order_router consumes → PassiveMaker.place_passive_limit_futures
  4. PassiveMaker fills → FillLogger writes stream:order.fill
  5. PseudoOCO bracket registered

Redis state is observed via fakeredis xrange.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.decision_engine.main import DecisionEngineDaemon
from services.order_router.main import OrderRouterDaemon
from services.risk_filter.main import RiskFilterDaemon
from shared.backtest.signals_writer import SignalsAllWriter
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.fill_logger import FillLogger
from shared.execution.passive_maker import Fill, PassiveMaker
from shared.execution.pseudo_oco import PseudoOCO
from shared.risk.layer import LayerResult, RiskFilterLayer

CANDIDATE = "stream:signal.candidate"
FINAL = "stream:signal.final"
ORDER_FILL = "stream:order.fill"


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


class _SetupAlwaysFires(Setup):
    CONFIG_CLASS = type("_C", (), {})

    def check(self, ctx):
        return Signal(
            setup_type="A_gap_reversion",
            direction="long",
            symbol="A05603",
            entry_price=331.20,
            stop_loss=330.50,
            take_profit=332.50,
            confidence=0.85,
            valid_until=ctx.now + timedelta(hours=1),
            generated_at=ctx.now,
        )


class _StubLayer(RiskFilterLayer):
    def __init__(self):
        super().__init__(filters=[])

    def evaluate(self, signal, snapshot):  # noqa: ARG002
        return LayerResult(passed=True, skip_reason=None, size_multiplier=1.0)


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.mark.asyncio
async def test_signal_to_fill_pipeline(redis):
    # --- 1. decision_engine ---
    # Provider yields ONE context then None forever, so only one signal fires.
    contexts_remaining = [
        SimpleNamespace(
            now=datetime(2026, 4, 28, 9, 30, tzinfo=UTC),
            symbol="A05603",
        )
    ]

    async def context_provider():
        return contexts_remaining.pop(0) if contexts_remaining else None

    decision = DecisionEngineDaemon(
        redis=redis,
        setups=[_SetupAlwaysFires()],
        context_provider=context_provider,
        candidate_stream=CANDIDATE,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )

    # --- 2. risk_filter ---
    signals_writer = SignalsAllWriter(batch_size=1)
    runtime_state = AsyncMock()
    runtime_state.snapshot = AsyncMock(return_value=SimpleNamespace())
    risk_filter = RiskFilterDaemon(
        redis=redis,
        layer=_StubLayer(),
        signals_writer=signals_writer,
        runtime_state=runtime_state,
        candidate_stream=CANDIDATE,
        final_stream=FINAL,
        consumer_group="risk_filter",
        worker_id="rf-1",
        final_maxlen=1000,
        xread_block_ms=10,
        batch_size=10,
    )

    # --- 3+4. order_router (PassiveMaker + FillLogger + PseudoOCO) ---
    fill_logger = FillLogger(redis=redis, stream=ORDER_FILL, batch_size=1)
    kis = AsyncMock()
    kis.get_futures_orderbook.return_value = SimpleNamespace(
        bid=[SimpleNamespace(price=331.20)],
        ask=[SimpleNamespace(price=331.22)],
    )
    kis.place_futures_order.return_value = "ORD-E2E-1"
    kis.await_fill.return_value = Fill(
        order_id="ORD-E2E-1", price=331.20, quantity=1, filled_at_ms=2000
    )
    passive = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(fill_logger=fill_logger)

    order_router = OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL,
        consumer_group="order_router",
        worker_id="or-1",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
    )

    # --- run all 3 daemons briefly ---
    async def _stop_after():
        await asyncio.sleep(0.1)
        await decision.stop()
        await risk_filter.stop()
        await order_router.stop()

    await asyncio.gather(
        decision.run(),
        risk_filter.run(),
        order_router.run(),
        _stop_after(),
    )

    # --- assertions: pipeline produced one full chain ---

    # decision_engine emitted at least one candidate
    candidates = await redis.xrange(CANDIDATE)
    assert len(candidates) >= 1
    candidate_signal_id = candidates[0][1][b"signal_id"].decode()

    # risk_filter forwarded to final stream with the SAME signal_id
    finals = await redis.xrange(FINAL)
    assert len(finals) >= 1
    assert finals[0][1][b"signal_id"].decode() == candidate_signal_id

    # order_router placed a passive limit
    kis.place_futures_order.assert_awaited()
    placed_kwargs = kis.place_futures_order.call_args.kwargs
    assert placed_kwargs["order_type"] == "limit"
    assert placed_kwargs["symbol"] == "A05603"

    # FillLogger wrote stream:order.fill
    fills = await redis.xrange(ORDER_FILL)
    assert len(fills) >= 1
    assert fills[0][1][b"signal_id"].decode() == candidate_signal_id

    # PseudoOCO has an active bracket
    assert len(pseudo_oco.active_handles) == 1
    handle = pseudo_oco.active_handles[0]
    assert handle.symbol == "A05603"
    assert handle.signal_id == candidate_signal_id


@pytest.mark.asyncio
async def test_kill_switch_sentinel_blocks_order_router(redis, tmp_path):
    """Pre-existing sentinel must keep order_router from consuming the final stream."""
    sentinel = tmp_path / "tripped"
    sentinel.write_text("previous trip")

    # Pre-populate the final stream (simulating pre-trip messages)
    await redis.xadd(
        FINAL,
        {
            "setup_type": "A_gap_reversion",
            "direction": "long",
            "symbol": "A05603",
            "entry_price": "331.20",
            "stop_loss": "330.50",
            "take_profit": "332.50",
            "confidence": "0.85",
            "generated_at_ms": "1700000000000",
            "valid_until_ms": "1700000100000",
            "reason_tags_json": "[]",
            "signal_id": "sig-pre-trip",
            "size_multiplier": "1.0",
            "filtered_at_ms": "1700000000000",
        },
    )

    fill_logger = FillLogger(redis=redis, batch_size=1)
    kis = AsyncMock()
    passive = PassiveMaker(kis_client=kis, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(fill_logger=fill_logger)
    order_router = OrderRouterDaemon(
        redis=redis,
        passive_maker=passive,
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream=FINAL,
        consumer_group="order_router",
        worker_id="or-blocked",
        xread_block_ms=10,
        batch_size=10,
        passive_timeout_seconds=5,
        kill_switch_sentinel_path=str(sentinel),
    )

    await order_router.run()

    assert order_router.refused_due_to_sentinel is True
    kis.place_futures_order.assert_not_awaited()
