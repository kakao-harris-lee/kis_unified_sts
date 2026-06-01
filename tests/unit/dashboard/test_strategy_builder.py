"""Strategy Builder dashboard route tests."""

import pytest
from fastapi.testclient import TestClient

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


def test_dashboard_registers_kis_builder_compat_routes():
    from services.dashboard.app import create_app

    client = TestClient(create_app(require_auth=False))

    listed = client.get("/api/kis-builder/strategies", headers={"accept": "application/json"})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 27

    executed = client.post(
        "/api/kis-builder/strategies/execute",
        json={
            "strategy_id": "golden_cross",
            "stocks": ["005930"],
            "params": {"short_period": 7, "long_period": 35},
        },
    )
    assert executed.status_code == 200
    assert executed.json()["results"][0]["action"] == "BUY"


@pytest.mark.asyncio
async def test_register_paper_accepts_camelcase_state(tmp_path, monkeypatch) -> None:
    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)

    camel = {
        "metadata": {
            "id": "camel_reg_test",
            "name": "Camel Reg",
            "description": "",
            "category": "custom",
            "tags": ["t"],
            "author": "u",
        },
        "assetClass": "stock",
        "indicators": [
            {"id": "i1", "indicatorId": "rsi", "alias": "rsi", "params": {}, "output": "value"}
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "id": "c1",
                    "left": {"type": "indicator", "indicatorAlias": "rsi", "indicatorOutput": "value"},
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "stopLoss": {"enabled": True, "percent": 5.0},
            "takeProfit": {"enabled": False, "percent": 10.0},
            "trailingStop": {"enabled": False, "percent": 3.0},
        },
    }

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(builder_state=camel)
    )
    assert result.asset_class == "stock"
    assert (tmp_path / "camel_reg_test.yaml").exists()
