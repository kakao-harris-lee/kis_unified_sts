"""Tests for scripts/trading/flatten_all.py — Phase 5 Task 4."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

spec = importlib.util.spec_from_file_location(
    "flatten_all",
    _REPO_ROOT / "scripts" / "trading" / "flatten_all.py",
)
_module = importlib.util.module_from_spec(spec)
sys.modules["flatten_all"] = _module
spec.loader.exec_module(_module)

_build_open_positions = _module._build_open_positions
render_dry_run = _module.render_dry_run
render_confirmed_summary = _module.render_confirmed_summary
flatten_all_async = _module.flatten_all_async


def _broker(symbol: str, side: str, qty: int, avg_price: float = 100.0) -> dict:
    return {"code": symbol, "side": side, "quantity": qty, "avg_price": avg_price}


class TestBuildOpenPositions:
    def test_long_buy_to_long(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        assert len(positions) == 1
        assert positions[0].direction == "long"

    def test_short_sell_to_short(self):
        positions = _build_open_positions([_broker("A05603", "SELL", 2)])
        assert len(positions) == 1
        assert positions[0].direction == "short"

    def test_kis_numeric_codes(self):
        positions = _build_open_positions(
            [_broker("A05603", "2", 1), _broker("A05604", "1", 1)]
        )
        sides = [p.direction for p in positions]
        assert "long" in sides
        assert "short" in sides

    def test_zero_qty_skipped(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 0)])
        assert positions == []

    def test_unknown_side_skipped(self):
        positions = _build_open_positions([_broker("A05603", "ambiguous", 1)])
        assert positions == []

    def test_missing_symbol_skipped(self):
        positions = _build_open_positions([{"code": "", "side": "BUY", "quantity": 1}])
        assert positions == []

    def test_unknown_symbol_skipped(self):
        # Symbol with no matching contract spec prefix
        positions = _build_open_positions(
            [{"code": "ZZZ999", "side": "BUY", "quantity": 1}]
        )
        assert positions == []

    def test_avg_price_propagated(self):
        positions = _build_open_positions(
            [_broker("A05603", "BUY", 1, avg_price=331.20)]
        )
        assert positions[0].entry_price == 331.20

    def test_tick_size_resolved_from_spec(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        # kospi200_mini tick_size_points = 0.02
        assert positions[0].tick_size_points == 0.02


class TestDryRun:
    def test_no_positions_message(self):
        msg = render_dry_run([])
        assert "no open positions" in msg

    def test_lists_each_position(self):
        positions = _build_open_positions(
            [_broker("A05603", "BUY", 1, avg_price=331.20)]
        )
        msg = render_dry_run(positions)
        assert "A05603" in msg
        assert "long" in msg
        assert "qty=1" in msg
        assert "Re-run with --confirm" in msg


class TestConfirmedSummary:
    def test_empty_results(self):
        msg = render_confirmed_summary([])
        assert "no positions" in msg

    def test_filled_status_shown(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        result = SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True)
        msg = render_confirmed_summary([(positions[0], result)])
        assert "FILLED" in msg

    def test_failed_status_shown(self):
        positions = _build_open_positions([_broker("A05603", "BUY", 1)])
        msg = render_confirmed_summary([(positions[0], None)])
        assert "FAILED" in msg


class TestFlattenAllAsync:
    @pytest.mark.asyncio
    async def test_calls_close_for_kill_switch_per_position(self):
        broker = [
            _broker("A05603", "BUY", 1, avg_price=331.20),
            _broker("A05604", "SELL", 2, avg_price=329.50),
        ]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            side_effect=[
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
            ]
        )

        results = await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
        )

        assert len(results) == 2
        assert force_close.close_for_kill_switch.await_count == 2

    @pytest.mark.asyncio
    async def test_per_position_failure_does_not_abort_others(self):
        broker = [
            _broker("A05603", "BUY", 1),
            _broker("A05604", "SELL", 2),
        ]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            side_effect=[
                Exception("KIS down"),
                SimpleNamespace(state=SimpleNamespace(value="filled"), is_filled=True),
            ]
        )

        results = await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
        )

        assert len(results) == 2
        assert results[0][1] is None  # failed
        assert results[1][1].is_filled  # succeeded

    @pytest.mark.asyncio
    async def test_empty_broker_positions_yields_no_calls(self):
        force_close = AsyncMock()
        results = await flatten_all_async(
            broker_positions=[],
            force_close_executor=force_close,
            reason="test",
            now_ms=1000,
        )
        assert results == []
        force_close.close_for_kill_switch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reason_propagated_to_close_call(self):
        broker = [_broker("A05603", "BUY", 1)]
        force_close = AsyncMock()
        force_close.close_for_kill_switch = AsyncMock(
            return_value=SimpleNamespace(
                state=SimpleNamespace(value="filled"), is_filled=True
            )
        )

        await flatten_all_async(
            broker_positions=broker,
            force_close_executor=force_close,
            reason="custom_reason",
            now_ms=12345,
        )

        kwargs = force_close.close_for_kill_switch.call_args.kwargs
        assert kwargs["reason"] == "custom_reason"
        assert kwargs["now_ms"] == 12345
