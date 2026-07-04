"""Tests for the trading startup sequence owner."""

from __future__ import annotations

import pytest


class FakeTradingOrchestrator:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.kis_config = object()
        self.data_source = object()

    def _init_kis_client(self) -> object:
        self.calls.append("kis_client")
        return self.kis_config

    def _validate_futures_product_contract(self) -> None:
        self.calls.append("futures_product_validation")

    def _init_futures_slippage_controller(self) -> None:
        self.calls.append("futures_slippage_controller")

    def _init_price_feeds(self, kis_config: object) -> object:
        assert kis_config is self.kis_config
        self.calls.append("price_feeds")
        return self.data_source

    def _init_data_provider(self, data_source: object) -> None:
        assert data_source is self.data_source
        self.calls.append("data_provider")

    def _init_tick_stream_publisher(self) -> None:
        self.calls.append("tick_stream_publisher")

    def _init_strategy_infrastructure(self) -> None:
        self.calls.append("strategy_infrastructure")

    def _init_indicator_engine(self) -> None:
        self.calls.append("indicator_engine")

    async def _init_execution_layer(self) -> None:
        self.calls.append("execution_layer")

    async def _ensure_db_schema(self) -> None:
        self.calls.append("ensure_db_schema")

    async def _load_swing_positions(self) -> None:
        self.calls.append("load_swing_positions")

    def _init_llm_context_publisher(self) -> None:
        self.calls.append("llm_context_publisher")


@pytest.mark.asyncio
async def test_startup_sequence_preserves_component_order_and_handoffs() -> None:
    from services.trading.startup_sequence import run_trading_startup_sequence

    orchestrator = FakeTradingOrchestrator()

    await run_trading_startup_sequence(orchestrator)

    assert orchestrator.calls == [
        "kis_client",
        "futures_product_validation",
        "futures_slippage_controller",
        "price_feeds",
        "data_provider",
        "tick_stream_publisher",
        "strategy_infrastructure",
        "indicator_engine",
        "execution_layer",
        "ensure_db_schema",
        "load_swing_positions",
        "llm_context_publisher",
    ]


@pytest.mark.asyncio
async def test_trading_orchestrator_initialize_components_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services.trading.orchestrator import TradingOrchestrator

    calls: list[object] = []

    async def fake_startup_sequence(orchestrator: object) -> None:
        calls.append(orchestrator)

    monkeypatch.setattr(
        "services.trading.orchestrator.run_trading_startup_sequence",
        fake_startup_sequence,
    )
    orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)

    await TradingOrchestrator._initialize_components(orchestrator)

    assert calls == [orchestrator]
