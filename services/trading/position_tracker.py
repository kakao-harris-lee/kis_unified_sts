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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from shared.exceptions import InfrastructureError, TradingSystemError, ValidationError
from shared.models.position import Position, PositionSide, PositionState
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedger, RuntimeLedgerError
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

    # Legacy database name kept for backward-compatible config construction.
    database: str = ""

    # Batch insert configuration
    batch_size: int = 50  # Number of closed positions to batch before flush
    flush_interval_seconds: float = 5.0  # Max seconds to wait before flush

    # Asset class for this tracker instance (used to guard stock-only paths)
    asset_class: str = ""  # e.g. 'stock', 'futures'

    # Runtime ledger backend.
    runtime_ledger_backend: str = "sqlite"  # sqlite|null
    runtime_ledger_sqlite_path: str = ""

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

        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")

        if self.flush_interval_seconds < 0:
            raise ValueError(
                f"flush_interval_seconds must be >= 0, got {self.flush_interval_seconds}"
            )
        if self.runtime_ledger_backend not in {"sqlite", "null"}:
            raise ValueError(
                "runtime_ledger_backend must be one of sqlite|null, "
                f"got {self.runtime_ledger_backend!r}"
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
        batch_size = data.get("batch_size", 50)
        flush_interval = data.get("flush_interval_seconds", 5.0)
        asset_class = data.get("asset_class", "")
        runtime_ledger_backend = data.get("runtime_ledger_backend", "sqlite")
        runtime_ledger_sqlite_path = data.get("runtime_ledger_sqlite_path", "")

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
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be int, got {type(batch_size)}")
        if not isinstance(flush_interval, (int, float)):
            raise TypeError(
                f"flush_interval_seconds must be numeric, got {type(flush_interval)}"
            )

        return cls(
            max_positions=int(max_positions),
            max_positions_per_symbol=int(max_per_symbol),
            default_breakeven_threshold_pct=float(breakeven_pct),
            default_maximize_threshold_pct=float(maximize_pct),
            default_fee_rate=float(fee_rate),
            max_events=int(max_events),
            max_closed_positions=int(max_closed),
            database=str(database),
            batch_size=int(batch_size),
            flush_interval_seconds=float(flush_interval),
            asset_class=str(asset_class),
            runtime_ledger_backend=str(runtime_ledger_backend),
            runtime_ledger_sqlite_path=str(runtime_ledger_sqlite_path),
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
        redis_client: Any | None = None,
        ch_fail_tracker: Any | None = None,
        runtime_ledger: RuntimeLedger | None = None,
    ):
        """
        Args:
            config: Tracker configuration
            uuid_generator: Optional UUID generator for testing (default: uuid4)
            redis_client: Optional async Redis client (DB 1).
            ch_fail_tracker: Legacy parameter ignored after external DB removal.
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

        # Idempotency index: client_order_id -> position_id
        # Used to deduplicate retried add_position calls (e.g., when the
        # caller retries after a transient broker ACK timeout on a fill
        # that actually succeeded).  Populated only when the caller passes
        # a non-empty ``client_order_id`` to :meth:`add_position`.
        self._by_client_order_id: dict[str, str] = {}

        # Event history (bounded with deque)
        self._events: deque[PositionEvent] = deque(maxlen=self.config.max_events)

        # Closed positions (bounded with deque)
        self._closed_positions: deque[Position] = deque(
            maxlen=self.config.max_closed_positions
        )

        # Batch accumulators for DB inserts
        self._pending_swing_positions: list[tuple[Any, ...]] = []
        self._pending_futures_trades: list[tuple[Any, ...]] = []
        self._pending_stock_trades: list[tuple[Any, ...]] = []
        self._batch_lock: asyncio.Lock = asyncio.Lock()
        self._runtime_ledger: RuntimeLedger | None = runtime_ledger

        # Auto-flush background task
        self._auto_flush_task: asyncio.Task | None = None

        _ = ch_fail_tracker, redis_client
        self._ch_fail_tracker: Any | None = None

        logger.info(
            f"PositionTracker initialized: max_positions={self.config.max_positions}"
        )

        # Start auto-flush task if configured
        self._start_auto_flush_task()

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
        execution_venue: str = "KRX",
        client_order_id: str | None = None,
        stop_price: float | None = None,
    ) -> Position | None:
        """Add a new position

        Args:
            code: Stock/futures code
            name: Stock/futures name
            entry_price: Entry price
            quantity: Position quantity
            strategy: Strategy name
            side: Position side (LONG/SHORT)
            fee_rate: Trading fee rate (overrides config default)
            metadata: Additional metadata dict
            execution_venue: Execution venue (KRX/ATS)
            stop_price: Optional initial hard-stop price. When supplied (and
                positive) it is persisted on the position so reconciliation /
                exports do not record ``stop_loss_price = 0``. The dynamic exit
                strategy (e.g. ThreeStageExit) may later ratchet this value.
            client_order_id: Optional idempotency key, typically a stable
                identifier derived from the originating signal or broker
                client-order-id.  When supplied, a second call with the
                same key returns the *existing* position instead of
                opening a duplicate one.  Required for safe retries
                across orchestrator crashes / broker ACK timeouts.

        Returns:
            Position if added successfully, None if limits exceeded.
            When ``client_order_id`` matches an existing open position,
            that position is returned (no new record created).
        """
        # Idempotency short-circuit: same client_order_id => same position.
        # We check before ``can_open_position`` so that retries are not
        # rejected by max_positions_per_symbol bounds.
        coid = (client_order_id or "").strip()
        if coid:
            existing_id = self._by_client_order_id.get(coid)
            if existing_id is not None:
                existing = self._positions.get(existing_id)
                if existing is not None:
                    logger.info(
                        "Idempotent add_position: client_order_id=%s already "
                        "maps to position id=%s (code=%s); returning existing.",
                        coid,
                        existing_id[:8],
                        existing.code,
                    )
                    return existing
                # Stale index entry (existing position was closed) — drop it
                # and fall through to open a fresh position.  This is safe
                # because a closed position cannot be "re-opened" via retry.
                self._by_client_order_id.pop(coid, None)

        if not self.can_open_position(code):
            logger.warning(
                f"Cannot open position for {code}: "
                f"max_positions={self.config.max_positions}, "
                f"current={self.position_count}"
            )
            return None

        position_id = self._generate_id()

        # Stash client_order_id in metadata so it survives Redis round-trips
        # and can be rebuilt on recovery.  The param is authoritative —
        # any conflicting value already in metadata is overwritten so the
        # in-memory index and the persisted record agree.
        position_metadata = dict(metadata or {})
        if coid:
            position_metadata["client_order_id"] = coid

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
            metadata=position_metadata,
            execution_venue=execution_venue,
        )

        # Persist an initial hard-stop when supplied so the position is never
        # recorded with stop_loss_price=0. Strategies whose stop is purely
        # derived at runtime (no absolute stop on the signal) keep the prior
        # default of 0.0.
        if stop_price is not None and stop_price > 0:
            position.stop_price = float(stop_price)

        # Add to main dict
        self._positions[position_id] = position

        # Update indices
        if code not in self._by_symbol:
            self._by_symbol[code] = []
        self._by_symbol[code].append(position_id)

        if strategy not in self._by_strategy:
            self._by_strategy[strategy] = []
        self._by_strategy[strategy].append(position_id)

        if coid:
            self._by_client_order_id[coid] = position_id

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
        client_order_id: str | None = None,
    ) -> Position | None:
        """Add position from entry signal.

        When ``client_order_id`` is not supplied explicitly, the signal's
        ``metadata['client_order_id']`` (or ``metadata['signal_id']``) is
        used as the idempotency key so retries of the same signal cannot
        create duplicate positions.  When neither is present, no
        idempotency key is registered \u2014 behavior matches the legacy
        callsites that have not yet adopted the contract.
        """
        meta = getattr(signal, "metadata", None) or {}
        effective_coid = client_order_id
        if not effective_coid:
            for meta_key in ("client_order_id", "signal_id"):
                candidate = str(meta.get(meta_key, "") or "").strip()
                if candidate:
                    effective_coid = candidate
                    break

        # Forward an absolute stop price from the signal metadata when present
        # so the persisted position carries a non-zero stop_loss_price.
        stop_price: float | None = None
        try:
            raw_stop = meta.get("stop_loss")
            if raw_stop is not None and float(raw_stop) > 0:
                stop_price = float(raw_stop)
        except (TypeError, ValueError):
            stop_price = None

        position_metadata: dict[str, Any] = {}
        for key in ("stop_loss", "take_profit"):
            if key in meta:
                position_metadata[key] = meta[key]

        return self.add_position(
            code=signal.code,
            name=signal.name,
            entry_price=signal.price,
            quantity=quantity,
            strategy=signal.strategy,
            side=side,
            client_order_id=effective_coid,
            stop_price=stop_price,
            metadata=position_metadata,
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

        # Re-register the idempotency key (if any) so retries from the
        # producer after a restart remain deduplicated.
        recovered_coid = ""
        if isinstance(position.metadata, dict):
            recovered_coid = str(position.metadata.get("client_order_id") or "").strip()
        if recovered_coid:
            self._by_client_order_id[recovered_coid] = position.id

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

    def remove_position(
        self,
        position_id: str,
        *,
        reason: str = "removed",
    ) -> Position | None:
        """Remove an active position without recording a trade close.

        Used for broker reconciliation when the broker is the source of truth
        and a recovered Redis position no longer exists in the account.
        """
        position = self._positions.pop(position_id, None)
        if position is None:
            logger.warning("Position not found for removal: %s", position_id)
            return None

        if position.code in self._by_symbol:
            try:
                self._by_symbol[position.code].remove(position_id)
            except ValueError:
                pass
            if not self._by_symbol[position.code]:
                del self._by_symbol[position.code]

        if position.strategy in self._by_strategy:
            try:
                self._by_strategy[position.strategy].remove(position_id)
            except ValueError:
                pass
            if not self._by_strategy[position.strategy]:
                del self._by_strategy[position.strategy]

        stale_coid: str | None = None
        for coid, pid in self._by_client_order_id.items():
            if pid == position_id:
                stale_coid = coid
                break
        if stale_coid is not None:
            self._by_client_order_id.pop(stale_coid, None)

        self._record_event(
            "removed",
            position_id,
            {
                "code": position.code,
                "quantity": position.quantity,
                "strategy": position.strategy,
                "reason": reason,
            },
        )
        logger.info(
            "Position removed: %s x%d (reason=%s, id=%s)",
            position.code,
            position.quantity,
            reason,
            position_id[:8],
        )
        return position

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

        # Drop the idempotency index entry for this position, if any.
        # Done by reverse lookup rather than reading metadata so the
        # index stays consistent even when callers mutate metadata.
        closed_coid: str | None = None
        for _coid, _pid in self._by_client_order_id.items():
            if _pid == position_id:
                closed_coid = _coid
                break
        if closed_coid is not None:
            self._by_client_order_id.pop(closed_coid, None)

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

    def _uses_legacy_persistence(self) -> bool:
        """Compatibility guard for removed external DB persistence."""
        return False

    def _get_runtime_ledger(self) -> RuntimeLedger | None:
        """Return the configured RuntimeLedger, lazily creating SQLite backend."""
        backend = self.config.runtime_ledger_backend
        if backend == "null":
            return None

        if self._runtime_ledger is not None:
            return self._runtime_ledger

        try:
            from shared.storage.runtime_ledger import SQLiteRuntimeLedger

            storage_config = StorageConfig.load_or_default()
            sqlite_config = storage_config.runtime_storage.sqlite
            if self.config.runtime_ledger_sqlite_path:
                sqlite_config = sqlite_config.model_copy(
                    update={"path": self.config.runtime_ledger_sqlite_path}
                )
            self._runtime_ledger = SQLiteRuntimeLedger(sqlite_config)
            return self._runtime_ledger
        except Exception as e:
            logger.error("Failed to initialize runtime ledger: %s", e, exc_info=True)
            return None

    def _position_asset_class(self, fallback: str = "unknown") -> str:
        """Return normalized tracker asset class for ledger rows."""
        return str(self.config.asset_class or fallback or "unknown")

    def _position_snapshot_payload(
        self,
        position: Position,
        *,
        asset_class: str | None = None,
        is_open: bool | None = None,
    ) -> dict[str, Any]:
        """Build a RuntimeLedger position snapshot payload."""
        open_flag = position.exit_time is None if is_open is None else is_open
        return {
            "id": position.id,
            "position_id": position.id,
            "asset_class": asset_class or self._position_asset_class(),
            "code": position.code,
            "symbol": position.code,
            "name": position.name,
            "side": position.side.value,
            "strategy": position.strategy,
            "quantity": position.quantity,
            "entry_time": position.entry_time,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "highest_price": position.highest_price,
            "lowest_price": position.lowest_price,
            "stop_price": position.stop_price,
            "state": position.state.value,
            "is_open": int(open_flag),
            "exit_time": position.exit_time,
            "exit_price": position.exit_price,
            "exit_reason": position.exit_reason,
            "pnl": self._calc_realized_pnl(position) if not open_flag else None,
            "fee_rate": position.fee_rate,
            "execution_venue": position.execution_venue,
            "metadata": position.metadata,
        }

    def _trade_payload(
        self,
        position: Position,
        *,
        asset_class: str,
    ) -> dict[str, Any]:
        """Build a RuntimeLedger trade payload from a closed position."""
        pnl = self._calc_realized_pnl(position)
        hold_seconds = self._closed_hold_seconds(position)
        metadata = position.metadata if isinstance(position.metadata, dict) else {}
        entry_notional = max(position.entry_price * position.quantity, 1e-9)
        return {
            "id": position.id,
            "trade_id": position.id,
            "idempotency_key": f"{asset_class}:{position.id}",
            "asset_class": asset_class,
            "code": position.code,
            "symbol": position.code,
            "name": position.name,
            "side": position.side.value,
            "strategy": position.strategy,
            "execution_venue": position.execution_venue,
            "entry_time": position.entry_time,
            "entry_price": position.entry_price,
            "exit_time": position.exit_time,
            "exit_price": position.exit_price,
            "quantity": position.quantity,
            "pnl": pnl,
            "pnl_pct": (pnl / entry_notional) * 100.0,
            "hold_seconds": hold_seconds,
            "exit_reason": position.exit_reason or "",
            "exit_state": position.state.value if position.state else "",
            "commission": float(metadata.get("commission", 0.0)),
            "slippage": float(metadata.get("slippage", 0.0)),
            "fee_rate": position.fee_rate,
            "metadata": metadata,
        }

    @staticmethod
    def _parse_ledger_datetime(value: Any) -> datetime:
        """Parse ledger datetime values, falling back to now for malformed rows."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _parse_ledger_side(value: Any) -> PositionSide:
        try:
            return PositionSide(str(value or PositionSide.LONG.value).lower())
        except ValueError:
            return PositionSide.LONG

    @staticmethod
    def _parse_ledger_state(value: Any) -> PositionState:
        try:
            return PositionState(str(value or PositionState.SURVIVAL.value).lower())
        except ValueError:
            return PositionState.SURVIVAL

    def _position_from_ledger_row(self, row: dict[str, Any]) -> Position | None:
        """Convert a RuntimeLedger position snapshot row into a Position."""
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        position_id = row.get("position_id") or payload.get("id")
        code = row.get("symbol") or payload.get("code") or payload.get("symbol")
        if not position_id or not code:
            logger.warning("Skipping ledger position row with missing id/code: %s", row)
            return None

        side = self._parse_ledger_side(row.get("side") or payload.get("side"))
        state = self._parse_ledger_state(row.get("state") or payload.get("state"))
        entry_price = float(row.get("entry_price") or payload.get("entry_price") or 0.0)
        current_price = float(
            row.get("current_price") or payload.get("current_price") or entry_price
        )
        position = Position(
            id=str(position_id),
            code=str(code),
            name=str(row.get("name") or payload.get("name") or code),
            side=side,
            quantity=int(row.get("quantity") or payload.get("quantity") or 0),
            entry_price=entry_price,
            entry_time=self._parse_ledger_datetime(
                row.get("entry_time") or payload.get("entry_time")
            ),
            current_price=current_price,
            highest_price=float(
                row.get("high_since_entry")
                or payload.get("highest_price")
                or payload.get("high_since_entry")
                or entry_price
            ),
            lowest_price=float(
                row.get("low_since_entry")
                or payload.get("lowest_price")
                or payload.get("low_since_entry")
                or entry_price
            ),
            state=state,
            strategy=str(row.get("strategy") or payload.get("strategy") or ""),
            fee_rate=float(payload.get("fee_rate") or self.config.default_fee_rate),
            metadata=dict(payload.get("metadata") or {}),
            execution_venue=str(payload.get("execution_venue") or "KRX"),
        )
        position.stop_price = float(
            row.get("stop_price") or payload.get("stop_price") or 0.0
        )
        return position

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
        "execution_venue, stop_loss_price, high_since_entry, current_state, is_open, "
        "exit_date, exit_price, exit_reason, pnl, side, fee_rate)"
    )
    _FUTURES_TRADE_INSERT_COLS = (
        "(id, asset_class, code, name, side, strategy, execution_venue, entry_date, entry_price, "
        "exit_date, exit_price, quantity, pnl, pnl_pct, hold_seconds, exit_reason, metadata_json)"
    )
    _FUTURES_TRADES_SCHEMA_TEMPLATE = """
        CREATE TABLE IF NOT EXISTS {database}.rl_trades (
            id String,
            asset_class LowCardinality(String),
            code String,
            name String,
            side LowCardinality(String),
            strategy LowCardinality(String),
            execution_venue LowCardinality(String) DEFAULT 'KRX',
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
        COMMENT 'Closed futures trade records for performance analytics'
    """

    _STOCK_TRADE_INSERT_COLS = (
        "(id, code, name, side, strategy, execution_venue, "
        "entry_date, entry_price, exit_date, exit_price, quantity, "
        "pnl, pnl_pct, commission, slippage, hold_seconds, "
        "exit_reason, exit_state, metadata_json)"
    )

    def _get_db_client(self):
        """Return the removed legacy database client.

        The method remains only so older tests/extensions fail with an explicit
        removal message instead of importing deleted storage modules.
        """
        from shared.db.client import ClickHouseRemovedError

        raise ClickHouseRemovedError(
            "External position persistence has been removed; use RuntimeLedger"
        )

    @staticmethod
    def _db_datetime(value: datetime | None) -> datetime | None:
        """Return a stable naive UTC datetime for legacy tuple helpers."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    @staticmethod
    def _closed_hold_seconds(position: Position) -> int | None:
        """Return hold seconds for a closed position, or None if timestamps are invalid."""
        if not position.entry_time or not position.exit_time:
            return 0
        try:
            hold_seconds = int(
                (position.exit_time - position.entry_time).total_seconds()
            )
        except TypeError:
            logger.warning(
                "Closed position %s has incompatible entry/exit timestamps; skipping persistence",
                position.id[:8],
            )
            return None
        if hold_seconds < 0:
            logger.warning(
                "Closed position %s has exit_time before entry_time "
                "(entry=%s, exit=%s); skipping persistence",
                position.id[:8],
                position.entry_time,
                position.exit_time,
            )
            return None
        return hold_seconds

    async def save_to_db(self) -> int:
        """Persist all open positions to the configured runtime ledger.

        Returns:
            Number of positions saved
        """
        if not self._positions:
            return 0

        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is None:
                return 0
            try:
                for position in self._positions.values():
                    await asyncio.to_thread(
                        ledger.record_position_snapshot,
                        self._position_snapshot_payload(position, is_open=True),
                    )
                logger.info(
                    "Saved %d open positions to runtime ledger", len(self._positions)
                )
                return len(self._positions)
            except RuntimeLedgerError as e:
                logger.error("Failed to save open positions to runtime ledger: %s", e)
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
                        self._db_datetime(position.entry_time),
                        position.entry_price,
                        position.quantity,
                        position.strategy,
                        position.execution_venue,
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

        except InfrastructureError as e:
            logger.error(f"Failed to save swing positions: {e}")
            return 0

    async def reconcile_open_positions_to_db(
        self,
        *,
        exit_reason: str = "reconciled_broker_absent",
    ) -> dict[str, int]:
        """Synchronize open-position ledger rows with current active positions.

        Current tracker positions are inserted as open rows. Existing legacy
        open rows absent by both id and code are closed via replacement rows.
        """
        if not self._uses_legacy_persistence():
            open_saved = await self.save_to_db()
            logger.info(
                "Reconciled runtime ledger open positions: open_saved=%d",
                open_saved,
            )
            return {"open_saved": open_saved, "closed_orphans": 0}

        try:
            ch, database = self._get_db_client()
            current_positions = list(self._positions.values())
            current_keys = {
                (p.id, p.code, self._db_datetime(p.entry_time))
                for p in current_positions
            }

            def _sync_reconcile() -> dict[str, int]:
                client = ch.get_sync_client()
                rows = client.execute(f"""
                    SELECT id, code, name, entry_date, entry_price, quantity,
                           strategy, execution_venue, stop_loss_price,
                           high_since_entry, current_state, side, fee_rate
                    FROM {database}.swing_positions FINAL
                    WHERE is_open = 1
                    ORDER BY entry_date ASC, code ASC, id ASC
                    """)

                closed_at = datetime.now()
                close_rows = []
                for row in rows:
                    (
                        pos_id,
                        code,
                        name,
                        entry_time,
                        entry_price,
                        quantity,
                        strategy,
                        execution_venue,
                        stop_price,
                        high_since_entry,
                        state_str,
                        side_str,
                        fee_rate_val,
                    ) = row
                    if (pos_id, code, self._db_datetime(entry_time)) in current_keys:
                        continue
                    # Close the orphan at the best last-known price rather than
                    # the entry price. Closing at entry would record pnl=0
                    # (break-even) and silently discard real P&L — e.g. a
                    # position that rallied +28~55% above entry would still be
                    # logged as flat. ``high_since_entry`` is the only
                    # last-known price column persisted on the open row, so it
                    # is used as the exit-price proxy; we fall back to
                    # ``entry_price`` only when it is unusable.
                    entry_px = float(entry_price or 0.0)
                    qty = int(quantity or 0)
                    high_px = float(high_since_entry or 0.0)
                    exit_px = high_px if high_px > 0 else entry_px
                    side_norm = (side_str or "long").lower()
                    if side_norm == "short":
                        pnl = (entry_px - exit_px) * qty
                    else:
                        pnl = (exit_px - entry_px) * qty
                    close_rows.append(
                        (
                            pos_id,
                            code,
                            name,
                            self._db_datetime(entry_time),
                            entry_px,
                            qty,
                            strategy,
                            execution_venue or "KRX",
                            float(stop_price or 0.0),
                            high_px or entry_px,
                            state_str or "survival",
                            0,
                            self._db_datetime(closed_at),
                            exit_px,
                            exit_reason,
                            pnl,
                            side_norm,
                            float(fee_rate_val or self.config.default_fee_rate),
                        )
                    )

                open_rows = [
                    (
                        position.id,
                        position.code,
                        position.name,
                        self._db_datetime(position.entry_time),
                        position.entry_price,
                        position.quantity,
                        position.strategy,
                        position.execution_venue,
                        position.stop_price,
                        position.highest_price,
                        position.state.value,
                        1,
                        None,
                        None,
                        None,
                        None,
                        position.side.value,
                        position.fee_rate,
                    )
                    for position in current_positions
                ]

                if close_rows:
                    client.execute(
                        f"INSERT INTO {database}.swing_positions "
                        f"{self._SWING_INSERT_COLS} VALUES",
                        close_rows,
                    )
                if open_rows:
                    client.execute(
                        f"INSERT INTO {database}.swing_positions "
                        f"{self._SWING_INSERT_COLS} VALUES",
                        open_rows,
                    )
                return {
                    "open_saved": len(open_rows),
                    "closed_orphans": len(close_rows),
                }

            result = await asyncio.to_thread(_sync_reconcile)
            logger.info(
                "Reconciled legacy open positions: open_saved=%d, closed_orphans=%d",
                result["open_saved"],
                result["closed_orphans"],
            )
            return result

        except InfrastructureError as e:
            logger.error("Failed to reconcile legacy swing positions: %s", e)
            return {"open_saved": 0, "closed_orphans": 0}

    async def save_closed_to_db(self, position: Position) -> bool:
        """Persist a closed position snapshot to the configured runtime ledger.

        This method uses a batching strategy to optimize database performance by
        accumulating closed positions and flushing them in bulk. Individual row
        inserts create excessive write amplification in external stores.

        Batching Behavior:
            - Positions are accumulated in an in-memory buffer (_pending_swing_positions)
            - Not immediately written to the database
            - Batched inserts reduce external store write amplification

        Flush Triggers (positions are written to DB when):
            1. Batch size threshold reached (config.batch_size, default 50)
            2. Timer-based auto-flush (every config.flush_interval_seconds, default 5s)
            3. Manual flush via flush_pending_positions()
            4. Graceful shutdown via stop_auto_flush()

        For critical scenarios requiring immediate persistence (e.g., testing),
        call flush_pending_positions() immediately after this method.

        Args:
            position: Closed position with exit_price/exit_time set.

        Returns:
            True if accumulated successfully, False if position validation fails
            or accumulation errors occur.

        Example:
            ```python
            # Normal usage - automatic batching
            await tracker.save_closed_to_db(position)

            # Force immediate flush (e.g., for testing or critical trades)
            await tracker.save_closed_to_db(position)
            await tracker.flush_pending_positions()
            ```
        """
        if not position.exit_price or not position.exit_time:
            return False

        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is None:
                return False
            if self._closed_hold_seconds(position) is None:
                return False
            try:
                await asyncio.to_thread(
                    ledger.record_position_snapshot,
                    self._position_snapshot_payload(position, is_open=False),
                )
                logger.info(
                    "Saved closed position snapshot to runtime ledger: %s (id=%s)",
                    position.code,
                    position.id[:8],
                )
                return True
            except RuntimeLedgerError as e:
                logger.error(
                    "Failed to save closed position %s to runtime ledger: %s",
                    position.id[:8],
                    e,
                )
                return False

        try:
            if self._closed_hold_seconds(position) is None:
                return False
            pnl = self._calc_realized_pnl(position)

            row = (
                position.id,
                position.code,
                position.name,
                self._db_datetime(position.entry_time),
                position.entry_price,
                position.quantity,
                position.strategy,
                position.execution_venue,
                position.stop_price,
                position.highest_price,
                position.state.value,
                0,  # is_open = closed
                self._db_datetime(position.exit_time),
                position.exit_price,
                position.exit_reason,
                pnl,
                position.side.value,
                position.fee_rate,
            )

            async with self._batch_lock:
                self._pending_swing_positions.append(row)
                batch_size = len(self._pending_swing_positions)

            logger.info(
                f"Accumulated closed position: {position.code} "
                f"(pnl={pnl:+,.0f}, id={position.id[:8]}, batch={batch_size}/{self.config.batch_size})"
            )

            # Flush if batch threshold reached
            if batch_size >= self.config.batch_size:
                await self._flush_swing_positions_batch()

            return True

        except (ValidationError, InfrastructureError) as e:
            logger.error(f"Failed to accumulate closed position {position.id[:8]}: {e}")
            return False

    async def save_futures_trade_to_db(
        self, position: Position, asset_class: str
    ) -> bool:
        """Persist a closed futures trade to the configured runtime ledger.

        This method uses a batching strategy to optimize database performance by
        accumulating closed futures trades and flushing them in bulk. During backtesting
        with Optuna, hundreds of positions may close per trial, making batching
        critical to avoid overwhelming external stores with individual inserts.

        Batching Behavior:
            - Trades are accumulated in an in-memory buffer (_pending_futures_trades)
            - Not immediately written to the database
            - Batched inserts reduce external store write amplification

        Flush Triggers (trades are written to DB when):
            1. Batch size threshold reached (config.batch_size, default 50)
            2. Timer-based auto-flush (every config.flush_interval_seconds, default 5s)
            3. Manual flush via flush_pending_positions()
            4. Graceful shutdown via stop_auto_flush()

        For critical scenarios requiring immediate persistence (e.g., testing),
        call flush_pending_positions() immediately after this method.

        Args:
            position: Closed position with exit_price/exit_time set.
            asset_class: Asset class of the trade (e.g., 'futures', 'stock')

        Returns:
            True if accumulated successfully, False if position validation fails
            or accumulation errors occur.

        Example:
            ```python
            # Normal usage - automatic batching
            await tracker.save_futures_trade_to_db(position, "futures")

            # Force immediate flush (e.g., for testing or critical trades)
            await tracker.save_futures_trade_to_db(position, "futures")
            await tracker.flush_pending_positions()
            ```
        """
        if not position.exit_price or not position.exit_time:
            return False

        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is None:
                return False
            if self._closed_hold_seconds(position) is None:
                return False
            try:
                await asyncio.to_thread(
                    ledger.record_trade,
                    self._trade_payload(
                        position,
                        asset_class=str(asset_class or "unknown"),
                    ),
                )
                logger.info(
                    "Saved futures trade to runtime ledger: %s (id=%s)",
                    position.code,
                    position.id[:8],
                )
                return True
            except RuntimeLedgerError as e:
                logger.error(
                    "Failed to save futures trade %s to runtime ledger: %s",
                    position.id[:8],
                    e,
                )
                return False

        try:
            pnl = self._calc_realized_pnl(position)
            hold_seconds = self._closed_hold_seconds(position)
            if hold_seconds is None:
                return False

            metadata = position.metadata if isinstance(position.metadata, dict) else {}
            metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)

            entry_notional = max(position.entry_price * position.quantity, 1e-9)
            pnl_pct = (pnl / entry_notional) * 100.0

            row = (
                position.id,
                str(asset_class or "unknown"),
                position.code,
                position.name,
                position.side.value,
                position.strategy,
                position.execution_venue,
                self._db_datetime(position.entry_time),
                position.entry_price,
                self._db_datetime(position.exit_time),
                position.exit_price,
                position.quantity,
                pnl,
                pnl_pct,
                hold_seconds,
                position.exit_reason or "",
                metadata_json,
            )

            async with self._batch_lock:
                self._pending_futures_trades.append(row)
                batch_size = len(self._pending_futures_trades)

            logger.info(
                f"Accumulated futures trade: {position.code} "
                f"(strategy={position.strategy}, pnl={pnl:+,.0f}, id={position.id[:8]}, batch={batch_size}/{self.config.batch_size})"
            )

            # Flush if batch threshold reached
            if batch_size >= self.config.batch_size:
                await self._flush_futures_trades_batch()

            return True

        except (ValidationError, InfrastructureError) as e:
            logger.error(f"Failed to accumulate futures trade {position.id[:8]}: {e}")
            return False

    async def save_stock_trade_to_db(self, position: Position) -> bool:
        """Persist a closed stock trade to the configured runtime ledger.

        This method is the stock-specific counterpart to
        save_futures_trade_to_db and uses the same batching strategy to optimise
        database performance.

        Batching Behavior:
            - Trades are accumulated in an in-memory buffer (_pending_stock_trades)
            - Not immediately written to the database
            - Batched inserts reduce external store overhead

        Flush Triggers (trades are written to DB when):
            1. Batch size threshold reached (config.batch_size, default 50)
            2. Timer-based auto-flush (every config.flush_interval_seconds, default 5s)
            3. Manual flush via flush_pending_positions()
            4. Graceful shutdown via stop_auto_flush()

        Args:
            position: Closed position with exit_price/exit_time set.

        Returns:
            True if accumulated successfully, False if guard conditions prevent
            accumulation (wrong asset_class, missing exit data, or errors).
        """
        if self.config.asset_class != "stock":
            logger.warning(
                f"save_stock_trade_to_db called on non-stock tracker "
                f"(asset_class={self.config.asset_class!r}); ignoring"
            )
            return False

        if not position.exit_price or not position.exit_time:
            logger.warning(
                f"save_stock_trade_to_db: position {position.id[:8]} has no exit data; skipping"
            )
            return False

        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is None:
                return False
            if self._closed_hold_seconds(position) is None:
                return False
            try:
                await asyncio.to_thread(
                    ledger.record_trade,
                    self._trade_payload(position, asset_class="stock"),
                )
                logger.info(
                    "Saved stock trade to runtime ledger: %s (id=%s)",
                    position.code,
                    position.id[:8],
                )
                return True
            except RuntimeLedgerError as e:
                logger.error(
                    "Failed to save stock trade %s to runtime ledger: %s",
                    position.id[:8],
                    e,
                )
                return False

        try:
            pnl = self._calc_realized_pnl(position)
            hold_seconds = self._closed_hold_seconds(position)
            if hold_seconds is None:
                return False

            entry_price = position.entry_price
            quantity = position.quantity
            pnl_pct = (pnl / max(entry_price * quantity, 1e-9)) * 100.0

            metadata = position.metadata if isinstance(position.metadata, dict) else {}
            commission = float(metadata.get("commission", 0.0))
            slippage = float(metadata.get("slippage", 0.0))
            metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)

            exit_state = ""
            if position.state is not None:
                exit_state = (
                    position.state.value
                    if hasattr(position.state, "value")
                    else str(position.state)
                )

            row = (
                position.id,
                position.code,
                position.name,
                position.side.value,
                position.strategy,
                position.execution_venue,
                self._db_datetime(position.entry_time),
                entry_price,
                self._db_datetime(position.exit_time),
                position.exit_price,
                quantity,
                pnl,
                pnl_pct,
                commission,
                slippage,
                hold_seconds,
                position.exit_reason or "",
                exit_state,
                metadata_json,
            )

            async with self._batch_lock:
                self._pending_stock_trades.append(row)
                batch_size = len(self._pending_stock_trades)

            logger.info(
                f"Accumulated stock trade: {position.code} "
                f"(strategy={position.strategy}, pnl={pnl:+,.0f}, id={position.id[:8]}, batch={batch_size}/{self.config.batch_size})"
            )

            # Flush if batch threshold reached
            if batch_size >= self.config.batch_size:
                await self._flush_stock_trades_batch()

            return True

        except (ValidationError, InfrastructureError) as e:
            logger.error(f"Failed to accumulate stock trade {position.id[:8]}: {e}")
            return False

    async def _flush_batch(
        self,
        pending_list: list[tuple[Any, ...]],
        table_name: str,
        insert_cols: str,
        label: str,
        pre_execute_sql: str | None = None,
    ) -> tuple[int, list[tuple[Any, ...]]]:
        """Generic batch flush: copy+clear under lock, then I/O outside lock.

        On failure the rows are re-enqueued so no data is lost.

        Args:
            pending_list: The accumulator list (e.g. _pending_swing_positions).
            table_name: Target legacy table (without database prefix).
            insert_cols: Column spec string for the INSERT statement.
            label: Human-readable label for log messages.
            pre_execute_sql: Optional SQL to run before the INSERT (e.g. schema ensure).

        Returns:
            Tuple of (rows_flushed, remaining_pending_list). The caller must
            reassign the pending list reference if rows were re-enqueued.
        """
        # Acquire lock only to snapshot + clear the buffer
        async with self._batch_lock:
            if not pending_list:
                return 0, pending_list
            rows = pending_list.copy()
            pending_list.clear()

        # Perform blocking I/O *outside* the lock
        try:
            ch, database = self._get_db_client()

            def _sync_flush():
                client = ch.get_sync_client()
                if pre_execute_sql:
                    client.execute(pre_execute_sql.format(database=database))
                client.execute(
                    f"INSERT INTO {database}.{table_name} {insert_cols} VALUES",
                    rows,
                )

            await asyncio.to_thread(_sync_flush)
            logger.info(f"Flushed {len(rows)} {label} batch to DB")

            # Observability: record successful legacy archive insert.
            if self._ch_fail_tracker is not None:
                self._ch_fail_tracker.record_success()

            return len(rows), pending_list

        except Exception as e:
            # Catch BOTH InfrastructureError (wrapped CH errors) AND raw
            # upstream driver exceptions (server, network, timeout, etc.)
            # so the kill_switch fail-rate metric
            # reflects every failure mode, not just the wrapped subset.
            # Re-enqueue rows so they are retried on the next flush.
            async with self._batch_lock:
                pending_list.extend(rows)

            # Distinguish wrapped vs raw for log clarity (InfrastructureError
            # is the project's normalised exception; raw driver errors are upstream).
            if isinstance(e, InfrastructureError):
                logger.error(f"Failed to flush {label} batch: {e}")
            else:
                logger.error(
                    f"Failed to flush {label} batch (raw {type(e).__name__}): {e}",
                    exc_info=True,
                )

            # Observability: record failed legacy archive insert.
            if self._ch_fail_tracker is not None:
                self._ch_fail_tracker.record_failure()

            return 0, pending_list

    async def _flush_swing_positions_batch(self) -> int:
        """Flush accumulated swing positions batch to the legacy archive.

        Returns:
            Number of positions flushed
        """
        count, self._pending_swing_positions = await self._flush_batch(
            self._pending_swing_positions,
            table_name="swing_positions",
            insert_cols=self._SWING_INSERT_COLS,
            label="swing positions",
        )
        return count

    async def _flush_futures_trades_batch(self) -> int:
        """Flush accumulated futures trades batch to the legacy archive.

        Returns:
            Number of trades flushed
        """
        count, self._pending_futures_trades = await self._flush_batch(
            self._pending_futures_trades,
            table_name="rl_trades",
            insert_cols=self._FUTURES_TRADE_INSERT_COLS,
            label="futures trades",
            pre_execute_sql=self._FUTURES_TRADES_SCHEMA_TEMPLATE,
        )
        return count

    async def _flush_stock_trades_batch(self) -> int:
        """Flush accumulated stock trades batch to the legacy archive.

        Returns:
            Number of trades flushed
        """
        count, self._pending_stock_trades = await self._flush_batch(
            self._pending_stock_trades,
            table_name="stock_trades",
            insert_cols=self._STOCK_TRADE_INSERT_COLS,
            label="stock trades",
        )
        return count

    async def flush_pending_positions(self) -> tuple[int, int]:
        """Flush all pending batches to database.

        This method is safe to call even if batches are empty.
        Typically called during graceful shutdown or manual flush triggers.

        Returns:
            Tuple of (swing_positions_flushed, futures_trades_flushed)
        """
        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is not None:
                await asyncio.to_thread(ledger.flush)
            return 0, 0

        swing_count = await self._flush_swing_positions_batch()
        futures_count = await self._flush_futures_trades_batch()
        stock_count = await self._flush_stock_trades_batch()

        if swing_count > 0 or futures_count > 0 or stock_count > 0:
            logger.info(
                f"Manual flush completed: {swing_count} swing positions, "
                f"{futures_count} futures trades, {stock_count} stock trades"
            )

        return swing_count, futures_count

    def _start_auto_flush_task(self) -> None:
        """Start background timer-based flush task.

        Creates an asyncio task that periodically flushes pending positions
        based on the configured flush_interval_seconds. The task runs
        indefinitely with robust error handling.

        The task is only started if flush_interval_seconds > 0 and a running
        event loop is available. In sync contexts (tests, CLI), the task
        creation is deferred — callers can invoke this again once an event
        loop is running.
        """
        if self.config.flush_interval_seconds <= 0:
            logger.debug("Auto-flush disabled (flush_interval_seconds <= 0)")
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("No running event loop; auto-flush task deferred")
            return

        async def _auto_flush_loop():
            """Background task that periodically flushes pending positions."""
            logger.info(
                f"Auto-flush task started (interval={self.config.flush_interval_seconds}s)"
            )
            while True:
                try:
                    await asyncio.sleep(self.config.flush_interval_seconds)
                    swing_count, futures_count = await self.flush_pending_positions()

                    # Only log if we actually flushed something
                    if swing_count > 0 or futures_count > 0:
                        logger.info(
                            f"Auto-flush triggered: {swing_count} swing positions, "
                            f"{futures_count} futures trades"
                        )
                except asyncio.CancelledError:
                    logger.info("Auto-flush task cancelled")
                    break
                except TradingSystemError as e:
                    logger.error(f"Error in auto-flush task: {e}", exc_info=True)
                    # Continue loop despite errors for robustness
                    await asyncio.sleep(1)  # Brief delay before retry

        # Create and store the task
        self._auto_flush_task = loop.create_task(_auto_flush_loop())
        logger.info("Auto-flush task created")

    async def stop_auto_flush(self) -> None:
        """Stop the auto-flush background task and flush remaining positions.

        Gracefully cancels the auto-flush task if it's running, waits for it
        to complete, then performs one final flush to ensure all pending
        positions are written to the database.

        This method is safe to call multiple times or if the task was never started.
        """
        if self._auto_flush_task is not None and not self._auto_flush_task.done():
            logger.info("Stopping auto-flush task...")
            self._auto_flush_task.cancel()

            try:
                await self._auto_flush_task
            except asyncio.CancelledError:
                logger.debug("Auto-flush task cancelled successfully")
            except TradingSystemError as e:
                logger.warning(f"Error while stopping auto-flush task: {e}")

        # Final flush to ensure all pending positions are written
        # flush_pending_positions also flushes _pending_stock_trades via _flush_stock_trades_batch
        swing_count, futures_count = await self.flush_pending_positions()
        if swing_count > 0 or futures_count > 0:
            logger.info(
                f"Final flush on shutdown: {swing_count} swing positions, "
                f"{futures_count} futures trades"
            )

    @staticmethod
    def _calc_realized_pnl(position: Position) -> float:
        """Calculate side-aware realized PnL for a closed position."""
        if not position.exit_price:
            return 0.0
        if position.side == PositionSide.LONG:
            return (position.exit_price - position.entry_price) * position.quantity
        return (position.entry_price - position.exit_price) * position.quantity

    async def load_from_db(self) -> int:
        """Load open positions from the configured runtime ledger on startup.

        Returns:
            Number of positions loaded
        """
        if not self._uses_legacy_persistence():
            ledger = self._get_runtime_ledger()
            if ledger is None:
                return 0
            try:
                asset_class = self.config.asset_class or None
                rows = await asyncio.to_thread(ledger.load_open_positions, asset_class)
                loaded = 0
                for row in rows:
                    position = self._position_from_ledger_row(row)
                    if position is None:
                        continue
                    if position.id in self._positions:
                        continue
                    if self.add_recovered_position(position):
                        loaded += 1

                if loaded:
                    logger.info("Loaded %d positions from runtime ledger", loaded)
                return loaded
            except RuntimeLedgerError as e:
                logger.error("Failed to load positions from runtime ledger: %s", e)
                return 0

        try:
            ch, database = self._get_db_client()

            def _sync_load():
                client = ch.get_sync_client()
                return client.execute(f"""
                    SELECT id, code, name, entry_date, entry_price, quantity,
                           strategy, execution_venue, stop_loss_price, high_since_entry, current_state,
                           side, fee_rate
                    FROM {database}.swing_positions FINAL
                    WHERE is_open = 1
                    ORDER BY entry_date ASC
                    """)

            result = await asyncio.to_thread(_sync_load)

            loaded = 0
            for row in result:
                if len(row) == 13:
                    (
                        pos_id,
                        code,
                        name,
                        entry_time,
                        entry_price,
                        quantity,
                        strategy,
                        execution_venue,
                        stop_price,
                        high_since_entry,
                        state_str,
                        side_str,
                        fee_rate_val,
                    ) = row
                elif len(row) == 12:
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
                    execution_venue = "KRX"
                else:
                    logger.warning(
                        "Skipping persisted position with unexpected column count: %s",
                        len(row),
                    )
                    continue

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
                    fee_rate=(
                        fee_rate_val if fee_rate_val else self.config.default_fee_rate
                    ),
                    execution_venue=execution_venue if execution_venue else "KRX",
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

        except InfrastructureError as e:
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
