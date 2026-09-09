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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import redis
from pydantic import ConfigDict, Field

from shared.config.base import ServiceConfigBase
from shared.exceptions import InfrastructureError
from shared.models.stream_models import ORDERBOOK_FIELDS, MarketTickMessage
from shared.streaming.client import RedisClient
from shared.streaming.codec import encode

logger = logging.getLogger(__name__)


def orderbook_publish_fields(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Top-of-book fields to merge into a futures tick before publishing.

    The KIS futures feed delivers orderbook (H0IFASP0) and trade (H0IFCNT0)
    ticks separately and only the trade tick reaches a tick callback, so every
    producer of the futures tick stream would otherwise publish quote-less
    ticks. A consumer that needs a quote — the decoupled order-router's
    send-time slippage gate, its paper fill simulator — would then have no
    source but a second KIS WebSocket on the same account, which is exactly
    the collision this avoids. Both producers (``services/market_ingest`` and
    the monolithic orchestrator) call this so the merge rule lives once.

    Returns ``{}`` unless both sides of the book are positive; never raises.
    ``code`` is excluded and the snapshot's ``timestamp`` is re-keyed to
    ``quote_ts``: the published entry's ``timestamp`` belongs to the trade tick,
    and a stale quote must not backdate a fresh trade. Keeping the orderbook
    tick's own time as a separate field is what lets a consumer bound the age of
    the BOOK rather than of the last print — the two diverge exactly when it
    matters, because the feed keeps merging a frozen book onto fresh trades
    (``KISFuturesPriceFeed._log_orderbook_staleness`` models that condition).
    """
    if not snapshot:
        return {}
    try:
        bid = float(snapshot.get("bid_price_1") or 0.0)
        ask = float(snapshot.get("ask_price_1") or 0.0)
    except (TypeError, ValueError):
        return {}
    if bid <= 0 or ask <= 0:
        return {}
    fields = {key: snapshot[key] for key in ORDERBOOK_FIELDS if key in snapshot}
    if "quote_ts" not in fields:
        # A WS feed snapshot times the book in `timestamp`; a snapshot that
        # already came off the stream carries `quote_ts` and keeps it.
        try:
            quote_ts = float(snapshot.get("timestamp"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return fields
        if quote_ts >= 0:
            fields["quote_ts"] = quote_ts
    return fields


class TickStreamPublisherConfig(ServiceConfigBase):
    """Configuration for tick stream publisher.

    Attributes:
        enabled: Enable tick stream publishing
        async_publish: Use async worker thread for publishing
        stock_stream: Redis stream name for stock ticks
        futures_stream: Redis stream name for futures ticks
        stream_maxlen: Maximum stream length (MAXLEN)
        stock_min_interval_seconds: Minimum interval between stock tick publishes
        futures_min_interval_seconds: Minimum interval between futures tick publishes
        stream_ttl_seconds: Stream TTL in seconds
        ttl_refresh_interval_seconds: Interval to refresh stream TTL
        queue_maxsize: Maximum queue size for async publishing
        flush_batch_size: Batch size for flushing queue
        worker_wait_seconds: Worker thread wait timeout
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=True, description="Enable tick stream publishing")
    async_publish: bool = Field(default=True, description="Use async worker thread")
    stock_stream: str = Field(
        default="market:ticks", description="Redis stream for stock ticks"
    )
    futures_stream: str = Field(
        default="raw_data", description="Redis stream for futures ticks"
    )
    stream_maxlen: int = Field(default=10000, description="Maximum stream length")
    stock_min_interval_seconds: float = Field(
        default=1.0, description="Min interval for stock ticks (seconds)"
    )
    futures_min_interval_seconds: float = Field(
        default=0.2, description="Min interval for futures ticks (seconds)"
    )
    stream_ttl_seconds: int = Field(default=86400, description="Stream TTL (seconds)")
    ttl_refresh_interval_seconds: float = Field(
        default=60.0, description="TTL refresh interval (seconds)"
    )
    queue_maxsize: int = Field(default=5000, description="Maximum queue size")
    flush_batch_size: int = Field(default=200, description="Batch size for queue flush")
    worker_wait_seconds: float = Field(
        default=0.2, description="Worker thread wait timeout (seconds)"
    )

    # Default env prefix (though we override from_env for custom mapping)
    _env_prefix = "MONITOR_TICK_STREAM_"

    @classmethod
    def from_env(
        cls, env_prefix: str | None = None, **overrides: Any
    ) -> TickStreamPublisherConfig:
        """Load configuration from environment variables.

        Handles non-standard env var names with mixed prefixes:
        - MONITOR_TICK_STREAM_* for most fields
        - MONITOR_STOCK_TICK_* for stock-specific fields
        - MONITOR_FUTURES_TICK_* for futures-specific fields
        """
        _ = env_prefix
        env_data = {}

        # Standard MONITOR_TICK_STREAM_* fields
        enabled = os.getenv("MONITOR_TICK_STREAM_ENABLED", "true").lower() == "true"
        env_data["enabled"] = enabled

        async_pub = os.getenv("MONITOR_TICK_STREAM_ASYNC", "true").lower() == "true"
        env_data["async_publish"] = async_pub

        # Non-standard prefix fields
        stock_stream = (
            os.getenv("MONITOR_STOCK_TICK_STREAM", "market:ticks").strip()
            or "market:ticks"
        )
        env_data["stock_stream"] = stock_stream

        futures_stream = (
            os.getenv("MONITOR_FUTURES_TICK_STREAM", "raw_data").strip() or "raw_data"
        )
        env_data["futures_stream"] = futures_stream

        # Numeric fields with validation
        stream_maxlen = int(os.getenv("MONITOR_TICK_STREAM_MAXLEN", "10000"))
        env_data["stream_maxlen"] = stream_maxlen

        stock_min_interval = float(
            os.getenv("MONITOR_STOCK_TICK_MIN_INTERVAL_SECONDS", "1.0")
        )
        env_data["stock_min_interval_seconds"] = stock_min_interval

        futures_min_interval = float(
            os.getenv("MONITOR_FUTURES_TICK_MIN_INTERVAL_SECONDS", "0.2")
        )
        env_data["futures_min_interval_seconds"] = futures_min_interval

        stream_ttl = int(os.getenv("MONITOR_TICK_STREAM_TTL_SECONDS", "86400"))
        env_data["stream_ttl_seconds"] = stream_ttl

        ttl_refresh = float(os.getenv("MONITOR_TICK_STREAM_TTL_REFRESH_SECONDS", "60"))
        env_data["ttl_refresh_interval_seconds"] = ttl_refresh

        # Queue fields with min/max constraints
        queue_maxsize = max(
            100, int(os.getenv("MONITOR_TICK_STREAM_QUEUE_MAXSIZE", "5000"))
        )
        env_data["queue_maxsize"] = queue_maxsize

        flush_batch = max(
            1, int(os.getenv("MONITOR_TICK_STREAM_FLUSH_BATCH_SIZE", "200"))
        )
        env_data["flush_batch_size"] = flush_batch

        worker_wait = max(
            0.01, float(os.getenv("MONITOR_TICK_STREAM_WORKER_WAIT_SECONDS", "0.2"))
        )
        env_data["worker_wait_seconds"] = worker_wait

        # Apply overrides
        env_data.update(overrides)

        return cls(**env_data)


