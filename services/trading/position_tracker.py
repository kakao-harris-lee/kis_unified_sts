"""Position Tracker

Tracks open positions and manages state transitions.

Maintains position state for the trading pipeline:
- Tracks all open positions
- Updates prices and highest/lowest values
- Manages state transitions (SURVIVAL → BREAKEVEN → MAXIMIZE)
- Maps positions to their originating strategies

Usage:
    tracker = PositionTracker()

    # Add position from filled order
    position = tracker.add_position(
        code="005930",
        name="삼성전자",
        entry_price=71000,
        quantity=10,
        strategy="mean_reversion",
    )

    # Update prices
    tracker.update_prices({"005930": {"close": 72000}})

    # Get positions
    positions = tracker.get_positions()
    positions_by_strategy = tracker.get_positions_by_strategy("mean_reversion")

    # Close position
    tracker.close_position(position.id, exit_price=72500, reason="TRAILING_STOP")
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from shared.models.position import Position, PositionSide, PositionState
from shared.utils.calc import validate_price

if TYPE_CHECKING:
    from shared.models.signal import Signal

logger = logging.getLogger(__name__)


# Validation constants
MIN_MAX_POSITIONS = 1
MAX_MAX_POSITIONS = 100
MIN_PRICE = 0.0
MAX_PRICE = 100_000_000.0  # 1억원 (reasonable max for Korean stocks)


class UUIDGenerator(Protocol):
    """Protocol for UUID generation (allows injection for testing)."""

    def __call__(self) -> str:
        """Generate a unique ID."""
        ...


def default_uuid_generator() -> str:
    """Default UUID generator."""
    return str(uuid.uuid4())


@dataclass
class PositionTrackerConfig:
    """Position tracker configuration"""

    # Maximum positions allowed
    max_positions: int = 10

    # Maximum positions per symbol
    max_positions_per_symbol: int = 1

    # State transition thresholds (can be overridden per strategy)
    default_breakeven_threshold_pct: float = 0.015  # 1.5%
    default_maximize_threshold_pct: float = 0.03  # 3%
    default_fee_rate: float = 0.003  # 0.3%

    # History limits (bounded memory)
    max_events: int = 1000
    max_closed_positions: int = 100

    # ClickHouse database name (empty = env default)
    database: str = ""

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_MAX_POSITIONS <= self.max_positions <= MAX_MAX_POSITIONS):
            raise ValueError(
                f"max_positions must be between {MIN_MAX_POSITIONS} "
                f"and {MAX_MAX_POSITIONS}, got {self.max_positions}"
            )

        if not (
            MIN_MAX_POSITIONS <= self.max_positions_per_symbol <= self.max_positions
        ):
            raise ValueError(
                f"max_positions_per_symbol must be between {MIN_MAX_POSITIONS} "
                f"and max_positions ({self.max_positions}), got {self.max_positions_per_symbol}"
            )

        if not (0 <= self.default_breakeven_threshold_pct <= 1.0):
            raise ValueError(
                f"default_breakeven_threshold_pct must be between 0 and 1.0, "
                f"got {self.default_breakeven_threshold_pct}"
            )

        if not (0 <= self.default_maximize_threshold_pct <= 1.0):
            raise ValueError(
                f"default_maximize_threshold_pct must be between 0 and 1.0, "
                f"got {self.default_maximize_threshold_pct}"
            )

        if self.default_maximize_threshold_pct <= self.default_breakeven_threshold_pct:
            raise ValueError(
                f"default_maximize_threshold_pct ({self.default_maximize_threshold_pct}) "
                f"must be greater than default_breakeven_threshold_pct "
                f"({self.default_breakeven_threshold_pct})"
            )

        if not (0 <= self.default_fee_rate <= 0.1):
            raise ValueError(
                f"default_fee_rate must be between 0 and 0.1, got {self.default_fee_rate}"
            )

        if self.max_events < 1:
            raise ValueError(f"max_events must be >= 1, got {self.max_events}")

        if self.max_closed_positions < 1:
            raise ValueError(
                f"max_closed_positions must be >= 1, got {self.max_closed_positions}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PositionTrackerConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary

        Returns:
            Validated PositionTrackerConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        max_positions = data.get("max_positions", 10)
        max_per_symbol = data.get("max_positions_per_symbol", 1)
        breakeven_pct = data.get("default_breakeven_threshold_pct", 0.015)
        maximize_pct = data.get("default_maximize_threshold_pct", 0.03)
        fee_rate = data.get("default_fee_rate", 0.003)
        max_events = data.get("max_events", 1000)
        max_closed = data.get("max_closed_positions", 100)
        database = data.get("database", "")

        # Type validation
        if not isinstance(max_positions, int):
            raise TypeError(f"max_positions must be int, got {type(max_positions)}")
        if not isinstance(max_per_symbol, int):
            raise TypeError(
                f"max_positions_per_symbol must be int, got {type(max_per_symbol)}"
            )
        if not isinstance(breakeven_pct, (int, float)):
            raise TypeError(
                f"default_breakeven_threshold_pct must be numeric, got {type(breakeven_pct)}"
            )
        if not isinstance(maximize_pct, (int, float)):
            raise TypeError(
                f"default_maximize_threshold_pct must be numeric, got {type(maximize_pct)}"
            )
        if not isinstance(fee_rate, (int, float)):
            raise TypeError(f"default_fee_rate must be numeric, got {type(fee_rate)}")

        return cls(
            max_positions=int(max_positions),
            max_positions_per_symbol=int(max_per_symbol),
            default_breakeven_threshold_pct=float(breakeven_pct),
            default_maximize_threshold_pct=float(maximize_pct),
            default_fee_rate=float(fee_rate),
            max_events=int(max_events),
            max_closed_positions=int(max_closed),
            database=str(database),
        )


@dataclass
class PositionEvent:
    """Position lifecycle event"""

    event_type: str  # "opened", "state_changed", "closed"
    position_id: str
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


class PositionTracker:
    """Position state tracker

    Tracks open positions and their state transitions.
    Provides position queries by various criteria.

    Usage:
        tracker = PositionTracker()

        # Add from signal
        position = tracker.add_from_signal(signal, quantity=10)

        # Update all prices
        tracker.update_prices(market_data)

        # Update states based on thresholds
        transitions = tracker.update_states()

        # Close position
        tracker.close_position(position_id, exit_price, reason)

        # For testing with deterministic IDs:
        tracker = PositionTracker(
            uuid_generator=lambda: "test-id-123",
        )
    """

    def __init__(
        self,
        config: PositionTrackerConfig | None = None,
        uuid_generator: Callable[[], str] | None = None,
    ):
        """
        Args:
            config: Tracker configuration
            uuid_generator: Optional UUID generator for testing (default: uuid4)
        """
        self.config = config or PositionTrackerConfig()

        # UUID generator (injectable for testing)
        self._uuid_generator = uuid_generator or default_uuid_generator

        # Active positions: id -> Position
        self._positions: dict[str, Position] = {}

        # Index: symbol -> list of position ids
        self._by_symbol: dict[str, list[str]] = {}

        # Index: strategy -> list of position ids
        self._by_strategy: dict[str, list[str]] = {}

        # Event history (bounded with deque)
        self._events: deque[PositionEvent] = deque(maxlen=self.config.max_events)

        # Closed positions (bounded with deque)
        self._closed_positions: deque[Position] = deque(
            maxlen=self.config.max_closed_positions
        )

        logger.info(
            f"PositionTracker initialized: max_positions={self.config.max_positions}"
        )

    @property
    def positions(self) -> list[Position]:
        """Get all open positions"""
        return list(self._positions.values())

    @property
    def position_count(self) -> int:
        """Number of open positions"""
        return len(self._positions)

    def can_open_position(self, symbol: str | None = None) -> bool:
        """Check if a new position can be opened"""
        # Check max positions
        if self.position_count >= self.config.max_positions:
            return False

        # Check per-symbol limit
        if symbol:
            symbol_positions = len(self._by_symbol.get(symbol, []))
            if symbol_positions >= self.config.max_positions_per_symbol:
                return False

        return True

    def add_position(
        self,
        code: str,
        name: str,
        entry_price: float,
        quantity: int,
        strategy: str,
        side: PositionSide = PositionSide.LONG,
        fee_rate: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Position | None:
        """Add a new position

        Returns:
            Position if added successfully, None if limits exceeded
        """
        if not self.can_open_position(code):
            logger.warning(
                f"Cannot open position for {code}: "
                f"max_positions={self.config.max_positions}, "
                f"current={self.position_count}"
            )
            return None

        position_id = self._generate_id()

        position = Position(
            id=position_id,
            code=code,
            name=name,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            current_price=entry_price,
            highest_price=entry_price,
            lowest_price=entry_price,
            state=PositionState.SURVIVAL,
            strategy=strategy,
            fee_rate=fee_rate or self.config.default_fee_rate,
            metadata=metadata or {},
        )

        # Add to main dict
        self._positions[position_id] = position

        # Update indices
        if code not in self._by_symbol:
            self._by_symbol[code] = []
        self._by_symbol[code].append(position_id)

        if strategy not in self._by_strategy:
            self._by_strategy[strategy] = []
        self._by_strategy[strategy].append(position_id)

        # Record event
        self._record_event(
            "opened",
            position_id,
            {
                "code": code,
                "entry_price": entry_price,
                "quantity": quantity,
                "strategy": strategy,
            },
        )

        logger.info(
            f"Position opened: {code} @ {entry_price:,.0f} x {quantity} "
            f"(strategy={strategy}, id={position_id[:8]})"
        )

        return position

    def add_from_signal(
        self,
        signal: Signal,
        quantity: int,
        side: PositionSide = PositionSide.LONG,
    ) -> Position | None:
        """Add position from entry signal"""
        return self.add_position(
            code=signal.code,
            name=signal.name,
            entry_price=signal.price,
            quantity=quantity,
            strategy=signal.strategy,
            side=side,
        )

    def add_recovered_position(self, position: Position) -> bool:
        """Add a position recovered from Redis (preserves original ID and state).

        Returns:
            True if added successfully, False if duplicate ID.
        """
        if position.id in self._positions:
            logger.warning(f"Duplicate position ID on recovery: {position.id[:8]}")
            return False

        self._positions[position.id] = position

        # Update indices
        if position.code not in self._by_symbol:
            self._by_symbol[position.code] = []
        self._by_symbol[position.code].append(position.id)

        if position.strategy not in self._by_strategy:
            self._by_strategy[position.strategy] = []
        self._by_strategy[position.strategy].append(position.id)

        self._record_event(
            "recovered",
            position.id,
            {
                "code": position.code,
                "entry_price": position.entry_price,
                "quantity": position.quantity,
                "strategy": position.strategy,
                "state": position.state.value,
            },
        )

        logger.info(
            f"Position recovered: {position.code} @ {position.entry_price:,.0f} x {position.quantity} "
            f"(strategy={position.strategy}, state={position.state.value}, id={position.id[:8]})"
        )
        return True

    def get_position(self, position_id: str) -> Position | None:
        """Get position by ID"""
        return self._positions.get(position_id)

    def get_positions_by_symbol(self, symbol: str) -> list[Position]:
        """Get positions for a symbol"""
        position_ids = self._by_symbol.get(symbol, [])
        return [self._positions[pid] for pid in position_ids if pid in self._positions]

    def get_positions_by_strategy(self, strategy: str) -> list[Position]:
        """Get positions for a strategy"""
        position_ids = self._by_strategy.get(strategy, [])
        return [self._positions[pid] for pid in position_ids if pid in self._positions]

    def update_prices(self, market_data: dict[str, Any]):
        """Update prices for all positions

        Args:
            market_data: Dict mapping symbol to price data
                {"005930": {"close": 71000}, ...} or
                {"005930": 71000, ...}

        Note:
            Invalid prices (None, negative, out of range) are silently ignored
            with a debug log message.
        """
        for position in self._positions.values():
            price_data = market_data.get(position.code)
            if price_data is None:
                continue

            # Extract price from various formats
            if isinstance(price_data, dict):
                price = price_data.get("close") or price_data.get("price")
            else:
                price = price_data

            # Validate price before updating
            if not validate_price(price, MIN_PRICE, MAX_PRICE):
                logger.debug(
                    f"Invalid price for {position.code}: {price} "
                    f"(must be between {MIN_PRICE} and {MAX_PRICE})"
                )
                continue

            position.update_price(float(price))

    def update_states(
        self,
        breakeven_threshold: float | None = None,
        maximize_threshold: float | None = None,
    ) -> list[tuple[Position, PositionState, PositionState]]:
        """Update position states based on profit thresholds

        Returns:
            List of (position, old_state, new_state) for positions that transitioned
        """
        breakeven_pct = (
            breakeven_threshold or self.config.default_breakeven_threshold_pct
        )
        maximize_pct = maximize_threshold or self.config.default_maximize_threshold_pct

        transitions = []

        for position in self._positions.values():
            old_state = position.state
            new_state = self._check_state_transition(
                position, breakeven_pct, maximize_pct
            )

            if new_state and new_state != old_state:
                position.state = new_state

                # Update stop price for breakeven
                if new_state == PositionState.BREAKEVEN:
                    position.stop_price = position.entry_price * (1 + position.fee_rate)

                transitions.append((position, old_state, new_state))

                self._record_event(
                    "state_changed",
                    position.id,
                    {
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "profit_rate": position.profit_rate,
                    },
                )

                logger.info(
                    f"State transition: {position.code} "
                    f"{old_state.value} → {new_state.value} "
                    f"(profit={position.profit_pct:+.2f}%)"
                )

        return transitions

    def _check_state_transition(
        self,
        position: Position,
        breakeven_pct: float,
        maximize_pct: float,
    ) -> PositionState | None:
        """Check if position should transition to new state"""
        profit_rate = position.profit_rate

        if position.state == PositionState.SURVIVAL:
            if profit_rate >= breakeven_pct:
                return PositionState.BREAKEVEN

        elif position.state == PositionState.BREAKEVEN:
            if profit_rate >= maximize_pct:
                return PositionState.MAXIMIZE

        return None

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str,
        quantity: int | None = None,
    ) -> Position | None:
        """Close a position (full or partial).

        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Exit reason (e.g., "TRAILING_STOP", "STOP_LOSS")
            quantity: Number of shares to close. None or >= position.quantity
                      means full close. A value < position.quantity triggers
                      a partial close (reduces quantity, position stays active).

        Returns:
            Closed position (full close) or a copy with partial close info,
            or None if not found.
        """
        position = self._positions.get(position_id)
        if not position:
            logger.warning(f"Position not found: {position_id}")
            return None

        # Determine close quantity
        close_qty = (
            quantity if quantity is not None and quantity > 0 else position.quantity
        )

        if close_qty >= position.quantity:
            # Full close — existing behavior
            return self._full_close(position, position_id, exit_price, reason)
        else:
            # Partial close — reduce quantity, keep position active
            return self._partial_close(position, close_qty, exit_price, reason)

    def _full_close(
        self,
        position: Position,
        position_id: str,
        exit_price: float,
        reason: str,
    ) -> Position:
        """Fully close a position — removes from active tracking."""
        # Update position
        position.exit_triggered = True
        position.exit_reason = reason
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.current_price = exit_price

        # Remove from active
        del self._positions[position_id]

        # Remove from indices using O(n) remove instead of O(n) list comprehension
        # Both are O(n), but remove() is cleaner and has better constant factors
        if position.code in self._by_symbol:
            try:
                self._by_symbol[position.code].remove(position_id)
            except ValueError:
                pass  # Already removed
            # Clean up empty lists
            if not self._by_symbol[position.code]:
                del self._by_symbol[position.code]

        if position.strategy in self._by_strategy:
            try:
                self._by_strategy[position.strategy].remove(position_id)
            except ValueError:
                pass  # Already removed
            # Clean up empty lists
            if not self._by_strategy[position.strategy]:
                del self._by_strategy[position.strategy]

        # Add to closed history (deque automatically maintains maxlen)
        self._closed_positions.append(position)

        # Record event
        self._record_event(
            "closed",
            position_id,
            {
                "code": position.code,
                "exit_price": exit_price,
                "reason": reason,
                "profit_rate": position.profit_rate,
                "hold_minutes": position.get_hold_duration(),
            },
        )

        logger.info(
            f"Position closed: {position.code} @ {exit_price:,.0f} "
            f"(reason={reason}, profit={position.profit_pct:+.2f}%)"
        )

        return position

    def _partial_close(
        self,
        position: Position,
        close_qty: int,
        exit_price: float,
        reason: str,
    ) -> Position:
        """Partially close a position — reduces quantity, keeps position active.

        Creates a synthetic closed-position record for the partial portion
        and reduces the original position's quantity.

        Args:
            position: The active position to partially close.
            close_qty: Number of shares to close.
            exit_price: Exit price for the partial close.
            reason: Exit reason.

        Returns:
            A copy of the position representing the closed portion,
            with quantity set to close_qty and exit fields populated.
        """
        import copy

        # Create a snapshot for the closed portion
        closed_portion = copy.copy(position)
        closed_portion.quantity = close_qty
        closed_portion.exit_triggered = True
        closed_portion.exit_reason = reason
        closed_portion.exit_price = exit_price
        closed_portion.exit_time = datetime.now()
        closed_portion.current_price = exit_price

        # Reduce the original position's quantity (stays in active tracking)
        position.quantity -= close_qty
        position.current_price = exit_price

        # Add partial close to closed history
        self._closed_positions.append(closed_portion)

        # Record event
        self._record_event(
            "partial_closed",
            position.id,
            {
                "code": position.code,
                "exit_price": exit_price,
                "reason": reason,
                "closed_qty": close_qty,
                "remaining_qty": position.quantity,
                "profit_rate": closed_portion.profit_rate,
                "hold_minutes": position.get_hold_duration(),
            },
        )

        logger.info(
            f"Position partially closed: {position.code} @ {exit_price:,.0f} "
            f"x {close_qty} (reason={reason}, remaining={position.quantity}, "
            f"profit={closed_portion.profit_pct:+.2f}%)"
        )

        return closed_portion

    def close_all(
        self, market_data: dict[str, Any], reason: str = "CLOSE_ALL"
    ) -> list[Position]:
        """Close all positions

        Args:
            market_data: Current market prices
            reason: Reason for closing all

        Returns:
            List of closed positions
        """
        closed = []
        position_ids = list(self._positions.keys())

        for position_id in position_ids:
            position = self._positions.get(position_id)
            if not position:
                continue

            # Get exit price
            price_data = market_data.get(position.code, {})
            if isinstance(price_data, dict):
                exit_price = price_data.get("close") or position.current_price
            else:
                exit_price = price_data or position.current_price

            if not exit_price or exit_price <= 0:
                logger.warning(
                    f"Skipping close for {position.code}: invalid price {exit_price}"
                )
                continue

            closed_pos = self.close_position(position_id, exit_price, reason)
            if closed_pos:
                closed.append(closed_pos)

        logger.info(f"Closed all positions: {len(closed)} positions")
        return closed

    def _generate_id(self) -> str:
        """Generate unique position ID using injected generator."""
        return self._uuid_generator()

    def _record_event(self, event_type: str, position_id: str, details: dict[str, Any]):
        """Record position event.

        Note: Uses deque with maxlen, so no manual trimming needed.
        """
        event = PositionEvent(
            event_type=event_type,
            position_id=position_id,
            timestamp=datetime.now(),
            details=details,
        )
        # deque with maxlen automatically discards oldest items
        self._events.append(event)

    def get_stats(self) -> dict[str, Any]:
        """Get tracker statistics"""
        total_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        winning = sum(1 for p in self._positions.values() if p.profit_rate > 0)

        closed_pnl = 0.0
        closed_wins = 0
        for p in self._closed_positions:
            if p.exit_price:
                # Use Position's built-in unrealized_pnl property
                # (current_price is set to exit_price when closing)
                pnl = p.unrealized_pnl
                closed_pnl += pnl
                if pnl > 0:
                    closed_wins += 1

        closed_count = len(self._closed_positions)

        return {
            "open_positions": self.position_count,
            "max_positions": self.config.max_positions,
            "unrealized_pnl": total_pnl,
            "winning_positions": winning,
            "by_strategy": {
                strategy: len(ids) for strategy, ids in self._by_strategy.items()
            },
            "by_symbol": {symbol: len(ids) for symbol, ids in self._by_symbol.items()},
            "closed_count": closed_count,
            "closed_pnl": closed_pnl,
            "closed_win_rate": (
                closed_wins / closed_count * 100 if closed_count > 0 else 0
            ),
            "events_count": len(self._events),
        }

    # Shared SQL column list for swing_positions INSERT (DRY)
    _SWING_INSERT_COLS = (
        "(id, code, name, entry_date, entry_price, quantity, strategy, "
        "stop_loss_price, high_since_entry, current_state, is_open, "
        "exit_date, exit_price, exit_reason, pnl, side, fee_rate)"
    )
    _RL_TRADE_INSERT_COLS = (
        "(id, asset_class, code, name, side, strategy, entry_date, entry_price, "
        "exit_date, exit_price, quantity, pnl, pnl_pct, hold_seconds, exit_reason, metadata_json)"
    )
    _RL_TRADES_SCHEMA_TEMPLATE = """
        CREATE TABLE IF NOT EXISTS {database}.rl_trades (
            id String,
            asset_class LowCardinality(String),
            code String,
            name String,
            side LowCardinality(String),
            strategy LowCardinality(String),
            entry_date DateTime,
            entry_price Float64,
            exit_date DateTime,
            exit_price Float64,
            quantity Int32,
            pnl Float64,
            pnl_pct Float64,
            hold_seconds UInt32,
            exit_reason String,
            metadata_json String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(exit_date)
        ORDER BY (asset_class, strategy, exit_date, id)
        TTL exit_date + INTERVAL 180 DAY
        COMMENT 'Closed RL trade records for performance analytics'
    """

    def _get_db_client(self):
        """Get ClickHouse client and database name for position persistence.

        Returns:
            Tuple of (ClickHouseClient, database_name)
        """
        from shared.db.client import ClickHouseClient
        from shared.db.config import ClickHouseConfig

        ch = ClickHouseClient(ClickHouseConfig())
        database = self.config.database if self.config.database else ch.config.database
        if not database.replace("_", "").isalnum():
            raise ValueError(f"Invalid database name: {database}")
        return ch, database

    async def save_to_db(self) -> int:
        """Persist all open positions to ClickHouse swing_positions table.

        Returns:
            Number of positions saved
        """
        if not self._positions:
            return 0

        try:
            ch, database = self._get_db_client()

            rows = []
            for position in self._positions.values():
                rows.append(
                    (
                        position.id,
                        position.code,
                        position.name,
                        position.entry_time,
                        position.entry_price,
                        position.quantity,
                        position.strategy,
                        position.stop_price,
                        position.highest_price,
                        position.state.value,
                        1,  # is_open
                        None,  # exit_date
                        None,  # exit_price
                        None,  # exit_reason
                        None,  # pnl
                        position.side.value,
                        position.fee_rate,
                    )
                )

            def _sync_save():
                client = ch.get_sync_client()
                client.execute(
                    f"INSERT INTO {database}.swing_positions "
                    f"{self._SWING_INSERT_COLS} VALUES",
                    rows,
                )

            await asyncio.to_thread(_sync_save)

            logger.info(f"Saved {len(rows)} swing positions to DB")
            return len(rows)

        except Exception as e:
            logger.error(f"Failed to save swing positions: {e}")
            return 0

    async def save_closed_to_db(self, position: Position) -> bool:
        """Persist a single closed position to ClickHouse.

        Args:
            position: Closed position with exit_price/exit_time set.

        Returns:
            True if saved successfully
        """
        if not position.exit_price or not position.exit_time:
            return False

        try:
            ch, database = self._get_db_client()

            pnl = self._calc_realized_pnl(position)

            row = (
                position.id,
                position.code,
                position.name,
                position.entry_time,
                position.entry_price,
                position.quantity,
                position.strategy,
                position.stop_price,
                position.highest_price,
                position.state.value,
                0,  # is_open = closed
                position.exit_time,
                position.exit_price,
                position.exit_reason,
                pnl,
                position.side.value,
                position.fee_rate,
            )

            def _sync_save():
                client = ch.get_sync_client()
                client.execute(
                    f"INSERT INTO {database}.swing_positions "
                    f"{self._SWING_INSERT_COLS} VALUES",
                    [row],
                )

            await asyncio.to_thread(_sync_save)

            logger.info(
                f"Persisted closed position: {position.code} "
                f"(pnl={pnl:+,.0f}, id={position.id[:8]})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to persist closed position {position.id[:8]}: {e}")
            return False

    async def save_rl_trade_to_db(self, position: Position, asset_class: str) -> bool:
        """Persist a closed RL trade to ClickHouse rl_trades table."""
        if not position.exit_price or not position.exit_time:
            return False

        try:
            ch, database = self._get_db_client()

            pnl = self._calc_realized_pnl(position)
            hold_seconds = 0
            if position.entry_time and position.exit_time:
                hold_seconds = max(
                    0, int((position.exit_time - position.entry_time).total_seconds())
                )

            metadata = position.metadata if isinstance(position.metadata, dict) else {}
            metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)

            row = (
                position.id,
                str(asset_class or "unknown"),
                position.code,
                position.name,
                position.side.value,
                position.strategy,
                position.entry_time,
                position.entry_price,
                position.exit_time,
                position.exit_price,
                position.quantity,
                pnl,
                position.profit_pct,
                hold_seconds,
                position.exit_reason or "",
                metadata_json,
            )

            def _sync_save():
                client = ch.get_sync_client()
                client.execute(self._RL_TRADES_SCHEMA_TEMPLATE.format(database=database))
                client.execute(
                    f"INSERT INTO {database}.rl_trades "
                    f"{self._RL_TRADE_INSERT_COLS} VALUES",
                    [row],
                )

            await asyncio.to_thread(_sync_save)

            logger.info(
                f"Persisted RL trade: {position.code} "
                f"(strategy={position.strategy}, pnl={pnl:+,.0f}, id={position.id[:8]})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to persist RL trade {position.id[:8]}: {e}")
            return False

    @staticmethod
    def _calc_realized_pnl(position: Position) -> float:
        """Calculate side-aware realized PnL for a closed position."""
        if not position.exit_price:
            return 0.0
        if position.side == PositionSide.LONG:
            return (position.exit_price - position.entry_price) * position.quantity
        return (position.entry_price - position.exit_price) * position.quantity

    async def load_from_db(self) -> int:
        """Load open positions from ClickHouse on startup.

        Returns:
            Number of positions loaded
        """
        try:
            ch, database = self._get_db_client()

            def _sync_load():
                client = ch.get_sync_client()
                return client.execute(f"""
                    SELECT id, code, name, entry_date, entry_price, quantity,
                           strategy, stop_loss_price, high_since_entry, current_state,
                           side, fee_rate
                    FROM {database}.swing_positions FINAL
                    WHERE is_open = 1
                    ORDER BY entry_date ASC
                    """)

            result = await asyncio.to_thread(_sync_load)

            loaded = 0
            for row in result:
                (
                    pos_id,
                    code,
                    name,
                    entry_time,
                    entry_price,
                    quantity,
                    strategy,
                    stop_price,
                    high_since_entry,
                    state_str,
                    side_str,
                    fee_rate_val,
                ) = row

                # Skip if already tracked
                if pos_id in self._positions:
                    continue

                # Map state string to PositionState
                try:
                    state = PositionState(state_str)
                except ValueError:
                    state = PositionState.SURVIVAL

                # Parse side
                try:
                    side = PositionSide(side_str)
                except (ValueError, KeyError):
                    side = PositionSide.LONG

                position = Position(
                    id=pos_id,
                    code=code,
                    name=name,
                    side=side,
                    quantity=quantity,
                    entry_price=entry_price,
                    entry_time=entry_time,
                    current_price=entry_price,
                    highest_price=high_since_entry or entry_price,
                    lowest_price=entry_price,
                    state=state,
                    strategy=strategy,
                    fee_rate=fee_rate_val if fee_rate_val else self.config.default_fee_rate,
                )
                position.stop_price = stop_price or 0.0

                # Add to tracker indices
                self._positions[pos_id] = position

                if code not in self._by_symbol:
                    self._by_symbol[code] = []
                self._by_symbol[code].append(pos_id)

                if strategy not in self._by_strategy:
                    self._by_strategy[strategy] = []
                self._by_strategy[strategy].append(pos_id)

                loaded += 1

            if loaded:
                logger.info(f"Loaded {loaded} swing positions from DB")
            return loaded

        except Exception as e:
            logger.error(f"Failed to load swing positions: {e}")
            return 0

    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent events (most recent first)"""
        # Convert deque to list for slicing, get last N items
        events_list = list(self._events)
        recent = events_list[-limit:] if len(events_list) > limit else events_list

        return [
            {
                "type": e.event_type,
                "position_id": e.position_id[:8],
                "timestamp": e.timestamp.isoformat(),
                "details": e.details,
            }
            for e in recent
        ]
