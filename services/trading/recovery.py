"""Position recovery helpers for trading runtime startup."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.exceptions import ConfigurationError, InfrastructureError
from shared.models.position import Position, PositionSide, PositionState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryFreshness:
    """Freshness decision for a recovered open position."""

    recoverable: bool
    is_swing: bool
    age_days: int


class PositionRecoveryService:
    """Own startup recovery of open positions into the runtime tracker."""

    def __init__(
        self,
        *,
        config: Any,
        position_tracker: Any,
        symbol_names: Mapping[str, str] | None,
        symbol_last_seen: dict[str, datetime],
        swing_strategies: Collection[str],
        reader_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.config = config
        self.position_tracker = position_tracker
        self.symbol_names = symbol_names or {}
        self.symbol_last_seen = symbol_last_seen
        self.swing_strategies = swing_strategies
        self.reader_factory = reader_factory

    async def recover_open_positions(
        self,
        *,
        recovery_disabled: bool = False,
    ) -> int:
        """Recover open positions from Redis first, then durable SQLite fallback."""
        if recovery_disabled:
            logger.info(
                "Position recovery disabled by env (STS_DISABLE_POSITION_RECOVERY)"
            )
            return 0

        redis_loaded = await self.recover_positions_from_redis()
        db_loaded = await self.recover_from_runtime_ledger()
        return redis_loaded + db_loaded

    async def recover_from_runtime_ledger(self) -> int:
        """Recover open positions from the runtime ledger through the tracker."""
        if self.position_tracker is None:
            return 0

        try:
            db_loaded = await self.position_tracker.load_from_db()
            if db_loaded:
                logger.info(
                    "Recovered %d open position(s) from runtime ledger "
                    "(durable SQLite fallback)",
                    db_loaded,
                )
            return int(db_loaded or 0)
        except (InfrastructureError, OSError, ConnectionError) as e:
            logger.warning(
                "Durable SQLite position recovery failed (continuing): %s", e
            )
            return 0

    async def recover_positions_from_redis(self) -> int:
        """Recover open positions from Redis on startup."""
        if self.position_tracker is None:
            return 0

        try:
            reader = self._create_reader()
        except (ConfigurationError, InfrastructureError) as e:
            logger.warning(f"Cannot initialize TradingStateReader for recovery: {e}")
            return 0

        positions = reader.get_positions()
        if not positions:
            logger.info("No positions to recover from Redis")
            return 0

        today = datetime.now().date()
        max_age_days = getattr(self.config, "swing_recovery_max_age_days", 7)
        recovered = 0
        stale = 0

        for pos_data in positions:
            pos_id = pos_data.get("id", "")
            strategy = pos_data.get("strategy", "")

            try:
                entry_time = parse_recovery_entry_time(pos_data)
            except (ValueError, TypeError):
                logger.warning(f"Invalid entry_time in Redis position: {pos_id[:8]}")
                reader.remove_position(pos_id)
                stale += 1
                continue

            freshness = evaluate_position_freshness(
                strategy=strategy,
                entry_time=entry_time,
                today=today,
                swing_strategies=self.swing_strategies,
                max_swing_age_days=max_age_days,
            )
            if not freshness.recoverable:
                if freshness.is_swing:
                    logger.debug(
                        f"Stale swing position: {pos_data.get('code')} "
                        f"(age={freshness.age_days}d)"
                    )
                else:
                    logger.debug(
                        f"Stale intraday position: {pos_data.get('code')} "
                        f"(age={freshness.age_days}d)"
                    )
                reader.remove_position(pos_id)
                stale += 1
                continue

            try:
                position = reconstruct_recovered_position(
                    pos_data,
                    entry_time=entry_time,
                    symbol_names=self.symbol_names,
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Failed to reconstruct position {pos_id[:8]}: {e}")
                reader.remove_position(pos_id)
                stale += 1
                continue

            if self.position_tracker.add_recovered_position(position):
                recovered += 1
                self._ensure_symbol_subscription(position.code)

        if stale > 0:
            logger.info(f"Cleaned {stale} stale positions from Redis")
        if recovered > 0:
            logger.info(
                f"Recovered {recovered} positions from Redis "
                f"({self.config.asset_class})"
            )
        return recovered

    def _create_reader(self) -> Any:
        asset_class = self.config.asset_class
        if self.reader_factory is not None:
            return self.reader_factory(asset_class)

        from shared.streaming.trading_state import TradingStateReader

        return TradingStateReader(asset_class)

    def _ensure_symbol_subscription(self, code: str) -> None:
        current_symbols = set(self.config.symbols or [])
        if code in current_symbols:
            return
        if self.config.symbols is None:
            self.config.symbols = []
        self.config.symbols.append(code)
        self.symbol_last_seen[code] = datetime.now()


def parse_recovery_entry_time(pos_data: Mapping[str, Any]) -> datetime:
    """Parse the persisted entry timestamp for a recoverable position."""
    entry_time_str = pos_data.get("entry_time", "")
    if not isinstance(entry_time_str, str) or not entry_time_str:
        raise ValueError("missing entry_time")
    try:
        return datetime.fromisoformat(entry_time_str)
    except ValueError as exc:
        raise ValueError("invalid entry_time") from exc


def evaluate_position_freshness(
    *,
    strategy: str,
    entry_time: datetime,
    today: date,
    swing_strategies: Collection[str],
    max_swing_age_days: int,
) -> RecoveryFreshness:
    """Evaluate Redis position freshness using swing/intraday recovery policy."""
    age_days = (today - entry_time.date()).days
    is_swing = strategy in swing_strategies
    if is_swing:
        recoverable = age_days <= max_swing_age_days
    else:
        recoverable = entry_time.date() == today
    return RecoveryFreshness(
        recoverable=recoverable,
        is_swing=is_swing,
        age_days=age_days,
    )


def reconstruct_recovered_position(
    pos_data: Mapping[str, Any],
    *,
    entry_time: datetime,
    symbol_names: Mapping[str, str],
) -> Position:
    """Reconstruct a Position from persisted recovery data."""
    side = PositionSide(pos_data.get("side", "long"))
    entry_price = float(pos_data["entry_price"])
    current_price = float(pos_data.get("current_price", entry_price))

    pos_code = str(pos_data["code"])
    position = Position(
        id=str(pos_data.get("id", "")),
        code=pos_code,
        name=str(pos_data.get("name", "") or symbol_names.get(pos_code, pos_code)),
        side=side,
        quantity=int(pos_data["quantity"]),
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
        highest_price=float(
            pos_data.get("highest_price", max(entry_price, current_price))
        ),
        lowest_price=float(
            pos_data.get("lowest_price", min(entry_price, current_price))
        ),
        state=_position_state_from_recovery_data(pos_data),
        strategy=str(pos_data.get("strategy", "")),
        fee_rate=float(pos_data.get("fee_rate", 0.003)),
    )

    recovered_coid = str(pos_data.get("client_order_id") or "").strip()
    if recovered_coid:
        position.metadata["client_order_id"] = recovered_coid

    stop_price = pos_data.get("stop_price")
    if stop_price is not None:
        position.stop_price = float(stop_price)

    return position


def _position_state_from_recovery_data(
    pos_data: Mapping[str, Any],
) -> PositionState:
    state = pos_data.get("state", PositionState.SURVIVAL.value)
    if isinstance(state, PositionState):
        return state
    return PositionState(str(state).lower())
