"""Owner tests for trading initialization runtime helpers."""

from __future__ import annotations

from services.trading.initialization_runtime import (
    ExecutionLayerInputs,
    execution_layer_mode,
    should_require_futures_contract_validation,
)


def test_execution_layer_mode_prefers_futures_live_guard() -> None:
    mode = execution_layer_mode(
        ExecutionLayerInputs(
            asset_class="futures",
            use_real_broker=False,
            futures_live_enabled=True,
        )
    )

    assert mode == "futures_live"


def test_execution_layer_mode_keeps_paper_default() -> None:
    mode = execution_layer_mode(
        ExecutionLayerInputs(
            asset_class="stock",
            use_real_broker=False,
            futures_live_enabled=False,
        )
    )

    assert mode == "paper"


def test_execution_layer_mode_uses_real_broker_after_live_guard() -> None:
    mode = execution_layer_mode(
        ExecutionLayerInputs(
            asset_class="stock",
            use_real_broker=True,
            futures_live_enabled=False,
        )
    )

    assert mode == "real_broker"


def test_futures_contract_validation_gate_is_asset_scoped() -> None:
    assert should_require_futures_contract_validation("futures") is True
    assert should_require_futures_contract_validation("stock") is False
