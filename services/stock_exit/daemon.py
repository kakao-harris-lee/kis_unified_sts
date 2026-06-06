"""Stock exit daemon (M4-X, timer-loop, shadow-first).

Scans open stock positions from ``trading:stock:positions`` (written by M4-O),
tracks each running high, runs ThreeStageExit, paper-sells exits, closes
positions (HDEL), and feeds realized PnL to RuntimeRiskState — activating M4-R's
PnL-dependent filters. Not a StreamStage (no upstream exit-candidate stream);
a decision-cadence loop like the M4-P StockStrategyDaemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from services.stock_exit.positions import (
    parse_position_record,
    position_from_record,
    record_with_high_water,
)
from shared.paper.models import OrderSide, OrderType

logger = logging.getLogger(__name__)


class StockExitDaemon:
    """Decision-cadence loop that exits open stock positions via ThreeStageExit."""

    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        exit_strategy: Any,
        broker: Any,
        fill_logger: Any,
        runtime_state: Any,
        positions_key: str,
        interval_seconds: float,
        now_fn: Any = lambda: datetime.now(UTC),
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.exit_strategy = exit_strategy
        self.broker = broker
        self.fill_logger = fill_logger
        self.runtime_state = runtime_state
        self.positions_key = positions_key
        self.interval_seconds = interval_seconds
        self.now_fn = now_fn
        self.fee_rate = float(getattr(exit_strategy.config, "fee_rate", 0.003))
        self._stop = asyncio.Event()

    async def run(self) -> None:
        await self.feed.start()
        try:
            while not self._stop.is_set():
                try:
                    await self.run_cycle()
                except Exception:
                    logger.exception("stock exit cycle failed; continuing")
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.interval_seconds
                    )
        finally:
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()

    async def run_cycle(self) -> None:
        raw = await self.redis.hgetall(self.positions_key)
        positions = []
        recs: dict[str, dict[str, Any]] = {}
        for value in raw.values():
            rec = parse_position_record(value)
            if rec is None:
                continue  # skip foreign/orchestrator entries (no opened_at_ms)
            pos = position_from_record(rec, fee_rate=self.fee_rate)
            recs[pos.code] = rec
            positions.append(pos)

        if not positions:
            return

        self.feed.update_symbols([p.code for p in positions])

        market_data: dict[str, dict[str, Any]] = {}
        for pos in positions:
            price = await self.feed.get_current_price(pos.code)
            close = price.get("close")
            if close is None:
                continue
            pos.update_price(float(close))
            await self.redis.hset(
                self.positions_key,
                pos.code,
                record_with_high_water(recs[pos.code], pos),
            )
            market_data[pos.code] = {"close": float(close)}

        # Only evaluate positions for which we have a live price.
        # Positions with no market data are skipped this cycle rather than
        # falling through to ThreeStageExit's entry_price fallback, which
        # would evaluate them at profit_pct=0 and fire TIME_CUT incorrectly.
        priced_positions = [p for p in positions if p.code in market_data]
        signals = await self.exit_strategy.scan_positions(
            priced_positions, market_data, market_state=None
        )
        pos_by_code = {p.code: p for p in positions}
        for sig in signals:
            await self._execute_exit(sig, pos_by_code.get(sig.code))

    async def _execute_exit(self, sig: Any, pos: Any) -> None:
        if pos is None:
            return
        qty = int(sig.quantity) if getattr(sig, "quantity", 0) else pos.quantity
        current = (
            float(sig.current_price) if sig.current_price > 0 else pos.current_price
        )

        order = await self.broker.submit_order(
            symbol=sig.code,
            side=OrderSide.SELL,
            quantity=qty,
            price=current,
            order_type=OrderType.MARKET,
            market_price=current,
        )
        if not order.filled:
            logger.info(
                "stock exit not filled code=%s reason=%s",
                sig.code,
                order.rejection_reason,
            )
            return  # leave position open, retry next cycle

        filled = float(order.fill_price or current)
        gross = (filled - pos.entry_price) * qty
        round_trip_fee = (pos.entry_price + filled) * qty * (pos.fee_rate / 2)
        pnl = gross - round_trip_fee

        # HDEL first (authoritative close — prevents re-sell / double PnL on retry).
        await self.redis.hdel(self.positions_key, sig.code)
        await self.runtime_state.record_trade(pnl_krw=pnl)
        if pnl > 0:
            await self.runtime_state.record_win()
        else:
            await self.runtime_state.record_loss()

        now_ms = int(self.now_fn().timestamp() * 1000)
        reason = getattr(sig.reason, "value", str(sig.reason))
        try:
            await self.fill_logger.log_fill(
                signal_id=pos.id,
                order_id=order.order_id or "",
                symbol=sig.code,
                side="SELL",
                order_type="market",
                requested_price=current,
                filled_price=filled,
                tick_size_points=0.0,
                slippage_ticks=abs(filled - current),
                quantity=qty,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue="KRX",
                trade_role="exit",
            )
        except Exception:
            logger.warning(
                "exit fill log failed code=%s (position already closed)",
                sig.code,
                exc_info=True,
            )
        logger.info("stock exit code=%s reason=%s pnl=%.0f", sig.code, reason, pnl)
