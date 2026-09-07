from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from shared.models.position import Position
from shared.storage.runtime_ledger import RuntimeLedgerError

logger = logging.getLogger("services.trading.position_tracker")


class PositionLegacyArchiveMixin:
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

    async def reconcile_open_positions_to_db(self) -> dict[str, int]:
        """Synchronize the runtime ledger's open-position rows with current
        active positions by re-saving every currently tracked open position.
        """
        open_saved = await self.save_to_db()
        logger.info(
            "Reconciled runtime ledger open positions: open_saved=%d",
            open_saved,
        )
        return {"open_saved": open_saved, "closed_orphans": 0}

    async def save_closed_to_db(self, position: Position) -> bool:
        """Persist a closed position snapshot to the configured runtime ledger.

        Args:
            position: Closed position with exit_price/exit_time set.

        Returns:
            True if the snapshot was recorded, False if the position lacks
            exit data, the ledger is unavailable, or persistence fails.
        """
        if not position.exit_price or not position.exit_time:
            return False

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

    async def save_futures_trade_to_db(
        self, position: Position, asset_class: str
    ) -> bool:
        """Persist a closed futures trade to the configured runtime ledger.

        Args:
            position: Closed position with exit_price/exit_time set.
            asset_class: Asset class of the trade (e.g., 'futures', 'stock')

        Returns:
            True if the trade was recorded, False if the position lacks exit
            data, the ledger is unavailable, or persistence fails.
        """
        if not position.exit_price or not position.exit_time:
            return False

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

    async def save_stock_trade_to_db(self, position: Position) -> bool:
        """Persist a closed stock trade to the configured runtime ledger.

        This method is the stock-specific counterpart to
        save_futures_trade_to_db.

        Args:
            position: Closed position with exit_price/exit_time set.

        Returns:
            True if the trade was recorded, False if guard conditions prevent
            it (wrong asset_class, missing exit data, unavailable ledger, or
            persistence failure).
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

    async def flush_pending_positions(self) -> tuple[int, int]:
        """Flush the runtime ledger's write-behind buffer, if any.

        Safe to call at any time; typically invoked during graceful shutdown.

        Returns:
            Always ``(0, 0)`` — the runtime ledger persists synchronously per
            call, so there is no pending in-memory batch left to report.
        """
        ledger = self._get_runtime_ledger()
        if ledger is not None:
            await asyncio.to_thread(ledger.flush)
        return 0, 0
