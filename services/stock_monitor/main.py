"""Stock monitor bridge entrypoint (flag-gated, shadow-first, default-off).

off (default): inert. shadow: publish to trading:stock:*:shadow + suppress
Telegram-to-log. live (M5d): live keys + real Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    return os.getenv("STOCK_MONITOR_DAEMON", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    if mode == "shadow":
        return "order.fill.stock.shadow", "signal.final.stock.shadow"
    return "order.fill.stock", "signal.final.stock"


def _ensure_shadow_isolation(mode: str) -> None:
    """Fail-safe: in shadow, force the dashboard key suffix if the operator
    forgot to set it, so M5a can never clobber the orchestrator's live keys."""
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("STOCK_MONITOR_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    _ensure_shadow_isolation(mode)

    from services.stock_monitor.alerts import AlertSink
    from services.stock_monitor.daemon import StockMonitorDaemon
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.notification.telegram import notifier_for_domain
    from shared.streaming.trading_state import TradingStatePublisher

    fill_default, signal_default = _streams_for(mode)
    fill_stream = os.environ.get("STOCK_FILL_STREAM", fill_default)
    signal_stream = os.environ.get("STOCK_FINAL_STREAM", signal_default)
    positions_key = os.environ.get("STOCK_POSITIONS_KEY", "trading:stock:positions")
    status_interval = float(os.environ.get("STOCK_MONITOR_STATUS_INTERVAL", "5"))
    tick_stream = os.environ.get("STOCK_TICK_STREAM", "market:ticks")

    fee_rate = float(
        ConfigLoader.load("stock_exit.yaml")
        .get("stock_exit", {})
        .get("fee_rate", 0.003)
    )
    tg = (
        ConfigLoader.load("stock_monitor.yaml")
        .get("stock_monitor", {})
        .get("telegram", {})
    )

    notifier = notifier_for_domain("stock") if mode == "live" else None
    alert_sink = AlertSink(
        notifier=notifier, mode=mode, pnl_alert_pct=float(tg.get("pnl_alert_pct", 3.0))
    )

    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)
    publisher = TradingStatePublisher(asset_class="stock")

    daemon = StockMonitorDaemon(
        redis=redis_client,
        feed=feed,
        publisher=publisher,
        alert_sink=alert_sink,
        positions_key=positions_key,
        fill_stream=fill_stream,
        signal_stream=signal_stream,
        consumer_group="stock_monitor",
        worker_id=f"stock-monitor-{socket.gethostname()}-{os.getpid()}",
        fee_rate=fee_rate,
        status_interval=status_interval,
        signal_meta_max=int(os.environ.get("STOCK_MONITOR_SIGNAL_META_MAX", "1000")),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    logger.info(
        "stock monitor starting mode=%s suffix=%s",
        mode,
        os.environ.get("TRADING_STATE_KEY_SUFFIX", ""),
    )
    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
