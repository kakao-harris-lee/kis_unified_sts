"""Runtime-storage acceptance tests for Redis + SQLite paper paths."""

from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.execution.fill_logger import FillLogger
from shared.models.position import Position, PositionSide, PositionState
from shared.storage.runtime_ledger import SQLiteRuntimeLedger


def _tracker_config(asset_class: str, db_path) -> PositionTrackerConfig:
    return PositionTrackerConfig(
        asset_class=asset_class,
        runtime_ledger_backend="sqlite",
        runtime_ledger_sqlite_path=str(db_path),
        flush_interval_seconds=0,
    )


def _closed_position(
    *,
    asset_class: str,
    code: str,
    name: str,
    side: PositionSide,
    entry_price: float,
    exit_price: float,
) -> Position:
    entry_time = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    position = Position(
        id=f"{asset_class}-closed-001",
        code=code,
        name=name,
        side=side,
        quantity=2,
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=exit_price,
        highest_price=max(entry_price, exit_price),
        lowest_price=min(entry_price, exit_price),
        state=PositionState.MAXIMIZE,
        strategy=f"{asset_class}_paper_smoke",
        fee_rate=0.0015,
        metadata={"commission": 12.5, "slippage": 1.0},
        execution_venue="KRX",
    )
    position.exit_price = exit_price
    position.exit_time = entry_time + timedelta(minutes=15)
    position.exit_reason = "paper_smoke_exit"
    return position


@pytest.mark.parametrize(
    (
        "asset_class",
        "code",
        "name",
        "side",
        "entry_price",
        "exit_price",
    ),
    [
        ("stock", "005930", "Samsung", PositionSide.LONG, 71000.0, 72000.0),
        ("futures", "101V6000", "KOSPI200 Mini", PositionSide.SHORT, 331.2, 330.0),
    ],
)
@pytest.mark.asyncio
async def test_paper_flow_uses_redis_and_sqlite_only(
    tmp_path,
    asset_class,
    code,
    name,
    side,
    entry_price,
    exit_price,
):
    db_path = tmp_path / f"{asset_class}-runtime.db"
    config = _tracker_config(asset_class, db_path)
    tracker = PositionTracker(
        config=config,
        uuid_generator=lambda: f"{asset_class}-open-001",
    )
    recovered = None
    redis = fakeredis.aioredis.FakeRedis(db=1)

    try:
        client_order_id = f"{asset_class}-signal-001"
        open_position = tracker.add_position(
            code=code,
            name=name,
            entry_price=entry_price,
            quantity=2,
            strategy=f"{asset_class}_paper_smoke",
            side=side,
            client_order_id=client_order_id,
        )
        assert open_position is not None
        assert await tracker.save_to_db() == 1

        ledger = tracker._get_runtime_ledger()
        assert isinstance(ledger, SQLiteRuntimeLedger)

        fill_logger = FillLogger(
            redis=redis,
            ch_client=None,
            runtime_ledger=ledger,
            asset_class=asset_class,
            maxlen=1000,
        )
        await fill_logger.log_fill(
            signal_id=client_order_id,
            order_id=f"{asset_class}-order-001",
            symbol=code,
            side=side.value,
            order_type="paper_market",
            requested_price=entry_price,
            filled_price=entry_price,
            tick_size_points=0.01,
            slippage_ticks=0.0,
            quantity=2,
            requested_at_ms=1_780_530_000_000,
            filled_at_ms=1_780_530_000_125,
            venue="KRX",
            trade_role="entry",
        )

        fills = ledger.query_fills({"asset_class": asset_class, "code": code})
        assert len(fills) == 1
        assert fills[0]["order_id"] == f"{asset_class}-order-001"
        assert await redis.xlen("stream:order.fill") == 1

        closed_position = _closed_position(
            asset_class=asset_class,
            code=code,
            name=name,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
        )
        if asset_class == "stock":
            assert await tracker.save_stock_trade_to_db(closed_position) is True
        else:
            assert (
                await tracker.save_futures_trade_to_db(closed_position, asset_class)
                is True
            )

        trades = ledger.query_trades({"asset_class": asset_class, "code": code})
        assert len(trades) == 1
        assert trades[0]["side"] == side.value
        assert trades[0]["pnl"] > 0

        await tracker.flush_pending_positions()
        ledger.close()

        recovered = PositionTracker(config=config)
        loaded = await recovered.load_from_db()
        recovered_position = recovered.get_position(open_position.id)

        assert loaded == 1
        assert recovered_position is not None
        assert recovered_position.code == code
        assert recovered_position.side == side
        assert recovered_position.metadata["client_order_id"] == client_order_id
    finally:
        await redis.aclose()
        if tracker._runtime_ledger is not None:
            tracker._runtime_ledger.close()
        if recovered is not None and recovered._runtime_ledger is not None:
            recovered._runtime_ledger.close()
