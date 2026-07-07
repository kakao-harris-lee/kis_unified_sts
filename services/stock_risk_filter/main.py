"""Stock risk-filter consumer-group daemon (M4-R, flag-gated, shadow-first).

Reads stock candidates from ``signal.candidate.stock.shadow`` (M4-P output),
runs the 8-filter RiskFilterLayer with stock config + session windows, and on
pass re-emits all candidate fields + size_multiplier + filtered_at_ms to
``signal.final.stock.shadow``.

Error taxonomy (mirrors services.risk_filter.main):
- Parse error            -> XACK (poison-pill drop)
- Filter eval raises     -> NO XACK (leave pending)
- final XADD raises      -> NO XACK

Flag routing (STOCK_RISK_FILTER env var):
  off (default / unset) — inert: log + close redis + return 0, no daemon
                          constructed.
  shadow                — full wiring: RiskFilterLayer + StockRiskFilterDaemon,
                          consuming signal.candidate.stock.shadow and emitting
                          signal.final.stock.shadow.
  live                  — same wiring on unsuffixed live streams.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from services.stock_risk_filter.codec import (
    decode_fields,
    stock_signal_from_stream_fields,
)
from shared.config.runtime_defaults import redis_url_from_env
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.strategy.market_time import now_kst
from shared.streaming.approval_gate import ApprovalGateConfig, is_gated, record_pending
from shared.streaming.stage import StreamStage
from shared.streaming.stock_keys import stock_daemon_positions_key

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400

# Asset-class tag for the pending-approval hash key / HASH field id (see
# shared/streaming/approval_keys.py). Fixed for this daemon — stock only.
_ASSET = "stock"


class StockRiskFilterDaemon(StreamStage):
    """Apply the 8-filter RiskFilterLayer to every stock candidate."""

    def __init__(
        self,
        *,
        redis: Any,
        layer: RiskFilterLayer,
        runtime_state: RuntimeRiskState,
        candidate_stream: str,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        final_maxlen: int,
        xread_block_ms: int,
        batch_size: int,
        clock: Callable[[], datetime] | None = None,
        approval_gate_config: ApprovalGateConfig | None = None,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=candidate_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.layer = layer
        self.runtime_state = runtime_state
        self.final_stream = final_stream
        self.final_maxlen = final_maxlen
        # Telegram interactive-alerts approval gate (Method A). Defaults to a
        # fully-inert config (enabled=False) so existing behavior is
        # unchanged unless an operator opts a strategy/symbol in.
        self.approval_gate_config = approval_gate_config or ApprovalGateConfig()
        # KST "now" provider — injectable so tests can pin the day boundary.
        self._clock = clock if clock is not None else now_kst
        # In-memory guard: the KST date we last reset (or confirmed reset) for.
        # Keeps the per-cycle hook off the Redis path except on the first cycle
        # of a new KST day.
        self._last_reset_date: date | None = None

    async def pre_iteration_gate(self) -> bool:
        """Reset the daily risk counters at the KST calendar-day boundary.

        The decoupled M4 pipeline keeps ``daily_trade_count`` / ``daily_pnl_krw``
        in ``risk:state:stock`` (24 h idle TTL). With trades continuing inside a
        <24 h weekday-to-weekday span the TTL never expired, so the counter
        accumulated across days and — once it reached
        ``risk_stock.max_daily_trades`` — every later candidate was silently
        rejected (``skip_reason="max_daily_trades"``, observed 2026-07-03). The
        futures orchestrator ``RiskManager`` already self-resets via
        ``_check_and_reset_daily``; this restores parity for the stock path.

        Runs once per consume cycle (before any candidate is evaluated), never
        per candidate. Reuses the unchanged ``RuntimeRiskState.should_reset_daily``
        / ``reset_daily`` API (the same one the M5c cron calls), so daily resets
        share the state load/save path with the weekly/monthly rollover. Always
        returns ``True`` — the reset must never abort the loop.
        """
        await self._maybe_reset_daily()
        return True

    async def _maybe_reset_daily(self) -> None:
        """Zero the daily counters once per KST day, idempotently.

        Fast path: an in-memory date guard skips Redis entirely for every cycle
        after the day's first. On a new KST date the Redis ``:meta`` guard
        (``should_reset_daily``) makes the reset idempotent across restarts and
        co-workers — a mid-session restart that finds the day already stamped
        skips the reset instead of wiping the session's accumulated counters.
        Transient Redis errors are swallowed (the loop must not die) and the
        in-memory guard is left un-advanced so the next cycle retries.
        """
        now = self._clock()
        today = now.date()
        if self._last_reset_date == today:
            return  # already handled this KST day — stay off the Redis path
        try:
            if await self.runtime_state.should_reset_daily(now_kst=now):
                await self.runtime_state.reset_daily(now_kst=now)
                logger.info("Stock daily risk counters reset for KST date %s", today)
        except Exception:
            logger.exception(
                "Stock daily risk-counter reset failed for KST date %s; "
                "retrying next cycle",
                today,
            )
            return  # do NOT advance the guard — retry on the next cycle
        self._last_reset_date = today

    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]  # noqa: ARG002
    ) -> bool:
        try:
            signal_id, signal = stock_signal_from_stream_fields(fields)
            passthrough = decode_fields(fields)
        except Exception:
            logger.exception("Unparseable stock candidate; ACKing as poison-pill")
            return True  # poison-pill: consume

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)  # type: ignore[arg-type]  # StockRiskSignal is duck-typed: filters only read .symbol + .generated_at
        except Exception:
            logger.exception(
                "Stock filter eval failed signal_id=%s; leaving pending", signal_id
            )
            return False

        if not result.passed:
            logger.info(
                "Stock candidate rejected signal_id=%s reason=%s",
                signal_id,
                result.skip_reason,
            )
            return True  # rejected: consume (no final)

        try:
            # signal_id is already carried by the decode_fields passthrough;
            # do not re-set it explicitly.
            fields_out = dict(passthrough)
            fields_out["size_multiplier"] = str(result.size_multiplier)
            fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
            if is_gated(signal.strategy, signal.code, self.approval_gate_config):
                # Telegram interactive-alerts approval gate (Method A): hold
                # the fully-assembled final-stream dict for operator approval
                # instead of XADDing to signal.final.stock. The bot replays
                # fields_out verbatim on approval.
                await record_pending(
                    self.redis,
                    _ASSET,
                    signal_id,
                    fields_out,
                    self.approval_gate_config.pending_ttl_seconds,
                )
                return True  # consumed: held pending, not XADDed
            await self.redis.xadd(
                self.final_stream,
                fields_out,
                maxlen=self.final_maxlen,
                approximate=True,
            )
            await self.redis.expire(self.final_stream, _STREAM_TTL_SECONDS)
        except Exception:
            logger.exception(
                "Stock final XADD failed signal_id=%s; leaving pending", signal_id
            )
            return False

        return True

    # No on_shutdown override: stock daemon has no audit-sink to flush.


# ---------------------------------------------------------------------------
# Flag-gated entrypoint (shadow-first, default-off)
# ---------------------------------------------------------------------------


def _resolve_mode() -> str:
    """Return the daemon mode from the env var (default 'off')."""
    return os.getenv("STOCK_RISK_FILTER", "off").strip().lower()


def _is_active_mode(mode: str) -> bool:
    """Return True when the daemon should run."""
    return mode in {"shadow", "live"}


def _streams_for(mode: str) -> tuple[str, str]:
    """Return ``(candidate_stream, final_stream)`` for the mode.

    shadow -> (signal.candidate.stock.shadow, signal.final.stock.shadow).
    live -> unsuffixed streams.
    """
    if mode == "shadow":
        return "signal.candidate.stock.shadow", "signal.final.stock.shadow"
    return "signal.candidate.stock", "signal.final.stock"


async def _build_and_run() -> int:
    """Flag-gated production entrypoint.

    off / unset: inert — log and return 0, constructing NONE of the
                 layer/runtime-state/daemon objects.
    shadow/live: full wiring through RiskFilterLayer on mode-appropriate streams.
    """
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if not _is_active_mode(mode):
        logger.info("STOCK_RISK_FILTER=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    from shared.risk.config import StockRiskConfig, load_stock_trading_windows
    from shared.streaming.client import RedisClient

    candidate_stream, final_stream = _streams_for(mode)
    candidate_stream = os.environ.get("STOCK_CANDIDATE_STREAM", candidate_stream)
    final_stream = os.environ.get("STOCK_FINAL_STREAM", final_stream)

    config = StockRiskConfig.from_yaml()
    windows = load_stock_trading_windows()

    # Sync redis for the open-position provider (layer.evaluate is sync).
    sync_redis = RedisClient.get_client()
    positions_key = stock_daemon_positions_key()

    def _has_open_position(code: str) -> bool:
        try:
            return bool(sync_redis.hexists(positions_key, code))
        except Exception:
            logger.warning(
                "Redis error checking open position for %s; "
                "assuming open (fail-closed)",
                code,
            )
            return True  # fail-closed: block re-entry on uncertainty

    layer = RiskFilterLayer.from_config(
        config=config,
        trading_windows=windows,
        has_open_position_provider=_has_open_position,
    )
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="stock")
    # Loaded once at startup (not on the hot path) — inert by default
    # (config/telegram_bot.yaml::approval_gate.enabled = false).
    approval_gate_config = ApprovalGateConfig.from_yaml()

    worker_id = f"stock-risk-filter-{socket.gethostname()}-{os.getpid()}"
    daemon = StockRiskFilterDaemon(
        redis=redis_client,
        layer=layer,
        runtime_state=runtime_state,
        candidate_stream=candidate_stream,
        final_stream=final_stream,
        consumer_group="stock_risk_filter",
        worker_id=worker_id,
        final_maxlen=10_000,
        xread_block_ms=2000,
        batch_size=10,
        approval_gate_config=approval_gate_config,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
