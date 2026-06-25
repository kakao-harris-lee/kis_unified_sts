"""Broker/ledger position verification for the trading orchestrator."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import yaml

from shared.config.loader import ConfigLoader
from shared.exceptions import (
    APIError,
    InfrastructureError,
    InvalidConfigError,
    MissingConfigError,
    NetworkError,
    ValidationError,
)
from shared.models.position import Position, PositionSide

logger = logging.getLogger("services.trading.orchestrator")

NotifyCallback = Callable[[str], Awaitable[None]]


class BrokerPositionVerifier:
    """Compare recovered tracker positions against broker balances."""

    async def verify(
        self,
        *,
        config: Any,
        kis_client: Any | None,
        position_tracker: Any,
        notify: NotifyCallback | None = None,
    ) -> None:
        """Redis 복구 포지션과 브로커 실제 잔고 비교.

        기본적으로 실행하되, futures paper 모드에서는 건너뛴다.
        (선물 paper는 VirtualBroker 상태가 기준이며 브로커 잔고조회 노이즈 방지)
        """
        # Load broker_verification config
        try:
            exec_cfg = ConfigLoader.load("execution.yaml")
            bv_cfg = exec_cfg.get("broker_verification", {})
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
        ):
            bv_cfg = {}

        if not bv_cfg.get("enabled", True):
            return

        if not kis_client:
            logger.debug("KIS client not available; skipping broker verification")
            return

        # Futures paper trading uses VirtualBroker state as source-of-truth.
        # Skip broker inquiry to avoid account-mapping noise and startup latency.
        if config.asset_class == "futures" and config.paper_trading:
            logger.info("Futures paper mode: skipping broker verification")
            return

        # Futures mock server doesn't support balance inquiry
        if config.asset_class == "futures" and not kis_client.config.is_real:
            logger.debug("Futures mock server: skipping broker verification")
            return

        try:
            if config.asset_class == "stock":
                broker_positions = await kis_client.get_stock_balance()
            else:
                broker_positions = await kis_client.get_futures_balance()
        except (APIError, NetworkError) as e:
            logger.warning(f"Broker balance inquiry failed: {e}")
            return

        if not broker_positions and not position_tracker.positions:
            logger.info("Broker verification: no positions on either side")
            return

        redis_by_code: dict[str, Position] = {}
        for pos in position_tracker.positions:
            redis_by_code[pos.code] = pos

        broker_by_code: dict[str, dict] = {}
        for bp in broker_positions:
            broker_by_code[bp["code"]] = bp

        redis_codes = set(redis_by_code)
        broker_codes = set(broker_by_code)
        matched = redis_codes & broker_codes
        redis_only = redis_codes - broker_codes
        broker_only = broker_codes - redis_codes

        reconcile_qty = bv_cfg.get("reconcile_quantity", True)
        reconcile_price = bv_cfg.get("reconcile_price", True)
        remove_redis_only = bv_cfg.get("remove_redis_only", False)
        sync_runtime_ledger = bv_cfg.get("sync_runtime_ledger", False)
        notify_on_mismatch = bv_cfg.get("notify_on_mismatch", True)
        auto_track = bv_cfg.get("auto_track_external", False)
        alerts: list[str] = []

        # In PAPER mode the broker (KIS mock) account is NOT the source of
        # truth — the VirtualBroker holds the authoritative paper positions and
        # the mock-mirror is fire-and-forget (and frequently fails). Treating
        # the mock balance as authoritative caused real paper positions to be
        # destroyed at break-even (remove_redis_only) and stray mock holdings to
        # be ingested as `external` paper positions (auto_track_external), both
        # churning P&L to zero. We therefore disable the destructive and
        # broker-overriding branches for paper trackers and keep verification
        # observe-only (still log/alert mismatches).
        if getattr(config, "paper_trading", False):
            if remove_redis_only or auto_track or reconcile_qty or reconcile_price:
                logger.info(
                    "Paper mode: broker is not authoritative for paper positions; "
                    "running broker verification in observe-only mode "
                    "(remove_redis_only/auto_track/reconcile disabled)"
                )
            remove_redis_only = False
            auto_track = False
            reconcile_qty = False
            reconcile_price = False

        # 1. Matched — verify quantity and side
        for code in matched:
            rp = redis_by_code[code]
            bp = broker_by_code[code]
            broker_side = PositionSide(bp["side"])

            if rp.side != broker_side:
                msg = (
                    f"[{code}] SIDE MISMATCH: Redis={rp.side.value}, "
                    f"Broker={broker_side.value}"
                )
                logger.error(msg)
                alerts.append(msg)

            if rp.quantity != bp["quantity"]:
                msg = (
                    f"[{code}] Quantity mismatch: "
                    f"Redis={rp.quantity}, Broker={bp['quantity']}"
                )
                logger.warning(msg)
                if reconcile_qty:
                    rp.quantity = bp["quantity"]
                    logger.info(
                        f"[{code}] Quantity reconciled to broker value: {bp['quantity']}"
                    )
                else:
                    alerts.append(msg)

            broker_avg_price = float(bp.get("avg_price") or 0.0)
            if broker_avg_price > 0 and abs(rp.entry_price - broker_avg_price) > 1e-6:
                msg = (
                    f"[{code}] Avg price mismatch: "
                    f"Redis={rp.entry_price:,.2f}, Broker={broker_avg_price:,.2f}"
                )
                logger.warning(msg)
                if reconcile_price:
                    rp.entry_price = broker_avg_price
                    logger.info(
                        f"[{code}] Entry price reconciled to broker value: {broker_avg_price:,.2f}"
                    )
                else:
                    alerts.append(msg)

            broker_current_price = float(bp.get("current_price") or 0.0)
            if broker_current_price > 0:
                rp.update_price(broker_current_price)

        # 2. Redis-only — position may have been closed externally
        for code in redis_only:
            rp = redis_by_code[code]
            msg = (
                f"[{code}] Redis-only position (not in broker). "
                f"qty={rp.quantity}, entry={rp.entry_price:,.0f}"
            )
            logger.warning(msg)
            if remove_redis_only:
                removed = position_tracker.remove_position(
                    rp.id,
                    reason="broker_absent",
                )
                if removed is not None:
                    logger.info(f"[{code}] Removed Redis-only position from tracker")
            else:
                alerts.append(msg)

        # 3. Broker-only — external position not tracked by system
        for code in broker_only:
            bp = broker_by_code[code]
            msg = (
                f"[{code}] Broker-only position (not in Redis). "
                f"qty={bp['quantity']}, avg_price={bp['avg_price']:,.0f}"
            )
            logger.warning(msg)
            if auto_track:
                try:
                    side = PositionSide(bp["side"])
                    broker_avg_price = float(bp["avg_price"])
                    broker_current_price = float(
                        bp.get("current_price") or broker_avg_price
                    )
                    new_pos = Position(
                        id=f"broker_{config.asset_class}_{code}_{side.value}",
                        code=code,
                        name=bp.get("name", ""),
                        side=side,
                        quantity=bp["quantity"],
                        entry_price=broker_avg_price,
                        current_price=broker_current_price,
                        highest_price=max(broker_avg_price, broker_current_price),
                        lowest_price=min(broker_avg_price, broker_current_price),
                        strategy="external",
                        metadata={
                            "source": "broker_verification",
                            "broker_reconciled_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    if position_tracker.add_recovered_position(new_pos):
                        logger.info(f"[{code}] Auto-tracked broker position")
                        if code not in (config.symbols or []):
                            if config.symbols is None:
                                config.symbols = []
                            config.symbols.append(code)
                except (
                    ValidationError,
                    InfrastructureError,
                    ValueError,
                    KeyError,
                ) as e:
                    logger.warning(f"[{code}] Failed to auto-track: {e}")
            else:
                alerts.append(msg)

        # Summary
        total = len(matched) + len(redis_only) + len(broker_only)
        if total > 0:
            logger.info(
                f"Broker verification: {len(matched)} matched, "
                f"{len(redis_only)} Redis-only, {len(broker_only)} broker-only"
            )

        if (
            sync_runtime_ledger
            and config.asset_class == "stock"
            and position_tracker is not None
        ):
            await position_tracker.reconcile_open_positions_to_db()

        # Telegram alert for mismatches
        if alerts and notify_on_mismatch and notify is not None:
            alert_text = (
                f"⚠️ Broker Position Verification ({config.asset_class})\n\n"
                + "\n".join(alerts)
            )
            await notify(alert_text)
