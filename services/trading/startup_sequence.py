"""Startup sequencing helpers for the trading orchestrator."""

from __future__ import annotations

from typing import Any


async def run_trading_startup_sequence(orchestrator: Any) -> None:
    """Initialize trading components in the orchestrator startup contract order."""
    kis_config = orchestrator._init_kis_client()

    orchestrator._validate_futures_product_contract()
    orchestrator._init_futures_slippage_controller()

    data_source = orchestrator._init_price_feeds(kis_config)
    orchestrator._init_data_provider(data_source)

    orchestrator._init_tick_stream_publisher()
    orchestrator._init_strategy_infrastructure()
    orchestrator._init_indicator_engine()

    await orchestrator._init_execution_layer()
    await orchestrator._ensure_db_schema()
    await orchestrator._load_swing_positions()

    orchestrator._init_llm_context_publisher()
