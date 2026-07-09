"""Order-router consumer-group daemon.

Phase 4 Task 12 — reads filtered :class:`Signal`s from
``signal.final.futures`` (live) / ``signal.final.futures.shadow`` (paper),
places passive limit entries via :class:`PassiveMaker`, and on fill registers
a stop+target bracket via :class:`PseudoOCO`. Fills are logged through
:class:`FillLogger` to ``order.fill.futures`` / ``order.fill.futures.shadow``.

This is the only daemon that holds wallet authority — every other Phase 4
component reads/audits, but the order_router places real orders. The
kill_switch daemon (Task 13) writes a sentinel file on trigger; we honor
it by:

  1. **On startup**: refusing to enter the consume loop when the sentinel
     already exists — the previous trip has not been operator-cleared yet.
  2. **Per loop iteration**: re-checking the sentinel before each
     ``xreadgroup`` so a mid-session trip drains pre-trip messages without
     placing further orders.

Operator clears the sentinel via ``scripts/kill_switch_clear.sh`` before
the next start.

Error taxonomy:
- Parse error                   → XACK (poison-pill drop)
- PassiveMaker raises           → NO XACK (retry — beware of double-fill;
                                  see PR #134 review note on idempotency)
- PseudoOCO.register_bracket    → NO XACK (entry filled but bracket not
                                  registered → caller must reconcile)

Telegram interactive-alerts (design doc
docs/plans/2026-07-07-telegram-interactive-alerts-design.md) adds an
``intent=close`` branch: the telegram_bot XADDs a close request onto the
same ``signal.final.futures[.shadow]`` stream (bot never calls the broker
directly — wallet authority stays here). The branch reads the held position
from ``futures:monitor:positions`` (owned by ``services/futures_monitor``)
to determine the flattening side/quantity, bypasses the entry-only guards
(position_size_cap, daily_trade_cap — closing reduces risk), keeps the
live_mode_guard + symbol_lock checks (a live close is still a live order),
and places a real market order via the same ``close_executor`` the
PseudoOCO exit-monitor uses for live brackets (``LiveExitExecutor`` in
live mode; ``None`` in paper mode synthesizes the fill instead).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path
from typing import Any

from services.futures_monitor.positions import parse_futures_position_record
from services.risk_filter.main import _signal_from_stream_fields
from shared.config.runtime_defaults import redis_url_from_env
from shared.execution.contract_spec import ContractSpec
from shared.execution.live_mode_guard import LiveModeGuard
from shared.execution.passive_maker import PassiveMaker
from shared.execution.pseudo_oco import PseudoOCO
from shared.execution.tick_math import _compute_slippage_ticks
from shared.streaming.stage import StreamStage

# Same env-var contract as services/futures_monitor/main.py — both daemons must
# agree on where the held-position hash lives. No shared constant module
# exists for this key (unlike shared/streaming/stock_keys.py for stock), so
# the default + env-override pair is intentionally duplicated here rather than
# introducing a new shared module out of this change's scope.
_FUTURES_POSITIONS_KEY_ENV = "FUTURES_MONITOR_POSITIONS_KEY"
_DEFAULT_FUTURES_POSITIONS_KEY = "futures:monitor:positions"


def _futures_positions_key() -> str:
    """Return the futures_monitor positions-hash key (env-overridable)."""
    return os.environ.get(_FUTURES_POSITIONS_KEY_ENV, _DEFAULT_FUTURES_POSITIONS_KEY)


logger = logging.getLogger(__name__)

# Phase 5 Gate-3 daily-trade counter lives in Redis under
# `order_router:daily_trades:YYYY-MM-DD` (KST date). Expires at the next
# KST midnight via TTL — restart-safe, multi-worker-safe (INCR is atomic).
_DAILY_TRADE_KEY_PREFIX = "order_router:daily_trades:"
_KST = timezone(timedelta(hours=9))


def _kst_date_key(now: datetime | None = None) -> str:
    """KST-date suffix for the daily-trade counter (e.g. ``2026-05-01``).

    The Phase 5 plan §2.3 daily-trade cap is "per trading day" by Korean
    convention. Using the KST date prevents 09:00–15:30 sessions from
    being split across UTC days.
    """
    ref = now or datetime.now(UTC)
    return ref.astimezone(_KST).date().isoformat()


def _seconds_until_next_kst_midnight(now: datetime | None = None) -> int:
    """TTL for the daily counter — wraps to 0 at next 00:00 KST.

    Caps at 86_400 just in case clock-skew makes the math return >24h.
    Floors at 60 so the counter never expires within the same minute.
    """
    ref = (now or datetime.now(UTC)).astimezone(_KST)
    next_midnight = datetime.combine(
        ref.date() + timedelta(days=1), dt_time.min, tzinfo=_KST
    )
    delta = int((next_midnight - ref).total_seconds())
    return max(60, min(delta, 86_400))


def _resolve_quantity(*, base_quantity: int, size_multiplier: float) -> int:
    """Scale ``base_quantity`` by ``size_multiplier``, floor at 1.

    Risk filter's :class:`ConsecutiveLossFilter` may emit
    ``size_multiplier=0.5`` to halve sizing after a losing streak. With
    ``base_quantity=1`` (current Phase 4 ladder), 0.5 rounds to 0; we floor
    at 1 contract because zero-sized orders are nonsensical and the filter's
    intent is "trade smaller", not "skip the trade" (which would have
    used ``passed=False``).
    """
    scaled = int(round(base_quantity * size_multiplier))
    return max(scaled, 1)


class OrderRouterDaemon(StreamStage):
    def __init__(
        self,
        *,
        redis: Any,
        passive_maker: PassiveMaker,
        pseudo_oco: PseudoOCO,
        contract_spec: ContractSpec,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        passive_timeout_seconds: int,
        base_quantity: int = 1,
        kill_switch_sentinel_path: str | None = None,
        live_mode_guard: LiveModeGuard | None = None,
        locked_symbol: str | None = None,
        futures_price_feed: Any = None,
        exit_poll_interval: float = 1.0,
        close_executor: Any = None,
        futures_positions_key: str | None = None,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=final_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.passive_maker = passive_maker
        self.pseudo_oco = pseudo_oco
        self.contract_spec = contract_spec
        self.passive_timeout_seconds = passive_timeout_seconds
        self.base_quantity = base_quantity
        # intent=close support (telegram interactive-alerts design doc): the
        # same close_executor PseudoOCO uses for live bracket exits
        # (LiveExitExecutor in live mode; None in paper mode synthesizes the
        # fill). Reusing it keeps the "one wallet-authority path" invariant —
        # no new order-placement code path is introduced for closes.
        self.close_executor = close_executor
        self.futures_positions_key = futures_positions_key or _futures_positions_key()
        self.close_count: int = 0
        self.close_blocked_count: int = 0
        self.sentinel_path = (
            Path(kill_switch_sentinel_path) if kill_switch_sentinel_path else None
        )
        self.live_mode_guard = live_mode_guard
        self.locked_symbol = locked_symbol
        self.futures_price_feed = futures_price_feed
        self.exit_poll_interval = exit_poll_interval
        self._exit_task: asyncio.Task[None] | None = None
        self.exits_fired_count: int = 0
        self.refused_due_to_sentinel: bool = False
        self.live_suspended_count: int = 0
        # Phase 5 Gate-3 cap counters (observability + tests)
        self.symbol_lock_blocked_count: int = 0
        self.daily_trade_blocked_count: int = 0
        self.position_size_capped_count: int = 0

    def _sentinel_present(self) -> bool:
        return self.sentinel_path is not None and self.sentinel_path.exists()

    async def on_startup(self) -> None:
        # Startup guard: refuse to consume if the kill switch tripped previously
        # and an operator has not yet run scripts/kill_switch_clear.sh.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel exists at %s — refusing to start. "
                "Run scripts/kill_switch_clear.sh after operator review.",
                self.sentinel_path,
            )
            self._stop.set()  # prevent the consume loop from running any iteration
        if self.futures_price_feed is not None and not self.refused_due_to_sentinel:
            self._exit_task = asyncio.create_task(self._exit_monitor_loop())

    async def on_shutdown(self) -> None:
        if self._exit_task is not None:
            self._exit_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._exit_task
            self._exit_task = None

    async def _exit_monitor_loop(self) -> None:
        """Poll the live feed and drive PseudoOCO stop/target/expiry closes.

        KIS server-side OCO is restricted, so brackets are monitored client-
        side here. Paper closes are synthetic; live closes place real orders
        via the PseudoOCO close_executor. Resilient: a bad iteration is logged
        and retried so the consume loop and feed stay alive.
        """
        symbol = self.locked_symbol
        if symbol is None:
            logger.warning("exit-monitor: no locked_symbol — not polling")
            return
        while not self._stop.is_set():
            try:
                price = await self.futures_price_feed.get_current_price(symbol)
                close = price.get("close") if price else None
                now_ms = int(datetime.now(UTC).timestamp() * 1000)
                if close is not None:
                    fired = await self.pseudo_oco.on_tick(
                        symbol=symbol,
                        price=float(close),
                        now_ms=now_ms,
                    )
                    self.exits_fired_count += len(fired)
                expired = await self.pseudo_oco.check_expiry(
                    now_ms=now_ms,
                    market_price=float(close) if close is not None else None,
                )
                self.exits_fired_count += len(expired)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("exit-monitor iteration failed; continuing")
            try:
                await asyncio.sleep(self.exit_poll_interval)
            except asyncio.CancelledError:
                raise

    async def pre_iteration_gate(self) -> bool:
        # Per-iteration guard: a mid-session trip must drain pre-trip messages
        # without placing further orders.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel appeared at %s during run; exiting.",
                self.sentinel_path,
            )
            return False
        return True

    async def _execute_futures_close(self, fields: dict[bytes, bytes]) -> bool:
        """Handle an ``intent=close`` message by flattening the held position.

        The telegram_bot XADDs ``intent=close`` + ``symbol`` (design doc
        docs/plans/2026-07-07-telegram-interactive-alerts-design.md,
        "Close execution preserves the wallet-authority invariant") — the
        bot never calls the broker directly. Quantity/side are read from
        ``futures:monitor:positions`` (owned by ``services/futures_monitor``)
        rather than trusted from the message, and the closing side is the
        opposite of the held side (preserves long/short symmetry).

        The order is placed via the same ``close_executor`` PseudoOCO uses
        for live bracket exits (``LiveExitExecutor`` in live mode; ``None``
        in paper mode synthesizes the fill instead of calling the paper
        adapter — mirrors :meth:`PseudoOCO._close`, since the paper KIS
        adapter only supports limit orders and would reject a market
        ``price=None`` call). The fill is logged with
        ``trade_role="force_close"`` so ``futures_monitor``'s existing fill
        handler HDELs the position hash and publishes the closed trade —
        this method does not touch that hash directly (DRY: one owner).

        Entry-only guards (position_size_cap, daily_trade_cap) are
        intentionally skipped — closing reduces risk, not adds it.
        ``live_mode_guard.is_live_suspended`` and the symbol lock are still
        enforced: a live close is still a live order, and the symbol lock
        guards against acting on a stale/foreign contract.
        """
        symbol = fields.get(b"symbol", b"").decode("utf-8", errors="replace")
        if not symbol:
            logger.warning("intent=close message missing symbol; dropping")
            return True  # poison-pill: consume

        if (
            self.live_mode_guard is not None
            and await self.live_mode_guard.is_live_suspended(self.redis)
        ):
            self.live_suspended_count += 1
            logger.warning("live_mode suspended; skipping close symbol=%s", symbol)
            return True  # skip (consumed, no retry)

        guard = self.live_mode_guard
        if (
            guard is not None
            and guard.symbol_lock_enabled
            and self.locked_symbol is not None
            and symbol != self.locked_symbol
        ):
            self.symbol_lock_blocked_count += 1
            logger.warning(
                "symbol_lock: close symbol=%s != locked=%s; skipping",
                symbol,
                self.locked_symbol,
            )
            return True  # skip (consumed)

        try:
            raw = await self.redis.hget(self.futures_positions_key, symbol)
        except Exception:
            logger.exception(
                "close: positions hash read failed symbol=%s; leaving pending", symbol
            )
            return False  # leave pending (no XACK) — transient Redis issue

        record = parse_futures_position_record(raw) if raw is not None else None
        if record is None:
            logger.warning(
                "close: no open position for symbol=%s; nothing to close", symbol
            )
            self.close_blocked_count += 1
            return True  # final state: nothing to flatten, consumed

        held_side = str(record.get("side", "long"))
        quantity = int(record.get("quantity", 0) or 0)
        entry_price = float(record.get("entry_price", 0.0) or 0.0)
        signal_id = str(record.get("signal_id", "")) or f"close-{symbol}"
        if quantity <= 0:
            logger.warning(
                "close: recorded quantity<=0 for symbol=%s; nothing to close", symbol
            )
            return True

        closing_side = "short" if held_side == "long" else "long"
        now_ms = int(datetime.now(UTC).timestamp() * 1000)

        reference_price = entry_price
        if self.futures_price_feed is not None:
            try:
                price = await self.futures_price_feed.get_current_price(symbol)
                close = price.get("close") if price else None
                if close is not None:
                    reference_price = float(close)
            except Exception:
                logger.warning(
                    "close: price feed lookup failed symbol=%s; using entry_price",
                    symbol,
                    exc_info=True,
                )

        if self.close_executor is not None:
            fill = await self.close_executor.flatten(
                symbol=symbol,
                side=closing_side,
                quantity=quantity,
                requested_price=reference_price,
                now_ms=now_ms,
            )
            if fill is None:
                logger.warning(
                    "close: live exit not placed symbol=%s qty=%d; will retry",
                    symbol,
                    quantity,
                )
                return False  # leave pending — mirrors PseudoOCO._close's live-blocked path
            filled_price = float(fill.price)
        else:
            # Paper: no close_executor is wired (mirrors the exit-monitor's
            # paper branch) — synthesize the fill at the reference price
            # rather than calling PaperKISFuturesAdapter, which only
            # supports limit orders and would reject price=None.
            filled_price = reference_price

        slippage_ticks = _compute_slippage_ticks(
            requested=reference_price,
            filled=filled_price,
            direction=closing_side,
            tick_size=self.contract_spec.tick_size_points,
        )
        try:
            await self.passive_maker.fill_logger.log_fill(
                signal_id=signal_id,
                order_id=f"close-{symbol}-{now_ms}",
                symbol=symbol,
                side=closing_side,
                order_type="market",
                requested_price=reference_price,
                filled_price=filled_price,
                tick_size_points=self.contract_spec.tick_size_points,
                slippage_ticks=slippage_ticks,
                quantity=quantity,
                requested_at_ms=now_ms,
                filled_at_ms=now_ms,
                venue="KRX",
                trade_role="force_close",
                broker_error_code="intent_close",
            )
        except Exception:
            logger.exception(
                "close: fill log failed symbol=%s; leaving pending", symbol
            )
            return False  # leave pending (no XACK)

        self.close_count += 1
        return True

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        if fields.get(b"intent", b"").decode("utf-8", errors="replace") == "close":
            return await self._execute_futures_close(fields)

        try:
            signal_id, signal = _signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable final signal; ACK as poison-pill")
            return True  # poison-pill: consume

        quantity = _resolve_quantity(
            base_quantity=self.base_quantity, size_multiplier=size_multiplier
        )

        if (
            self.live_mode_guard is not None
            and await self.live_mode_guard.is_live_suspended(self.redis)
        ):
            self.live_suspended_count += 1
            logger.warning(
                "live_mode suspended; skipping signal_id=%s symbol=%s",
                signal_id,
                signal.symbol,
            )
            return True  # skip (consumed, no retry)

        guard = self.live_mode_guard

        if (
            guard is not None
            and guard.symbol_lock_enabled
            and self.locked_symbol is not None
            and signal.symbol != self.locked_symbol
        ):
            self.symbol_lock_blocked_count += 1
            logger.warning(
                "symbol_lock: signal.symbol=%s != locked=%s; skipping signal_id=%s",
                signal.symbol,
                self.locked_symbol,
                signal_id,
            )
            return True  # skip (consumed)

        if guard is not None and quantity > guard.max_position_size_contracts:
            self.position_size_capped_count += 1
            logger.warning(
                "position_size_cap: signal=%s quantity %d → %d (gate3)",
                signal_id,
                quantity,
                guard.max_position_size_contracts,
            )
            quantity = guard.max_position_size_contracts

        if guard is not None:
            counter_key = f"{_DAILY_TRADE_KEY_PREFIX}{_kst_date_key()}"
            try:
                count = await self.redis.incr(counter_key)
                if int(count) == 1:
                    await self.redis.expire(
                        counter_key, _seconds_until_next_kst_midnight()
                    )
            except Exception:
                logger.exception(
                    "daily_trade counter INCR failed; allowing signal_id=%s",
                    signal_id,
                )
            else:
                if int(count) > guard.max_daily_trades:
                    self.daily_trade_blocked_count += 1
                    logger.warning(
                        "daily_trade_cap: count=%d > max=%d; skipping signal_id=%s",
                        int(count),
                        guard.max_daily_trades,
                        signal_id,
                    )
                    return True  # cap hit: skip (consumed)

        try:
            result = await self.passive_maker.place_passive_limit_futures(
                signal=signal,
                signal_id=signal_id,
                quantity=quantity,
                spec=self.contract_spec,
                timeout_seconds=self.passive_timeout_seconds,
            )
        except Exception:
            logger.exception(
                "passive_maker raised signal_id=%s; leaving pending", signal_id
            )
            return False  # leave pending (no XACK)

        if not result.is_filled:
            logger.info(
                "passive limit not filled signal_id=%s reason=%s",
                signal_id,
                result.reason,
            )
            return True  # final state, consumed, no bracket

        try:
            from shared.execution.passive_maker import Fill

            fill = Fill(
                order_id=result.order_id or "",
                price=result.filled_price or 0.0,
                quantity=quantity,
                filled_at_ms=0,
            )
            await self.pseudo_oco.register_bracket(
                signal=signal,
                signal_id=signal_id,
                fill=fill,
                tick_size_points=self.contract_spec.tick_size_points,
            )
        except Exception:
            logger.exception(
                "OCO register failed signal_id=%s order_id=%s; leaving pending",
                signal_id,
                result.order_id,
            )
            return False  # leave pending

        return True  # success: consume


def _resolve_mode() -> str:
    """order_router execution mode: off (default) | paper | live.

    Anything other than ``paper``/``live`` (including unset or empty) resolves
    to the safety-critical default ``off`` so the helper always returns one of
    the three documented modes.
    """
    mode = os.getenv("FUTURES_ORDER_ROUTER", "off").strip().lower()
    return mode if mode in ("paper", "live") else "off"


def _final_stream_for(mode: str) -> str:
    """Final-signal stream the order_router consumes (F-1).

    paper → `.shadow` isolated stream (forms the shadow pipeline with
    risk_filter shadow); live → unsuffixed. Env-overridable.
    """
    base = "signal.final.futures.shadow" if mode == "paper" else "signal.final.futures"
    return os.getenv("FUTURES_FINAL_STREAM", base)


def _fill_stream_for(mode: str) -> str:
    """Fill stream FillLogger writes (F-1). paper → `.shadow`; live → unsuffixed."""
    base = "order.fill.futures.shadow" if mode == "paper" else "order.fill.futures"
    return os.getenv("FUTURES_FILL_STREAM", base)


async def _build_and_run() -> int:
    """Production entrypoint — wires KIS adapter + PassiveMaker + PseudoOCO.

    Phase 4 Task 17 (KIS adapter) + config loaders close the prior PR #135
    "EX_CONFIG stub" deferral. The kill_switch sentinel path is read from
    KillSwitchConfig so the order_router refuses to start under the same
    path the kill_switch daemon writes to.
    """
    import signal as signal_mod
    import socket

    import redis.asyncio as aioredis

    from services.kill_switch.config import KillSwitchConfig
    from services.order_router.config import Phase4ExecutionConfig
    from shared.config.loader import ConfigLoader
    from shared.execution.config import ExecutionConfig
    from shared.execution.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )
    from shared.execution.executor import OrderExecutor
    from shared.execution.fill_logger import FillLogger
    from shared.execution.futures_instrument import resolve_futures_instrument_from_env
    from shared.execution.kis_futures_adapter import KISFuturesAdapter
    from shared.execution.live_exit_executor import LiveExitExecutor
    from shared.execution.live_mode_guard import LiveModeGuard
    from shared.execution.passive_maker import PassiveMaker
    from shared.execution.pseudo_oco import PseudoOCO
    from shared.kis.auth import KISAuthConfig
    from shared.kis.futures_feed import KISFuturesPriceFeed
    from shared.risk.runtime_state import RuntimeRiskState
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("paper", "live"):
        logger.info("FUTURES_ORDER_ROUTER=%s (off) — order_router inert, exiting", mode)
        await redis_client.aclose()
        return 0

    runtime_ledger = None
    storage_config = StorageConfig.load_or_default()
    if storage_config.runtime_storage.backend == "sqlite":
        runtime_ledger = SQLiteRuntimeLedger(storage_config.runtime_storage.sqlite)

    phase4_config = Phase4ExecutionConfig.from_yaml()
    kill_config = KillSwitchConfig.from_yaml()
    live_guard = LiveModeGuard.from_yaml()

    contract_specs = ContractSpecRegistry.from_yaml("config/execution.yaml")
    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol
    spec = resolve_contract_spec(symbol, contract_specs)

    fill_logger = FillLogger(
        redis=redis_client,
        archive_client=None,
        stream=_fill_stream_for(mode),
        maxlen=phase4_config.final_stream_maxlen,
        batch_size=10,
        runtime_ledger=runtime_ledger,
        asset_class="futures",
    )

    # Feed is ALWAYS real (both paper AND live): KIS 모의투자 serves no futures
    # realtime feed, so the real WS is the only orderbook source. This drops the
    # old KIS_FUTURES_MARKET gating on the feed — paper mode simulates execution,
    # not data; live order placement remains gated by OrderExecutor.config.trading_mode.
    kis_auth = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=True,
    )
    futures_feed = KISFuturesPriceFeed(config=kis_auth)
    futures_feed.update_symbols([symbol])
    await futures_feed.start()

    if mode == "paper":
        from shared.execution.paper_kis_futures_adapter import PaperKISFuturesAdapter

        kis_adapter: Any = PaperKISFuturesAdapter(futures_price_feed=futures_feed)
        guard_for_daemon = None  # paper places no real orders
        exit_runtime_state: Any = RuntimeRiskState(
            redis=redis_client, asset_class="futures", key_suffix="shadow"
        )
        exit_close_executor: Any = None  # paper: synthetic fills, no real orders
        exit_feed: Any = futures_feed
        logger.info(
            "order_router PAPER mode — real orderbook, simulated fills, no real orders"
        )
    else:  # live
        execution_section = ConfigLoader.load("execution.yaml").get("execution", {})
        order_executor = OrderExecutor(ExecutionConfig(**execution_section))
        await order_executor.initialize()
        kis_adapter = KISFuturesAdapter(
            order_executor=order_executor,
            futures_price_feed=futures_feed,
        )
        guard_for_daemon = live_guard
        # Live exit-monitor wiring (F-6 Task 3): real market flatten, guard-blocked.
        exit_runtime_state = RuntimeRiskState(redis=redis_client, asset_class="futures")
        exit_close_executor = LiveExitExecutor(
            kis_client=kis_adapter, live_mode_guard=live_guard, redis=redis_client
        )
        exit_feed = futures_feed

    passive_maker = PassiveMaker(kis_client=kis_adapter, fill_logger=fill_logger)
    pseudo_oco = PseudoOCO(
        fill_logger=fill_logger,
        runtime_state=exit_runtime_state,
        multiplier_krw_per_point=spec.multiplier_krw_per_point,
        close_executor=exit_close_executor,
    )

    worker_id = f"order-router-{socket.gethostname()}-{os.getpid()}"
    daemon = OrderRouterDaemon(
        redis=redis_client,
        passive_maker=passive_maker,
        pseudo_oco=pseudo_oco,
        contract_spec=spec,
        final_stream=_final_stream_for(mode),
        consumer_group="order_router",
        worker_id=worker_id,
        xread_block_ms=phase4_config.xread_block_ms,
        batch_size=phase4_config.xread_batch_size,
        passive_timeout_seconds=phase4_config.passive_timeout_seconds,
        base_quantity=phase4_config.base_quantity,
        kill_switch_sentinel_path=kill_config.sentinel_path,
        live_mode_guard=guard_for_daemon,
        locked_symbol=symbol,
        futures_price_feed=exit_feed,
        # intent=close reuses the same close_executor as the PseudoOCO
        # exit-monitor: None (synthetic fill) in paper, LiveExitExecutor in
        # live — one wallet-authority order-placement path either way.
        close_executor=exit_close_executor,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    # Publish the kill-switch api_error_rate metric for the decoupled futures
    # pipeline: OrderExecutor's REST outcomes feed the tracker (executor.py) and
    # this process owns the …:order_router source key (KIS_ERROR_RATE_SOURCE).
    # Gated by ORDER_ROUTER_PUBLISH_KIS_ERROR_RATE (default true) for opt-out.
    from shared.kis.error_rate import (
        start_error_rate_publisher,
        stop_error_rate_publisher,
    )

    publish_error_rate = (
        os.environ.get("ORDER_ROUTER_PUBLISH_KIS_ERROR_RATE", "true").strip().lower()
        == "true"
    )
    error_rate_tracker = await start_error_rate_publisher(enabled=publish_error_rate)

    try:
        await daemon.run()
    finally:
        await stop_error_rate_publisher(error_rate_tracker)
        await fill_logger.flush()
        await futures_feed.stop()
        await redis_client.aclose()
        if runtime_ledger is not None:
            runtime_ledger.close()
    return 0


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
