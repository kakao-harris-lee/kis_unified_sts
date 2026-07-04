from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from shared.exceptions import InfrastructureError
from shared.models.position import Position, PositionSide, PositionState
from shared.portfolio.config import track_for_asset_class
from shared.storage.config import StorageConfig
from shared.storage.runtime_ledger import RuntimeLedger, RuntimeLedgerError

logger = logging.getLogger("services.trading.position_tracker")


class PositionLedgerPersistenceMixin:
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
        """Build a RuntimeLedger position snapshot payload.

        The ``idempotency_key`` is intentionally stable per position
        (``<asset_class>:<position_id>``) and independent of open/closed
        state. This makes repeated open-position snapshots UPSERT a single
        row (no duplicate-row spam from the periodic auto-flush mirror) and
        lets the closing snapshot supersede the open row *in place* — it
        flips ``is_open`` to 0 on the same row, so ``load_open_positions``
        (which filters ``is_open = 1``) never resurrects a closed position
        on the next restart.
        """
        resolved_asset_class = asset_class or self._position_asset_class()
        open_flag = position.exit_time is None if is_open is None else is_open
        return {
            "id": position.id,
            "position_id": position.id,
            "idempotency_key": f"{resolved_asset_class}:{position.id}",
            "asset_class": resolved_asset_class,
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
            # Portfolio track tag ("B" stock / "C" futures) derived from the
            # asset class — shared.portfolio owns the mapping.
            "track_id": track_for_asset_class(asset_class),
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
