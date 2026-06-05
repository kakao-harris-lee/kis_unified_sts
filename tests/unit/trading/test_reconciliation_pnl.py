"""Regression tests for paper-trading reconciliation and stop persistence."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_position(
    code="005930",
    name="삼성전자",
    side=PositionSide.LONG,
    quantity=100,
    entry_price=70000.0,
    strategy="bb_reversion",
) -> Position:
    return Position(
        id=f"test_{code}",
        code=code,
        name=name,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        current_price=entry_price,
        strategy=strategy,
    )


def _make_broker_position(
    code="005930",
    name="삼성전자",
    side="long",
    quantity=100,
    avg_price=70000.0,
) -> dict:
    return {
        "code": code,
        "name": name,
        "side": side,
        "quantity": quantity,
        "avg_price": avg_price,
        "current_price": avg_price,
        "unrealized_pnl": 0.0,
    }


class TestPaperModeBrokerNotAuthoritative:
    """In PAPER mode the broker mock account must not destroy paper positions."""

    def _orch(self, paper_trading: bool):
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        orch = MagicMock()
        orch.config = MagicMock()
        orch.config.asset_class = "stock"
        orch.config.paper_trading = paper_trading
        orch.config.symbols = []
        orch._position_tracker = tracker
        orch._kis_client = MagicMock()
        orch._kis_client.config = MagicMock()
        orch._kis_client.config.is_real = False
        orch._notify = AsyncMock()
        return orch, tracker

    def _bv_config(self):
        return {
            "broker_verification": {
                "enabled": True,
                "auto_track_external": True,
                "remove_redis_only": True,
                "reconcile_quantity": True,
                "reconcile_price": True,
                "sync_runtime_ledger": False,
                "notify_on_mismatch": False,
            }
        }

    def test_paper_does_not_remove_redis_only(self):
        """Paper position absent from mock account must be kept."""
        from services.trading.orchestrator import TradingOrchestrator

        orch, tracker = self._orch(paper_trading=True)
        tracker.add_recovered_position(_make_position(code="005930"))
        orch._kis_client.get_stock_balance = AsyncMock(return_value=[])

        with patch(
            "services.trading.orchestrator.ConfigLoader.load",
            return_value=self._bv_config(),
        ):
            _run(TradingOrchestrator._verify_positions_with_broker(orch))

        assert len(tracker.get_positions_by_symbol("005930")) == 1

    def test_paper_does_not_auto_track_broker_only(self):
        """Stray mock-account holdings must not be ingested as paper positions."""
        from services.trading.orchestrator import TradingOrchestrator

        orch, tracker = self._orch(paper_trading=True)
        orch._kis_client.get_stock_balance = AsyncMock(
            return_value=[
                _make_broker_position(
                    code="035420", name="NAVER", quantity=30, avg_price=250000.0
                )
            ]
        )

        with patch(
            "services.trading.orchestrator.ConfigLoader.load",
            return_value=self._bv_config(),
        ):
            _run(TradingOrchestrator._verify_positions_with_broker(orch))

        assert tracker.get_positions_by_symbol("035420") == []
        assert tracker.position_count == 0

    def test_live_still_removes_redis_only(self):
        """LIVE mode keeps broker-authoritative behavior."""
        from services.trading.orchestrator import TradingOrchestrator

        orch, tracker = self._orch(paper_trading=False)
        orch._kis_client.config.is_real = True
        tracker.add_recovered_position(_make_position(code="005930"))
        tracker.reconcile_open_positions_to_db = AsyncMock(
            return_value={"open_saved": 0, "closed_orphans": 1}
        )
        orch._kis_client.get_stock_balance = AsyncMock(return_value=[])

        with patch(
            "services.trading.orchestrator.ConfigLoader.load",
            return_value=self._bv_config(),
        ):
            _run(TradingOrchestrator._verify_positions_with_broker(orch))

        assert tracker.get_positions_by_symbol("005930") == []

    def test_live_still_auto_tracks_broker_only(self):
        """LIVE mode still auto-tracks genuine broker-only positions."""
        from services.trading.orchestrator import TradingOrchestrator

        orch, tracker = self._orch(paper_trading=False)
        orch._kis_client.config.is_real = True
        orch._kis_client.get_stock_balance = AsyncMock(
            return_value=[
                _make_broker_position(
                    code="035420", name="NAVER", quantity=30, avg_price=250000.0
                )
            ]
        )

        with patch(
            "services.trading.orchestrator.ConfigLoader.load",
            return_value=self._bv_config(),
        ):
            _run(TradingOrchestrator._verify_positions_with_broker(orch))

        tracked = tracker.get_positions_by_symbol("035420")
        assert len(tracked) == 1
        assert tracked[0].strategy == "external"


class TestStopPricePersistedOnEntry:
    """``add_position`` must persist an initial stop when supplied."""

    def test_stop_price_set_from_arg(self):
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        pos = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=70000.0,
            quantity=10,
            strategy="bb_reversion",
            stop_price=68000.0,
        )
        assert pos is not None
        assert pos.stop_price == pytest.approx(68000.0)

    def test_stop_price_defaults_to_zero_when_not_supplied(self):
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        pos = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=70000.0,
            quantity=10,
            strategy="bb_reversion",
        )
        assert pos is not None
        assert pos.stop_price == 0.0

    def test_add_from_signal_forwards_stop_loss_metadata(self):
        from shared.models.signal import Signal, SignalType

        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        signal = Signal(
            code="005930",
            name="삼성전자",
            signal_type=SignalType.ENTRY,
            price=70000.0,
            strategy="bb_reversion",
            confidence=0.8,
            metadata={"stop_loss": 68000.0},
        )
        pos = tracker.add_from_signal(signal, quantity=10)
        assert pos is not None
        assert pos.stop_price == pytest.approx(68000.0)
