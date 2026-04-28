"""Runtime mutating risk state for Phase 4 daemons.

Phase 3's :class:`shared.risk.state.RiskStateSnapshot` is a read-only view
constructed for each filter evaluation. The Phase 4 daemons (order_router
fill handler + kill_switch monitor) need higher-level operations:

  * record a closed trade — accumulates daily/weekly PnL and trade count
  * record a loss/win — drives the consecutive-loss counter
  * reset_daily — zeros the daily counters at the 09:00 KST session start
  * should_reset_daily — calendar-day boundary check

This wraps the existing Phase 3 :class:`RiskState` Redis HASH writer and
adds a sibling ``risk:state:{asset_class}:meta`` HASH for daily-reset
bookkeeping (``last_reset_date_kst``).

Each operation does load → mutate → save. Multi-writer atomicity isn't
guaranteed, but in Phase 4 only one daemon (order_router) writes — risk_filter
only reads via :class:`RiskStateSnapshot`. WATCH/Lua isn't required.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.risk.state import RiskState, RiskStateSnapshot

_META_TTL_SECONDS = 86400 * 7  # 7-day rolling window covers KR holidays.


class RuntimeRiskState:
    def __init__(self, *, redis: Any, asset_class: str = "futures") -> None:
        self._redis = redis
        self._asset_class = asset_class
        self._risk_state = RiskState(redis, asset_class)
        self._meta_key = f"risk:state:{asset_class}:meta"

    async def snapshot(self) -> RiskStateSnapshot:
        return await self._risk_state.load()

    async def record_trade(self, *, pnl_krw: float) -> None:
        snap = await self._risk_state.load()
        snap.daily_pnl_krw += pnl_krw
        snap.weekly_pnl_krw += pnl_krw
        snap.daily_trade_count += 1
        await self._risk_state.save(snap)

    async def record_loss(self) -> None:
        snap = await self._risk_state.load()
        snap.consecutive_losses += 1
        await self._risk_state.save(snap)

    async def record_win(self) -> None:
        snap = await self._risk_state.load()
        snap.consecutive_losses = 0
        await self._risk_state.save(snap)

    async def reset_daily(self, *, now_kst: datetime) -> None:
        snap = await self._risk_state.load()
        snap.daily_pnl_krw = 0.0
        snap.daily_trade_count = 0
        await self._risk_state.save(snap)
        await self._redis.hset(
            self._meta_key, "last_reset_date_kst", now_kst.date().isoformat()
        )
        await self._redis.expire(self._meta_key, _META_TTL_SECONDS)

    async def should_reset_daily(self, *, now_kst: datetime) -> bool:
        last = await self._redis.hget(self._meta_key, "last_reset_date_kst")
        if last is None:
            return True
        if isinstance(last, (bytes, bytearray)):
            last = last.decode()
        return last != now_kst.date().isoformat()
