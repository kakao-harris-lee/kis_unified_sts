"""Lightweight Redis stream publisher for monitoring ticks.

This module mirrors websocket tick payloads to Redis Streams so that
stream_exporter can build realtime Prometheus metrics without touching
the trading write-path semantics.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from shared.streaming.client import RedisClient

logger = logging.getLogger(__name__)


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
    return None


@dataclass(frozen=True)
class TickStreamPublisherConfig:
    enabled: bool = True
    stock_stream: str = "market:ticks"
    futures_stream: str = "raw_data"
    stream_maxlen: int = 10000
    stock_min_interval_seconds: float = 1.0
    futures_min_interval_seconds: float = 0.2
    stream_ttl_seconds: int = 86400
    ttl_refresh_interval_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> TickStreamPublisherConfig:
        return cls(
            enabled=os.getenv("MONITOR_TICK_STREAM_ENABLED", "true").lower() == "true",
            stock_stream=os.getenv("MONITOR_STOCK_TICK_STREAM", "market:ticks").strip()
            or "market:ticks",
            futures_stream=os.getenv("MONITOR_FUTURES_TICK_STREAM", "raw_data").strip()
            or "raw_data",
            stream_maxlen=int(os.getenv("MONITOR_TICK_STREAM_MAXLEN", "10000")),
            stock_min_interval_seconds=float(
                os.getenv("MONITOR_STOCK_TICK_MIN_INTERVAL_SECONDS", "1.0")
            ),
            futures_min_interval_seconds=float(
                os.getenv("MONITOR_FUTURES_TICK_MIN_INTERVAL_SECONDS", "0.2")
            ),
            stream_ttl_seconds=int(
                os.getenv("MONITOR_TICK_STREAM_TTL_SECONDS", "86400")
            ),
            ttl_refresh_interval_seconds=float(
                os.getenv("MONITOR_TICK_STREAM_TTL_REFRESH_SECONDS", "60")
            ),
        )


class TickStreamPublisher:
    """Best-effort tick mirroring into Redis streams."""

    def __init__(
        self, config: TickStreamPublisherConfig, client: Any | None = None
    ) -> None:
        self.config = config
        self.client = client or RedisClient.get_client()
        self._last_publish_at: dict[tuple[str, str], float] = {}
        self._last_ttl_refresh_at: dict[str, float] = {}

    def publish(self, asset: str, symbol: str, payload: dict[str, Any]) -> None:
        if not self.config.enabled:
            return

        stream_name, min_interval = self._resolve(asset)
        if not stream_name:
            return

        now = time.time()
        key = (asset, symbol)
        last = self._last_publish_at.get(key, 0.0)
        if now - last < max(0.0, min_interval):
            return

        fields = self._build_fields(symbol=symbol, payload=payload, now=now)
        if fields is None:
            return

        try:
            self.client.xadd(
                stream_name,
                fields,
                maxlen=self.config.stream_maxlen,
                approximate=True,
            )
            self._last_publish_at[key] = now
            self._refresh_ttl_if_due(stream_name=stream_name, now=now)
        except Exception:
            logger.debug(
                "Tick stream publish failed: asset=%s symbol=%s stream=%s",
                asset,
                symbol,
                stream_name,
                exc_info=True,
            )

    def _resolve(self, asset: str) -> tuple[str, float]:
        if asset == "stock":
            return self.config.stock_stream, self.config.stock_min_interval_seconds
        if asset == "futures":
            return self.config.futures_stream, self.config.futures_min_interval_seconds
        return "", 0.0

    def _build_fields(
        self,
        *,
        symbol: str,
        payload: dict[str, Any],
        now: float,
    ) -> dict[str, str] | None:
        price = (
            _parse_float(payload.get("current_price"))
            or _parse_float(payload.get("close"))
            or _parse_float(payload.get("price"))
        )
        if price is None or price <= 0:
            return None

        event_ts = _parse_float(payload.get("timestamp")) or now
        fields: dict[str, str] = {
            "symbol": symbol,
            "code": symbol,
            "price": str(price),
            "current_price": str(price),
            "close": str(price),
            "timestamp": str(event_ts),
        }

        for key in ("open", "high", "low"):
            value = _parse_float(payload.get(key))
            if value is not None:
                fields[key] = str(value)

        volume = _parse_float(payload.get("volume"))
        if volume is not None and volume >= 0:
            fields["volume"] = str(volume)

        vol_cum = _parse_bool(payload.get("volume_is_cumulative"))
        if vol_cum is not None:
            fields["volume_is_cumulative"] = "true" if vol_cum else "false"

        return fields

    def _refresh_ttl_if_due(self, *, stream_name: str, now: float) -> None:
        interval = max(0.0, self.config.ttl_refresh_interval_seconds)
        last = self._last_ttl_refresh_at.get(stream_name, 0.0)
        if now - last < interval:
            return
        try:
            self.client.expire(stream_name, int(self.config.stream_ttl_seconds))
            self._last_ttl_refresh_at[stream_name] = now
        except Exception:
            logger.debug(
                "Failed to refresh stream TTL: stream=%s",
                stream_name,
                exc_info=True,
            )
