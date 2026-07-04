from __future__ import annotations

import asyncio
import logging

from shared.exceptions import TradingSystemError

logger = logging.getLogger("services.trading.position_tracker")


class PositionAutoFlushMixin:
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

                    # Mirror currently-open positions to the durable runtime
                    # ledger so they survive a Redis loss / container recreate.
                    # Idempotent UPSERT keyed by position id => the
                    # position_snapshots table always reflects the live set of
                    # open positions without duplicate-row spam.
                    snapshot_count = 0
                    if self.config.snapshot_open_positions:
                        snapshot_count = await self.save_to_db()

                    # Only log if we actually flushed/mirrored something
                    if swing_count > 0 or futures_count > 0 or snapshot_count > 0:
                        logger.info(
                            f"Auto-flush triggered: {swing_count} swing positions, "
                            f"{futures_count} futures trades, "
                            f"{snapshot_count} open snapshots"
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
