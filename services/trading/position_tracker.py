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
import contextlib
import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from services.trading.position_models import (
    MAX_PRICE,
    MIN_PRICE,
    PositionEvent,
    PositionTrackerConfig,
    default_uuid_generator,
)
from services.trading.position_persistence import PositionPersistenceMixin
from shared.models.position import Position, PositionSide, PositionState
from shared.storage.runtime_ledger import RuntimeLedger
from shared.utils.calc import validate_price

if TYPE_CHECKING:
    from shared.models.signal import Signal

logger = logging.getLogger(__name__)


# Validation constants


class PositionTracker(PositionPersistenceMixin):
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
            with contextlib.suppress(ValueError):
                self._by_symbol[position.code].remove(position_id)
            if not self._by_symbol[position.code]:
                del self._by_symbol[position.code]

        if position.strategy in self._by_strategy:
            with contextlib.suppress(ValueError):
                self._by_strategy[position.strategy].remove(position_id)
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
