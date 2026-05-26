"""Strategy Lab dashboard route tests."""

import pytest

from shared.strategy_lab.store import StrategyLabStore, reset_memory_store

pytest.importorskip("anyio.to_thread")

from fastapi import HTTPException  # noqa: E402


def _spec_payload() -> dict:
    return {
        "name": "Visual test draft",
        "asset_class": "stock",
        "entry": {
            "operator": "all",
            "conditions": [
                {
                    "left": {"kind": "indicator", "name": "rsi"},
                    "operator": "lte",
                    "right": {"kind": "literal", "value": 30},
                }
            ],
        },
        "exit": {
            "operator": "all",
            "conditions": [
                {
                    "left": {"kind": "indicator", "name": "rsi"},
                    "operator": "gte",
                    "right": {"kind": "literal", "value": 70},
                }
            ],
        },
        "risk": {"order_amount": 1_000_000},
    }


@pytest.mark.asyncio
async def test_strategy_lab_preview_ticket_and_paper_order(monkeypatch):
    from services.dashboard.routes import strategy_lab

    reset_memory_store()
    store = StrategyLabStore(use_redis=False)
    monkeypatch.setattr(strategy_lab, "_store", lambda: store)

    capabilities = await strategy_lab.get_capabilities()
    assert "rsi" in capabilities["capabilities"]["indicators"]

    response = await strategy_lab.preview_signal(
        strategy_lab.PreviewSignalRequest.model_validate(
            {
                "spec": _spec_payload(),
                "symbols": ["005930"],
                "market_data": {
                    "005930": {
                        "symbol": "005930",
                        "price": 70_000,
                        "indicators": {"rsi": 25},
                    }
                },
            }
        )
    )
    signal = response.signals[0]
    assert signal.side == "BUY"
    assert signal.orderability == "paper_orderable"

    ticket = await strategy_lab.create_order_ticket(
        signal.signal_id,
        strategy_lab.OrderTicketCreateRequest(order_amount=1_000_000),
    )
    assert ticket.status == "ready"
    assert ticket.quantity == 14

    order = await strategy_lab.submit_paper_order(
        strategy_lab.PaperOrderSubmitRequest(ticket_id=ticket.ticket_id)
    )
    assert order.status == "filled"
    assert order.fill_id is not None and order.fill_id.startswith("fill_")


@pytest.mark.asyncio
async def test_strategy_lab_requires_market_data(monkeypatch):
    from services.dashboard.routes import strategy_lab

    reset_memory_store()
    store = StrategyLabStore(use_redis=False)
    monkeypatch.setattr(strategy_lab, "_store", lambda: store)

    with pytest.raises(HTTPException) as exc:
        await strategy_lab.preview_signal(
            strategy_lab.PreviewSignalRequest.model_validate(
                {
                    "spec": _spec_payload(),
                    "symbols": ["005930"],
                    "market_data": {},
                }
            )
        )

    assert exc.value.status_code == 400
    assert "market_data missing" in exc.value.detail
