"""F-3 e2e: PassiveMaker over PaperKISFuturesAdapter — fills/misses, no real orders."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter
from shared.execution.passive_maker import PassiveMaker


class _FakeFeed:
    def __init__(self, snapshot: dict, price: dict) -> None:
        self._snap = snapshot
        self._price = price

    async def get_current_price(self, _symbol: str) -> dict:
        return dict(self._price)

    def get_orderbook_snapshot(self, _symbol: str) -> dict:
        return dict(self._snap)


def _spec() -> ContractSpec:
    return ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50_000,
        tick_size_points=0.02,
        tick_value_krw=1_000,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 6, 8, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 6, 8, 5, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_paper_passive_entry_fills_at_bid_and_logs() -> None:
    # long: limit posted at best_bid 331.20; last trade 331.18 (<= bid) -> fills
    feed = _FakeFeed({"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.18})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    fill_logger = MagicMock()
    fill_logger.log_fill = AsyncMock()
    pm = PassiveMaker(kis_client=adapter, fill_logger=fill_logger)

    result = await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="s1",
        quantity=1,
        spec=_spec(),
        timeout_seconds=1,
    )

    assert result.is_filled
    assert result.filled_price == 331.20  # passive fill at posted bid
    fill_logger.log_fill.assert_awaited_once()
    # paper: the order id is synthetic (no real KIS order was ever placed)
    assert result.order_id.startswith("PAPER-")


@pytest.mark.asyncio
async def test_paper_passive_entry_misses_when_market_away() -> None:
    # long: limit 331.20; market stays above (trade 331.30, ask 331.22) -> miss
    feed = _FakeFeed({"bid_price_1": 331.20, "ask_price_1": 331.22}, {"close": 331.30})
    adapter = PaperKISFuturesAdapter(futures_price_feed=feed, poll_interval=0.01)
    fill_logger = MagicMock()
    fill_logger.log_fill = AsyncMock()
    pm = PassiveMaker(kis_client=adapter, fill_logger=fill_logger)

    result = await pm.place_passive_limit_futures(
        signal=_signal("long"),
        signal_id="s2",
        quantity=1,
        spec=_spec(),
        timeout_seconds=0.05,
    )

    assert not result.is_filled
    fill_logger.log_fill.assert_not_awaited()  # no fill logged on a miss
