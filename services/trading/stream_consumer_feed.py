"""StreamConsumerFeed — a MarketDataSource backed by the Redis tick stream.

Reads the ticks the market-ingest daemon publishes to ``market:ticks`` /
``raw_data``, keeps an in-memory price cache, and (when given an indicator
engine) pushes each tick to it — so the orchestrator can consume the tick
stream instead of owning the KIS WebSocket feed (M1c). Drop-in for
``MarketDataProvider``'s ``data_source``: implements ``get_current_price`` plus
the optional ``supports_instant_read`` / ``get_health_status`` hooks.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _decode(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return None if value is None else str(value)


def _parse_entry_fields(
    fields: dict[Any, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Parse a tick-stream entry into ``(symbol, price_dict)``.

    Inverse of ``TickStreamPublisher._build_fields``: rebuilds the dict shape
    the KIS feeds' ``get_current_price`` returns (``code``/``close``/``open``/
    ``high``/``low``/``volume``/``timestamp`` + optional ``volume_is_cumulative``).
    Returns ``None`` when the entry has no usable symbol or price.
    """
    g: dict[str, str | None] = {}
    for raw_key, raw_value in fields.items():
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        g[key] = _decode(raw_value)

    symbol = g.get("symbol") or g.get("code")
    if not symbol:
        return None

    close_raw = g.get("close") or g.get("current_price") or g.get("price")
    if close_raw is None:
        return None
    try:
        close = float(close_raw)
    except (TypeError, ValueError):
        return None

    price: dict[str, Any] = {"code": symbol, "close": close}
    for key in ("open", "high", "low"):
        if g.get(key) is not None:
            try:  # noqa: SIM105
                price[key] = float(g[key])
            except (TypeError, ValueError):
                pass
    if g.get("volume") is not None:
        try:  # noqa: SIM105
            price["volume"] = int(float(g["volume"]))
        except (TypeError, ValueError):
            pass
    if g.get("volume_is_cumulative") is not None:
        price["volume_is_cumulative"] = str(g["volume_is_cumulative"]).lower() == "true"
    try:
        price["timestamp"] = (
            float(g["timestamp"]) if g.get("timestamp") else time.time()
        )
    except (TypeError, ValueError):
        price["timestamp"] = time.time()
    return symbol, price


class StreamConsumerFeed:
    """A ``MarketDataSource`` that mirrors the Redis tick stream in memory."""

    def __init__(
        self,
        *,
        redis: Any,
        stream: str,
        indicator_engine: Any | None = None,
        stale_threshold_seconds: float = 30.0,
        xread_block_ms: int = 1000,
        xread_count: int = 200,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.indicator_engine = indicator_engine
        self._stale_threshold = stale_threshold_seconds
        self.xread_block_ms = xread_block_ms
        self.xread_count = xread_count
        self._prices: dict[str, dict[str, Any]] = {}
        self._symbol_tick_ts: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self._last_tick_ts: float | None = None
        self._last_id: str = "$"
        self._running = False

    @property
    def supports_instant_read(self) -> bool:
        return True

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        return dict(self._prices.get(symbol, {}))

    def update_symbols(self, symbols: list[str]) -> None:
        self._subscribed = set(symbols)

    def _apply_entry(self, fields: dict[Any, Any]) -> None:
        parsed = _parse_entry_fields(fields)
        if parsed is None:
            return
        symbol, price = parsed
        self._prices[symbol] = price
        now = time.time()
        self._symbol_tick_ts[symbol] = now
        self._last_tick_ts = now
        if self.indicator_engine is not None:
            self._push_indicator(symbol, price)

    def _push_indicator(self, symbol: str, price: dict[str, Any]) -> None:
        eng = self.indicator_engine
        try:
            raw_vol = float(price.get("volume", 0) or 0)
            seen = getattr(eng, "_last_cumulative_volume", None)
            if isinstance(seen, dict) and symbol not in seen:
                eng.set_volume_baseline(symbol, raw_vol)
            ts = datetime.fromtimestamp(price.get("timestamp", time.time()), UTC)
            eng.on_tick(symbol, price, ts)
        except Exception:
            logger.exception("indicator on_tick failed symbol=%s", symbol)

    def get_staleness_seconds(self) -> float | None:
        if self._last_tick_ts is None:
            return None
        return max(0.0, time.time() - self._last_tick_ts)

    def is_healthy(self) -> bool:
        if not self._running:
            return False
        staleness = self.get_staleness_seconds()
        return staleness is not None and staleness < self._stale_threshold

    def get_health_status(self) -> dict[str, Any]:
        now = time.time()
        fresh = sum(
            1
            for ts in self._symbol_tick_ts.values()
            if now - ts < self._stale_threshold
        )
        return {
            "running": self._running,
            "connected": self._running,
            "staleness_seconds": self.get_staleness_seconds(),
            "symbol_count": len(self._subscribed) or len(self._symbol_tick_ts),
            "fresh_symbol_count": fresh,
            "stale_symbol_count": max(0, len(self._symbol_tick_ts) - fresh),
            "last_tick_ts": self._last_tick_ts,
            "is_healthy": self.is_healthy(),
        }
