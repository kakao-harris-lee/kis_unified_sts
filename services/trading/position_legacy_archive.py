from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.exceptions import InfrastructureError, ValidationError
from shared.models.position import Position
from shared.storage.runtime_ledger import RuntimeLedgerError

logger = logging.getLogger("services.trading.position_tracker")


class PositionLegacyArchiveMixin:
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
