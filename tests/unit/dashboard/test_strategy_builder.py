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


def _futures_register_state(strategy_id: str = "fut_reg_test") -> dict:
    return {
        "metadata": {
            "id": strategy_id,
            "name": "Fut Reg",
            "description": "",
            "category": "custom",
            "tags": ["t"],
            "author": "u",
        },
        "asset_class": "futures",
        "indicators": [
            {"indicator_id": "rsi", "alias": "rsi", "params": {}, "output": "value"}
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {"type": "indicator", "indicator_alias": "rsi", "indicator_output": "value"},
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {"stop_loss": {"enabled": True, "percent": 5.0}},
    }


@pytest.mark.asyncio
async def test_register_paper_accepts_futures_and_uses_contract_sizing(tmp_path, monkeypatch):
    import yaml as _yaml

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(
            builder_state=_futures_register_state(), contracts=2
        )
    )
    assert result.asset_class == "futures"

    doc = _yaml.safe_load((tmp_path / "fut_reg_test.yaml").read_text(encoding="utf-8"))
    position = doc["strategy"]["position"]
    assert position["type"] == "fixed"
    assert position["params"]["fixed_quantity"] == 2
    assert "order_amount_per_stock" not in position["params"]


@pytest.mark.asyncio
async def test_register_paper_rejects_unknown_asset_class(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)
    bad = _futures_register_state("bad_asset")
    bad["asset_class"] = "options"

    with pytest.raises(HTTPException) as exc:
        await kis_builder.register_paper_strategy(
            kis_builder.RegisterPaperRequest(builder_state=bad)
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_register_paper_stock_still_uses_krw_sizing(tmp_path, monkeypatch):
    import yaml as _yaml

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)
    stock = _futures_register_state("stock_reg_test")
    stock["asset_class"] = "stock"

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(builder_state=stock, order_amount=2_000_000)
    )
    assert result.asset_class == "stock"
    doc = _yaml.safe_load((tmp_path / "stock_reg_test.yaml").read_text(encoding="utf-8"))
    position = doc["strategy"]["position"]
    assert position["params"]["order_amount_per_stock"] == 2_000_000
    assert "fixed_quantity" not in position["params"]


@pytest.mark.asyncio
async def test_register_paper_futures_defaults_to_one_contract(tmp_path, monkeypatch):
    # Omitting `contracts` must materialize 1 contract (the safe Phase-1 default),
    # not fall through to amount-based sizing (fixed_quantity must be 1, not 0).
    import yaml as _yaml

    from services.dashboard.routes import kis_builder

    monkeypatch.setattr(kis_builder, "_BUILT_STRATEGIES_DIR", tmp_path)

    result = await kis_builder.register_paper_strategy(
        kis_builder.RegisterPaperRequest(
            builder_state=_futures_register_state("fut_default_contracts")
        )
    )
    assert result.asset_class == "futures"
    doc = _yaml.safe_load(
        (tmp_path / "fut_default_contracts.yaml").read_text(encoding="utf-8")
    )
    assert doc["strategy"]["position"]["params"]["fixed_quantity"] == 1


def test_capabilities_expose_tier1_indicators() -> None:
    """The Tier1 catalog expansion must surface the newly-exposed indicators."""
    from shared.strategy_builder.catalog import load_capabilities

    catalog = load_capabilities()
    by_id = {indicator.id: indicator for indicator in catalog.indicators}

    # Original 10 stay present (no regression).
    for base in (
        "sma",
        "ema",
        "rsi",
        "macd",
        "bollinger",
        "stochastic",
        "atr",
        "adx",
        "volume_ma",
        "vwap",
    ):
        assert base in by_id, f"base indicator {base} disappeared"

    # Tier1 additions are exposed.
    for new_id in (
        "williams_r",
        "cci",
        "trix",
        "obv",
        "mfi",
        "rvol",
        "volume_acceleration",
        "ichimoku",
    ):
        assert new_id in by_id, f"tier1 indicator {new_id} missing from catalog"


def test_capabilities_tier1_flags_are_honest() -> None:
    """Flags must match what the runtime/backtest engine actually produces.

    Engine-produced indicators (base flat path + momentum_5m bundle) are
    runtime/backtest true; ``ichimoku`` has a calculator but no engine wiring,
    so it must stay implemented-only.
    """
    from shared.strategy_builder.catalog import load_capabilities

    by_id = {i.id: i for i in load_capabilities().indicators}

    # Produced at runtime (momentum_5m bundle) AND backtest -> both true.
    for produced in ("williams_r", "cci", "trix", "obv"):
        ind = by_id[produced]
        assert ind.implemented is True
        assert ind.runtime_supported is True, f"{produced} should be runtime true"
        assert ind.backtest_supported is True, f"{produced} should be backtest true"

    # Produced as flat keys by the base indicator path -> both true.
    for produced in ("mfi", "rvol", "volume_acceleration"):
        ind = by_id[produced]
        assert ind.implemented is True
        assert ind.runtime_supported is True, f"{produced} should be runtime true"
        assert ind.backtest_supported is True, f"{produced} should be backtest true"

    # Calculator exists but is NOT wired into the streaming/backtest engine.
    ichimoku = by_id["ichimoku"]
    assert ichimoku.implemented is True
    assert ichimoku.runtime_supported is False, "ichimoku is not engine-produced"
    assert ichimoku.backtest_supported is False, "ichimoku is not engine-produced"

    # trix exposes both the oscillator value and its signal line.
    assert {o.id for o in by_id["trix"].outputs} == {"value", "signal"}
