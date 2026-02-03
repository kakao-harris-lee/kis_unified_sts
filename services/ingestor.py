"""Market tick ingestor service.

Publishes real-time-ish stock ticks into Redis Stream `market:ticks`.

This service:
  1) Reads the latest universe snapshot from Redis key `system:universe:latest`
  2) Polls KIS current price for those symbols via `KISStockPollingAdapter`
  3) Publishes each tick to Redis Stream `market:ticks`

Notes:
  - Polling is a baseline. For true realtime, replace adapter with stock WS.

Environment variables:
  - `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_IS_REAL`
  - `TICK_STREAM` (default: market:ticks)
  - `UNIVERSE_LATEST_KEY` (default: system:universe:latest)
  - `INGESTOR_POLL_INTERVAL_SECONDS` (default: 1.0)
  - `INGESTOR_MAX_WORKERS` (default: 8)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from shared.kis import KISAuthConfig
from shared.kis.stock_poll_adapter import KISStockPollingAdapter
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestorConfig:
    tick_stream: str = os.environ.get("TICK_STREAM", "market:ticks")
    universe_latest_key: str = os.environ.get(
        "UNIVERSE_LATEST_KEY", "system:universe:latest"
    )
    poll_interval_seconds: float = float(
        os.environ.get("INGESTOR_POLL_INTERVAL_SECONDS", "1.0")
    )
    max_workers: int = int(os.environ.get("INGESTOR_MAX_WORKERS", "8"))


def _extract_codes(snapshot: dict[str, Any]) -> list[str]:
    codes = snapshot.get("codes", [])
    if not isinstance(codes, list):
        return []
    out = []
    for c in codes:
        s = str(c).strip()
        if s:
            out.append(s)
    return out


def run_ingestor(config: IngestorConfig) -> None:
    kis_is_real = os.environ.get("KIS_IS_REAL", "true").lower() == "true"
    kis_config = KISAuthConfig(is_real=kis_is_real)

    redis_client = RedisClient.get_client()
    publisher = StreamPublisher(config.tick_stream)

    adapter = KISStockPollingAdapter(
        kis_config,
        poll_interval_seconds=config.poll_interval_seconds,
        max_workers=config.max_workers,
    )

    def on_tick(tick) -> None:
        publisher.publish(tick.to_dict())

    adapter.connect()

    # Polling adapter runs a blocking loop → run in a daemon thread.
    t = threading.Thread(
        target=lambda: adapter.subscribe([], on_tick),
        name="kis_stock_polling",
        daemon=True,
    )
    t.start()

    last_codes: list[str] = []

    logger.info(
        f"Ingestor started (stream={config.tick_stream}, universe_key={config.universe_latest_key})"
    )

    try:
        while True:
            raw = redis_client.get(config.universe_latest_key)
            if raw:
                try:
                    snapshot = json.loads(raw)
                    codes = _extract_codes(snapshot)
                    if codes and codes != last_codes:
                        adapter.update_symbols(codes)
                        last_codes = codes
                        logger.info(f"Updated symbols: {len(codes)}")
                except Exception as e:
                    logger.debug(f"Failed to parse universe snapshot: {e}")

            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        adapter.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_ingestor(IngestorConfig())


if __name__ == "__main__":
    main()

