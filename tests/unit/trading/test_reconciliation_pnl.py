"""Regression tests for paper-trading position-reconciliation P&L loss.

Root cause being guarded against:

1. ``reconcile_open_positions_to_db`` closed ClickHouse orphan rows at
   ``exit_price = entry_price`` → ``pnl = 0`` (break-even), silently
   discarding real P&L for positions that had moved far from entry. The
   ``high_since_entry`` column carries the best last-known price and must be
   used as the close price instead of ``entry_price``.

2. In PAPER mode the KIS (mock) account balance is NOT the source of truth
   for the VirtualBroker paper positions. ``remove_redis_only`` and
   ``auto_track_external`` must therefore be disabled for paper trackers so a
   mock-mirror miss does not destroy a real paper position (break-even churn)
   nor ingest stray broker holdings as ``external`` paper positions.

3. ``add_position`` must persist an initial ``stop_price`` when one is supplied
   so reconciliation/exports do not record ``stop_loss_price = 0``.
"""

import asyncio
from datetime import datetime
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


class TestReconcileClosesAtLastKnownPrice:
    """``reconcile_open_positions_to_db`` must not zero out P&L on orphan close."""

    def _patch_db(self, tracker, open_rows):
        """Wire a fake ClickHouse sync client returning ``open_rows`` and
        capturing the INSERTed close rows."""
        captured = {"close_rows": None, "open_rows": None}

        sync_client = MagicMock()
        sync_client.execute.return_value = open_rows

        def _execute(sql, params=None):
            if "INSERT" in sql and params is not None:
                # Distinguish close vs open inserts by is_open flag (col idx 11)
                if params and params[0][11] == 0:
                    captured["close_rows"] = params
                else:
                    captured["open_rows"] = params
                return None
            return open_rows

        sync_client.execute.side_effect = _execute

        ch = MagicMock()
        ch.get_sync_client.return_value = sync_client
        tracker._get_db_client = MagicMock(return_value=(ch, "market"))
        return captured

    def test_orphan_long_closed_at_high_not_entry(self):
        """A LONG orphan that rallied is closed at high_since_entry, pnl > 0."""
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))

        entry = 7262.16
        high = 12000.0
        qty = 100
        # DB open row absent from the live tracker → treated as orphan.
        open_rows = [
            (
                "orphan_001740",  # id
                "001740",  # code
                "테스트",  # name
                datetime(2026, 5, 20),  # entry_date
                entry,  # entry_price
                qty,  # quantity
                "external",  # strategy
                "KRX",  # execution_venue
                0.0,  # stop_loss_price
                high,  # high_since_entry
                "survival",  # current_state
                "long",  # side
                0.003,  # fee_rate
            )
        ]
        captured = self._patch_db(tracker, open_rows)

        result = _run(tracker.reconcile_open_positions_to_db())

        assert result["closed_orphans"] == 1
        close_row = captured["close_rows"][0]
        # _SWING_INSERT_COLS: ... is_open(11), exit_date(12), exit_price(13),
        # exit_reason(14), pnl(15) ...
        exit_price = close_row[13]
        pnl = close_row[15]
        assert exit_price == pytest.approx(
            high
        ), "orphan must close at last-known high, not entry"
        assert exit_price != pytest.approx(entry)
        assert pnl == pytest.approx(
            (high - entry) * qty
        ), "pnl must reflect real price movement, not be zeroed"
        assert pnl > 0

    def test_orphan_short_pnl_sign(self):
        """A SHORT orphan: pnl = (entry - exit) * qty."""
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        entry = 100.0
        last = 90.0  # short profited as price fell; high_since_entry tracks extreme
        qty = 2
        open_rows = [
            (
                "orphan_short",
                "A05001",
                "미니선물",
                datetime(2026, 5, 20),
                entry,
                qty,
                "external",
                "KRX",
                0.0,
                last,  # high_since_entry used as last-known price proxy
                "survival",
                "short",
                0.0,
            )
        ]
        captured = self._patch_db(tracker, open_rows)

        _run(tracker.reconcile_open_positions_to_db())

        close_row = captured["close_rows"][0]
        exit_price = close_row[13]
        pnl = close_row[15]
        assert exit_price == pytest.approx(last)
        assert pnl == pytest.approx((entry - last) * qty)

    def test_orphan_missing_high_falls_back_to_entry(self):
        """When high_since_entry is unusable, fall back to entry (pnl 0) safely."""
        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        entry = 5000.0
        qty = 10
        open_rows = [
            (
                "orphan_nohigh",
                "000001",
                "x",
                datetime(2026, 5, 20),
                entry,
                qty,
                "external",
                "KRX",
                0.0,
                0.0,  # high_since_entry unusable
                "survival",
                "long",
                0.0,
            )
        ]
        captured = self._patch_db(tracker, open_rows)
        _run(tracker.reconcile_open_positions_to_db())
        close_row = captured["close_rows"][0]
        assert close_row[13] == pytest.approx(entry)
        assert close_row[15] == pytest.approx(0.0)


class TestPaperModeBrokerNotAuthoritative:
    """In PAPER mode the broker (mock) account must not destroy paper positions."""

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
                "sync_clickhouse": False,
                "notify_on_mismatch": False,
            }
        }

    def test_paper_does_not_remove_redis_only(self):
        """Paper position absent from mock account must be KEPT (not removed)."""
        from services.trading.orchestrator import TradingOrchestrator

        orch, tracker = self._orch(paper_trading=True)
        tracker.add_recovered_position(_make_position(code="005930"))
        orch._kis_client.get_stock_balance = AsyncMock(return_value=[])

        with patch(
            "services.trading.orchestrator.ConfigLoader.load",
            return_value=self._bv_config(),
        ):
            _run(TradingOrchestrator._verify_positions_with_broker(orch))

        # Paper position must survive a mock-mirror miss.
        assert len(tracker.get_positions_by_symbol("005930")) == 1

    def test_paper_does_not_auto_track_broker_only(self):
        """Stray mock-account holdings must NOT be ingested as paper positions."""
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
        """LIVE mode keeps broker-authoritative behavior (regression guard)."""
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
        """Backward-compatible: omitting stop_price keeps prior behavior."""
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
        """A signal carrying metadata['stop_loss'] sets the position stop_price."""
        from shared.models.signal import Signal, SignalType

        tracker = PositionTracker(PositionTrackerConfig(max_positions=20))
        signal = Signal(
            code="005930",
            name="삼성전자",
            signal_type=SignalType.ENTRY,
            price=70000.0,
            strategy="bb_reversion",
            metadata={"stop_loss": 68000.0},
        )
        pos = tracker.add_from_signal(signal, quantity=10)
        assert pos is not None
        assert pos.stop_price == pytest.approx(68000.0)
