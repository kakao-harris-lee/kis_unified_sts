import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.models.position import Position, PositionSide


def _config(asset_class: str = "stock", paper_trading: bool = False):
    return SimpleNamespace(
        asset_class=asset_class,
        paper_trading=paper_trading,
        symbols=[],
    )


def _position(code: str = "005930", quantity: int = 10) -> Position:
    return Position(
        id=f"pos_{code}",
        code=code,
        name="Samsung",
        side=PositionSide.LONG,
        quantity=quantity,
        entry_price=70_000.0,
        current_price=70_000.0,
        strategy="bb_reversion",
    )


class FakePositionTracker:
    def __init__(self, positions=None):
        self.positions = list(positions or [])
        self.removed = []
        self.recovered = []
        self.reconcile_open_positions_to_db = AsyncMock()

    def remove_position(self, position_id, reason=None):
        self.removed.append((position_id, reason))
        for index, position in enumerate(self.positions):
            if position.id == position_id:
                return self.positions.pop(index)
        return None

    def add_recovered_position(self, position):
        self.recovered.append(position)
        self.positions.append(position)
        return True


class FakeKisClient:
    def __init__(self, *, stock_positions=None, futures_positions=None, is_real=True):
        self.config = SimpleNamespace(is_real=is_real)
        self.get_stock_balance = AsyncMock(return_value=list(stock_positions or []))
        self.get_futures_balance = AsyncMock(return_value=list(futures_positions or []))


def _broker_verification_config(**overrides):
    config = {
        "enabled": True,
        "reconcile_quantity": True,
        "reconcile_price": True,
        "remove_redis_only": False,
        "sync_runtime_ledger": False,
        "notify_on_mismatch": True,
        "auto_track_external": False,
    }
    config.update(overrides)
    return {"broker_verification": config}


@pytest.fixture
def verifier(monkeypatch):
    from services.trading import broker_verification as broker_verification_module
    from services.trading.broker_verification import BrokerPositionVerifier

    monkeypatch.setattr(
        broker_verification_module.ConfigLoader,
        "load",
        staticmethod(lambda *_args, **_kwargs: _broker_verification_config()),
    )
    return BrokerPositionVerifier()


@pytest.mark.asyncio
async def test_no_positions_on_redis_or_broker_skips_action(verifier, caplog):
    kis_client = FakeKisClient(stock_positions=[])
    position_tracker = FakePositionTracker()
    notify = AsyncMock()

    with caplog.at_level(logging.INFO, logger="services.trading.orchestrator"):
        await verifier.verify(
            config=_config(),
            kis_client=kis_client,
            position_tracker=position_tracker,
            notify=notify,
        )

    kis_client.get_stock_balance.assert_awaited_once()
    assert position_tracker.positions == []
    assert position_tracker.removed == []
    assert position_tracker.recovered == []
    position_tracker.reconcile_open_positions_to_db.assert_not_awaited()
    notify.assert_not_awaited()
    assert "Broker verification: no positions on either side" in caplog.text


@pytest.mark.asyncio
async def test_futures_paper_mode_skips_broker_inquiry(verifier, caplog):
    kis_client = FakeKisClient(futures_positions=[])
    position_tracker = FakePositionTracker()

    with caplog.at_level(logging.INFO, logger="services.trading.orchestrator"):
        await verifier.verify(
            config=_config(asset_class="futures", paper_trading=True),
            kis_client=kis_client,
            position_tracker=position_tracker,
            notify=AsyncMock(),
        )

    kis_client.get_futures_balance.assert_not_awaited()
    assert "Futures paper mode: skipping broker verification" in caplog.text


@pytest.mark.asyncio
async def test_missing_kis_client_skips_verification(verifier, caplog):
    notify = AsyncMock()

    with caplog.at_level(logging.DEBUG, logger="services.trading.orchestrator"):
        await verifier.verify(
            config=_config(),
            kis_client=None,
            position_tracker=FakePositionTracker([_position()]),
            notify=notify,
        )

    notify.assert_not_awaited()
    assert "KIS client not available; skipping broker verification" in caplog.text


@pytest.mark.asyncio
async def test_mismatched_positions_emit_warning_payload(monkeypatch, caplog):
    from services.trading import broker_verification as broker_verification_module
    from services.trading.broker_verification import BrokerPositionVerifier

    monkeypatch.setattr(
        broker_verification_module.ConfigLoader,
        "load",
        staticmethod(
            lambda *_args, **_kwargs: _broker_verification_config(
                reconcile_quantity=False
            )
        ),
    )
    notify = AsyncMock()
    position_tracker = FakePositionTracker([_position(quantity=10)])
    kis_client = FakeKisClient(
        stock_positions=[
            {
                "code": "005930",
                "name": "Samsung",
                "side": "long",
                "quantity": 12,
                "avg_price": 70_000.0,
                "current_price": 70_000.0,
            }
        ]
    )

    await BrokerPositionVerifier().verify(
        config=_config(),
        kis_client=kis_client,
        position_tracker=position_tracker,
        notify=notify,
    )

    assert position_tracker.positions[0].quantity == 10
    notify.assert_awaited_once()
    alert_text = notify.await_args.args[0]
    assert "Broker Position Verification (stock)" in alert_text
    assert "[005930] Quantity mismatch: Redis=10, Broker=12" in alert_text
    assert "[005930] Quantity mismatch: Redis=10, Broker=12" in caplog.text
