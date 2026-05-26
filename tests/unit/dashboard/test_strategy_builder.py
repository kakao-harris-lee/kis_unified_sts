"""Strategy Builder dashboard route tests."""

import pytest

from shared.strategy_builder.schema import (
    BuilderCondition,
    BuilderConditionGroup,
    BuilderIndicator,
    BuilderMetadata,
    BuilderState,
    ConditionOperand,
    ConditionOperator,
    OperandType,
    SymbolSeries,
)
from shared.strategy_builder.store import StrategyBuilderStore, reset_memory_store
from shared.strategy_lab.store import StrategyLabStore
from shared.strategy_lab.store import reset_memory_store as reset_lab_store


def _state() -> BuilderState:
    return BuilderState(
        metadata=BuilderMetadata(id="builder_route_test", name="Builder Route Test"),
        indicators=[
            BuilderIndicator(indicator_id="sma", alias="sma_fast", params={"period": 5}),
            BuilderIndicator(indicator_id="sma", alias="sma_slow", params={"period": 20}),
        ],
        entry=BuilderConditionGroup(
            conditions=[
                BuilderCondition(
                    left=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_fast",
                    ),
                    operator=ConditionOperator.CROSS_ABOVE,
                    right=ConditionOperand(
                        type=OperandType.INDICATOR,
                        indicator_alias="sma_slow",
                    ),
                )
            ]
        ),
        exit=BuilderConditionGroup(conditions=[]),
    )


@pytest.mark.asyncio
async def test_strategy_builder_preview_signal_and_order(monkeypatch):
    from services.dashboard.routes import strategy_builder

    reset_memory_store()
    reset_lab_store()
    builder_store = StrategyBuilderStore(use_redis=False)
    lab_store = StrategyLabStore(use_redis=False)
    monkeypatch.setattr(strategy_builder, "_store", lambda: builder_store)
    monkeypatch.setattr(strategy_builder, "_lab_store", lambda: lab_store)

    capabilities = await strategy_builder.get_capabilities()
    assert "sma" in {indicator.id for indicator in capabilities.indicators}

    response = await strategy_builder.preview_signals(
        strategy_builder.PreviewSignalRequest(
            state=_state(),
            series=[
                SymbolSeries(
                    symbol="005930",
                    fields={"close": [69000, 71000]},
                    indicators={
                        "sma_fast.value": [99.0, 101.0],
                        "sma_slow.value": [100.0, 100.0],
                    },
                )
            ],
        )
    )

    signal = response.signals[0]
    assert signal.side == "BUY"

    ticket = await strategy_builder.create_order_ticket(
        signal.signal_id,
        strategy_builder.OrderTicketCreateRequest(order_amount=1_000_000),
    )
    assert ticket["status"] == "ready"

    order = await strategy_builder.submit_paper_order(
        strategy_builder.PaperOrderSubmitRequest(ticket_id=ticket["ticket_id"])
    )
    assert order["status"] == "filled"
