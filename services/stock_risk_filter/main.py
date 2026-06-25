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
from typing import Any

from services.stock_risk_filter.codec import (
    decode_fields,
    stock_signal_from_stream_fields,
)
from shared.config.runtime_defaults import redis_url_from_env
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.stage import StreamStage
from shared.streaming.stock_keys import stock_daemon_positions_key

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


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