class OrderbookMergeLog:
    """One-shot WARNING / recovery-INFO latch for the futures orderbook merge.

    Both producers merge the same way and fail the same way, and a silent
    revert to trade-only ticks has no local symptom at all: it surfaces far
    downstream as the order-router blocking every signal on
    ``orderbook_unavailable``, which reads as a market condition rather than a
    data gap. Prior reviews (#621 F5, #623 F2) asked for exactly this shape.

    First failure logs WARNING, first success after that logs INFO, and the
    steady state on either side is silent — the merge sits on a per-tick hot
    path, so a per-occurrence log is not an option.
    """

    def __init__(self, log: logging.Logger, producer: str) -> None:
        self._log = log
        self._producer = producer
        self._warned = False

    @property
    def warned(self) -> bool:
        return self._warned

    def failed(self, reason: str) -> None:
        if self._warned:
            return
        self._warned = True
        self._log.warning(
            "%s: futures orderbook merge unavailable (%s) — republished ticks "
            "carry no quote, so a stream consumer's entry gate blocks on "
            "orderbook_unavailable. Logged once until it recovers.",
            self._producer,
            reason,
        )

    def ok(self) -> None:
        if not self._warned:
            return
        self._warned = False
        self._log.info(
            "%s: futures orderbook merge recovered — republished ticks carry a "
            "quote again",
            self._producer,
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
        try:
            msg = MarketTickMessage.from_source_payload(
                asset=asset,
                symbol=symbol,
                payload=payload,
                now=now,
            )
        except ValueError:
            return None

        # `encode` drops None fields, so the optional orderbook fields
        # (bid/ask price+qty, spread — shared.models.stream_models.
        # ORDERBOOK_FIELDS) ride along only when the producer's payload
        # carried them. Trade-only producers publish exactly what they did
        # before; the orchestrator's merged feed snapshot now also carries
        # the top of book.
        fields = encode(msg)
        # Compatibility aliases for the rollout window. New consumers should
        # decode the canonical v1 schema; old consumers still see the legacy
        # field names they already understand.
        fields["code"] = msg.symbol
        fields["close"] = str(msg.price)
        fields["current_price"] = str(msg.price)
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
        except (redis.RedisError, InfrastructureError) as e:
            self._publish_error_total += 1
            logger.debug(
                "Redis stream publish failed: asset=%s symbol=%s stream=%s error=%s",
                asset,
                symbol,
                stream_name,
                e,
            )

    def _refresh_ttl_if_due(self, *, stream_name: str, now: float) -> None:
        interval = max(0.0, self.config.ttl_refresh_interval_seconds)
        last = self._last_ttl_refresh_at.get(stream_name, 0.0)
        if now - last < interval:
            return
        try:
            self.client.expire(stream_name, int(self.config.stream_ttl_seconds))
            self._last_ttl_refresh_at[stream_name] = now
        except (redis.RedisError, InfrastructureError) as e:
            logger.debug(
                "Failed to refresh stream TTL: stream=%s error=%s",
                stream_name,
                e,
            )
