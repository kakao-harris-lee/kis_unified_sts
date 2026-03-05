"""Lightweight Redis stream publisher for monitoring ticks.

This module mirrors websocket tick payloads to Redis Streams so that
stream_exporter can build realtime Prometheus metrics without touching
the trading write-path semantics.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
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


def _extract_symbol_name(payload: dict[str, Any]) -> str:
    for key in (
        "name",
        "stock_name",
        "symbol_name",
        "item_name",
        "prdt_name",
        "hts_kor_isnm",
    ):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


@dataclass(frozen=True)
class TickStreamPublisherConfig:
    enabled: bool = True
    async_publish: bool = True
    stock_stream: str = "market:ticks"
    futures_stream: str = "raw_data"
    stream_maxlen: int = 10000
    stock_min_interval_seconds: float = 1.0
    futures_min_interval_seconds: float = 0.2
    stream_ttl_seconds: int = 86400
    ttl_refresh_interval_seconds: float = 60.0
    queue_maxsize: int = 5000
    flush_batch_size: int = 200
    worker_wait_seconds: float = 0.2

    @classmethod
    def from_env(cls) -> TickStreamPublisherConfig:
        return cls(
            enabled=os.getenv("MONITOR_TICK_STREAM_ENABLED", "true").lower() == "true",
            async_publish=os.getenv("MONITOR_TICK_STREAM_ASYNC", "true").lower()
            == "true",
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
            queue_maxsize=max(
                100,
                int(os.getenv("MONITOR_TICK_STREAM_QUEUE_MAXSIZE", "5000")),
            ),
            flush_batch_size=max(
                1,
                int(os.getenv("MONITOR_TICK_STREAM_FLUSH_BATCH_SIZE", "200")),
            ),
            worker_wait_seconds=max(
                0.01,
                float(os.getenv("MONITOR_TICK_STREAM_WORKER_WAIT_SECONDS", "0.2")),
            ),
        )


@dataclass(frozen=True)
class _QueuedTick:
    stream_name: str
    asset: str
    symbol: str
    fields: dict[str, str]
    enqueued_at: float


class TickStreamPublisher:
    """Best-effort tick mirroring into Redis streams."""

    def __init__(
        self, config: TickStreamPublisherConfig, client: Any | None = None
    ) -> None:
        self.config = config
        self.client = client or RedisClient.get_client()
        self._last_enqueue_at: dict[tuple[str, str], float] = {}
        self._last_ttl_refresh_at: dict[str, float] = {}
        self._pending: deque[_QueuedTick] = deque()
        self._queue_lock = threading.Lock()
        self._queue_cond = threading.Condition(self._queue_lock)
        self._closed = False
        self._worker_thread: threading.Thread | None = None

        # Internal health stats (read-only via get_stats()).
        self._enqueued_total = 0
        self._published_total = 0
        self._dropped_total = 0
        self._dropped_overflow_total = 0
        self._publish_error_total = 0
        self._max_queue_depth = 0
        self._last_publish_success_at: float | None = None

        if self.config.enabled and self.config.async_publish:
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="TickStreamPublisherWorker",
            )
            self._worker_thread.start()

    def publish(self, asset: str, symbol: str, payload: dict[str, Any]) -> None:
        if not self.config.enabled:
            return

        stream_name, min_interval = self._resolve(asset)
        if not stream_name:
            return

        now = time.time()
        key = (asset, symbol)
        last = self._last_enqueue_at.get(key, 0.0)
        if now - last < max(0.0, min_interval):
            return

        fields = self._build_fields(
            asset=asset, symbol=symbol, payload=payload, now=now
        )
        if fields is None:
            return
        self._last_enqueue_at[key] = now

        if self.config.async_publish:
            self._enqueue(
                _QueuedTick(
                    stream_name=stream_name,
                    asset=asset,
                    symbol=symbol,
                    fields=fields,
                    enqueued_at=now,
                )
            )
            return
        self._publish_now(
            stream_name=stream_name, asset=asset, symbol=symbol, fields=fields, now=now
        )

    def close(self, timeout: float = 2.0) -> None:
        if not self.config.async_publish:
            return
        with self._queue_cond:
            self._closed = True
            self._queue_cond.notify_all()
        worker = self._worker_thread
        if worker and worker.is_alive():
            worker.join(timeout=max(0.1, timeout))
            if worker.is_alive():
                logger.warning("Tick stream publisher worker did not stop cleanly")

    def get_stats(self) -> dict[str, Any]:
        with self._queue_lock:
            queue_depth = len(self._pending)
        worker_alive = bool(self._worker_thread and self._worker_thread.is_alive())
        return {
            "async_publish": self.config.async_publish,
            "queue_depth": queue_depth,
            "queue_maxsize": self.config.queue_maxsize,
            "queue_high_watermark": self._max_queue_depth,
            "enqueued_total": self._enqueued_total,
            "published_total": self._published_total,
            "dropped_total": self._dropped_total,
            "dropped_overflow_total": self._dropped_overflow_total,
            "publish_error_total": self._publish_error_total,
            "worker_alive": worker_alive,
            "last_publish_success_at": self._last_publish_success_at,
        }

    def _resolve(self, asset: str) -> tuple[str, float]:
        if asset == "stock":
            return self.config.stock_stream, self.config.stock_min_interval_seconds
        if asset == "futures":
            return self.config.futures_stream, self.config.futures_min_interval_seconds
        return "", 0.0

    def _build_fields(
        self,
        *,
        asset: str,
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
            "asset": asset,
            "symbol": symbol,
            "code": symbol,
            "price": str(price),
            "current_price": str(price),
            "close": str(price),
            "timestamp": str(event_ts),
        }
        symbol_name = _extract_symbol_name(payload)
        if symbol_name:
            fields["name"] = symbol_name

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

    def _enqueue(self, tick: _QueuedTick) -> None:
        with self._queue_cond:
            if self._closed:
                self._dropped_total += 1
                return
            if len(self._pending) >= self.config.queue_maxsize:
                self._pending.popleft()
                self._dropped_total += 1
                self._dropped_overflow_total += 1
            self._pending.append(tick)
            self._enqueued_total += 1
            if len(self._pending) > self._max_queue_depth:
                self._max_queue_depth = len(self._pending)
            self._queue_cond.notify()

    def _worker_loop(self) -> None:
        while True:
            batch = self._take_batch()
            if not batch:
                if self._closed:
                    return
                continue
            self._flush_batch(batch)

    def _take_batch(self) -> list[_QueuedTick]:
        with self._queue_cond:
            while not self._pending and not self._closed:
                self._queue_cond.wait(timeout=self.config.worker_wait_seconds)
            if not self._pending:
                return []
            n = min(len(self._pending), self.config.flush_batch_size)
            return [self._pending.popleft() for _ in range(n)]

    def _flush_batch(self, batch: list[_QueuedTick]) -> None:
        latest_by_symbol: dict[tuple[str, str], _QueuedTick] = {}
        for item in batch:
            latest_by_symbol[(item.stream_name, item.symbol)] = item

        for item in latest_by_symbol.values():
            self._publish_now(
                stream_name=item.stream_name,
                asset=item.asset,
                symbol=item.symbol,
                fields=item.fields,
                now=time.time(),
            )

    def _publish_now(
        self,
        *,
        stream_name: str,
        asset: str,
        symbol: str,
        fields: dict[str, str],
        now: float,
    ) -> None:
        try:
            self.client.xadd(
                stream_name,
                fields,
                maxlen=self.config.stream_maxlen,
                approximate=True,
            )
            self._published_total += 1
            self._last_publish_success_at = now
            self._refresh_ttl_if_due(stream_name=stream_name, now=now)
        except Exception:
            self._publish_error_total += 1
            logger.debug(
                "Tick stream publish failed: asset=%s symbol=%s stream=%s",
                asset,
                symbol,
                stream_name,
                exc_info=True,
            )

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
