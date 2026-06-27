"""Futures monitor bridge entrypoint (flag-gated, shadow-first, default-off).

off (default): inert. shadow: publish to trading:futures:*:shadow + suppress
Telegram-to-log. live: live keys + real futures Telegram (Phase-5-gated).

Consumes order.fill.futures[.shadow] and signal.final.futures[.shadow].
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from shared.config.runtime_defaults import redis_url_from_env

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    return os.getenv("FUTURES_MONITOR_DAEMON", "off").strip().lower()


def _streams_for(mode: str) -> tuple[str, str]:
    if mode == "shadow":
        return "order.fill.futures.shadow", "signal.final.futures.shadow"
    return "order.fill.futures", "signal.final.futures"


def _ensure_shadow_isolation(mode: str) -> None:
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    if mode == "live" and os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        logger.warning("clearing TRADING_STATE_KEY_SUFFIX for live futures monitor")
        os.environ["TRADING_STATE_KEY_SUFFIX"] = ""


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = redis_url_from_env()
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("FUTURES_MONITOR_DAEMON=%s (off) — daemon inert, exiting", mode)
        await redis_client.aclose()
        return 0

    _ensure_shadow_isolation(mode)

    from services.futures_monitor.daemon import FuturesMonitorDaemon
    from services.stock_monitor.alerts import AlertSink
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.config.loader import ConfigLoader
    from shared.execution.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )
    from shared.execution.futures_instrument import resolve_futures_instrument_from_env
    from shared.notification.telegram import notifier_for_domain
    from shared.streaming.trading_state import TradingStatePublisher

    fill_default, signal_default = _streams_for(mode)
    fill_stream = os.environ.get("FUTURES_FILL_STREAM", fill_default)
    signal_stream = os.environ.get("FUTURES_FINAL_STREAM", signal_default)
    positions_key = os.environ.get(
        "FUTURES_MONITOR_POSITIONS_KEY", "futures:monitor:positions"
    )
    status_interval = float(os.environ.get("FUTURES_MONITOR_STATUS_INTERVAL", "5"))
    tick_stream = os.environ.get("FUTURES_TICK_STREAM", "raw_data")

    specs = ContractSpecRegistry.from_yaml("config/execution.yaml")
    instrument = resolve_futures_instrument_from_env()
    symbol = instrument.symbol
    spec = resolve_contract_spec(symbol, specs)

    tg = (
        ConfigLoader.load("futures_monitor.yaml")
        .get("futures_monitor", {})
        .get("telegram", {})
    )
    notifier = notifier_for_domain("futures") if mode == "live" else None
    alert_sink = AlertSink(
        notifier=notifier, mode=mode, pnl_alert_pct=float(tg.get("pnl_alert_pct", 3.0))
    )

    feed = StreamConsumerFeed(redis=redis_client, stream=tick_stream)
    feed.update_symbols([symbol])
    publisher = TradingStatePublisher(asset_class="futures")

    worker_id = f"futures-monitor-{socket.gethostname()}-{os.getpid()}"
    daemon = FuturesMonitorDaemon(
        redis=redis_client,
        feed=feed,
        publisher=publisher,
        alert_sink=alert_sink,
        positions_key=positions_key,
        fill_stream=fill_stream,
        signal_stream=signal_stream,
        consumer_group="futures_monitor",
        worker_id=worker_id,
        multiplier=spec.multiplier_krw_per_point,
        status_interval=status_interval,
        signal_meta_max=int(os.environ.get("FUTURES_MONITOR_SIGNAL_META_MAX", "1000")),
        health_stale_seconds=float(tg.get("health_stale_seconds", 600)),
        health_cooldown_seconds=float(tg.get("health_cooldown_seconds", 1800)),
        digest_time_kst=str(tg.get("digest_time_kst", "15:40")),
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    logger.info(
        "futures monitor starting worker=%s mode=%s symbol=%s suffix=%s",
        worker_id,
        mode,
        symbol,
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
