"""Stock monitor bridge entrypoint (flag-gated, shadow-first, default-off).

off (default): inert. shadow: publish to trading:stock:*:shadow + suppress
Telegram-to-log. live (M5d): live keys + real Telegram.

Consumes the daemon streams ``order.fill.stock[.shadow]`` and
``signal.final.stock[.shadow]`` (suffix in shadow mode).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    """Return the daemon mode from STOCK_MONITOR_DAEMON (default 'off')."""
    return os.getenv("STOCK_MONITOR_DAEMON", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    """Return (fill_stream, signal_stream) for the mode (shadow -> suffixed, else live)."""
    if mode == "shadow":
        return "order.fill.stock.shadow", "signal.final.stock.shadow"
    return "order.fill.stock", "signal.final.stock"


def _ensure_shadow_isolation(mode: str) -> None:
    """Fail-safe dashboard key suffix handling.

    Shadow must always use isolated keys. Live must always use unsuffixed keys,
    even when the base systemd unit supplied ``TRADING_STATE_KEY_SUFFIX=shadow``.
    """
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    if mode == "live" and os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        logger.warning("clearing TRADING_STATE_KEY_SUFFIX for live stock monitor")
        os.environ["TRADING_STATE_KEY_SUFFIX"] = ""


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
    from shared.streaming.stock_keys import stock_daemon_positions_key
    from shared.streaming.trading_state import TradingStatePublisher

    fill_default, signal_default = _streams_for(mode)
    fill_stream = os.environ.get("STOCK_FILL_STREAM", fill_default)
    signal_stream = os.environ.get("STOCK_FINAL_STREAM", signal_default)
    positions_key = stock_daemon_positions_key()
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

    worker_id = f"stock-monitor-{socket.gethostname()}-{os.getpid()}"
    daemon = StockMonitorDaemon(
        redis=redis_client,
        feed=feed,
        publisher=publisher,
        alert_sink=alert_sink,
        positions_key=positions_key,
        fill_stream=fill_stream,
        signal_stream=signal_stream,
        consumer_group="stock_monitor",
        worker_id=worker_id,
        fee_rate=fee_rate,
        status_interval=status_interval,
        signal_meta_max=int(os.environ.get("STOCK_MONITOR_SIGNAL_META_MAX", "1000")),
        health_stale_seconds=float(tg.get("health_stale_seconds", 600)),
        health_cooldown_seconds=float(tg.get("health_cooldown_seconds", 1800)),
        digest_time_kst=str(tg.get("digest_time_kst", "15:40")),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    logger.info(
        "stock monitor starting worker=%s mode=%s suffix=%s",
        worker_id,
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
