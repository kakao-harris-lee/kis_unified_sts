"""StreamConsumerFeed — a MarketDataSource backed by the Redis tick stream.

Reads the ticks the market-ingest daemon publishes to ``market:ticks`` /
``raw_data``, keeps an in-memory price cache, and (when given an indicator
engine) pushes each tick to it — so the orchestrator can consume the tick
stream instead of owning the KIS WebSocket feed (M1c). Drop-in for
``MarketDataProvider``'s ``data_source``: implements ``get_current_price`` plus
the optional ``supports_instant_read`` / ``get_health_status`` hooks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from shared.models.stream_models import MarketTickMessage
from shared.streaming.audit import RateLimitedLog, format_audit_kv
from shared.streaming.codec import StreamDecodeError, decode

logger = logging.getLogger(__name__)

_READ_ERROR_SLEEP_SECONDS = 0.5


def _parse_entry_fields(
    fields: dict[Any, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Parse a tick-stream entry into ``(symbol, price_dict)``.

    Inverse of ``TickStreamPublisher._build_fields``: rebuilds the dict shape
    the KIS feeds' ``get_current_price`` returns (``code``/``close``/``open``/
    ``high``/``low``/``volume``/``timestamp`` + optional ``volume_is_cumulative``
    and the optional top-of-book fields).
    Returns ``None`` when the entry has no usable symbol or price.
    """
    try:
        tick = decode(
            MarketTickMessage,
            fields,
            legacy_adapter=MarketTickMessage.from_legacy_fields,
        )
    except StreamDecodeError:
        return None
    return tick.symbol, tick.to_price_dict()


class StreamConsumerFeed:
    """A ``MarketDataSource`` that mirrors the Redis tick stream in memory."""

    def __init__(
        self,
        *,
        redis: Any,
        stream: str,
        indicator_engine: Any | None = None,
        tick_callback: Callable[[str, dict[str, Any], datetime], None] | None = None,
        stale_threshold_seconds: float = 30.0,
        xread_block_ms: int = 1000,
        xread_count: int = 200,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.indicator_engine = indicator_engine
        self._tick_callback = tick_callback
        self._stale_threshold = stale_threshold_seconds
        self.xread_block_ms = xread_block_ms
        self.xread_count = xread_count
        self._prices: dict[str, dict[str, Any]] = {}
        self._symbol_tick_ts: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self._last_tick_ts: float | None = None
        # Arrival time of the newest entry that carried a usable top of book —
        # observability only (get_health_status), same clock as
        # ``_last_tick_ts`` so the two ages are comparable.
        self._last_orderbook_ts: float | None = None
        self._aux_symbols_warned = False
        self._last_id: str = "$"
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._xread_error_log = RateLimitedLog()

    @property
    def supports_instant_read(self) -> bool:
        return True

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        return dict(self._prices.get(symbol, {}))

    def update_symbols(
        self, symbols: list[str], auxiliary_symbols: list[str] | None = None
    ) -> None:
        """Record the symbols this consumer cares about.

        ``auxiliary_symbols`` exists for signature parity with
        ``KIS*PriceFeed.update_symbols``: the WS feeds subscribe to the extra
        symbols, but a stream consumer only ever sees what the *producer*
        subscribed to and published. Passing it is therefore not an error but
        also not a subscription — warn once so a missing cross-asset quote is
        traceable to this, and see the producer (market_ingest /
        orchestrator) to actually add the symbol.
        """
        self._subscribed = set(symbols)
        if auxiliary_symbols and not self._aux_symbols_warned:
            self._aux_symbols_warned = True
            logger.warning(
                "stream feed ignores auxiliary_symbols=%s (stream=%s): only "
                "symbols the producer publishes are available; subscribe them "
                "on the producer instead",
                list(auxiliary_symbols),
                self.stream,
            )

    def get_orderbook_snapshot(self, symbol: str) -> dict[str, Any]:
        """Return the cached top of book, or ``{}`` when none is known.

        Contract-identical to ``KISFuturesPriceFeed.get_orderbook_snapshot``:
        same key set (``code``/``timestamp`` + ``bid_price_1``/``bid_qty_1``/
        ``ask_price_1``/``ask_qty_1``/``spread``), same
        "both sides must be positive" precondition, and ``spread`` derived
        from bid/ask when the producer did not carry it. ``timestamp`` is the
        producer's tick time, not our arrival time, so a downstream freshness
        check measures the market event.

        Caveat: the cached dict is the producer's *merged* snapshot (trade
        tick fields overwrite orderbook fields of the same name), so
        ``timestamp`` tracks the newest tick of either kind — the same
        semantics as the WS feed's own fallback branch, and one step looser
        than its primary branch, which keeps the orderbook tick's own time.
        """
        price = self._prices.get(symbol)
        if not price:
            return {}
        bid = price.get("bid_price_1")
        ask = price.get("ask_price_1")
        if bid is None or ask is None or float(bid) <= 0 or float(ask) <= 0:
            return {}
        snapshot: dict[str, Any] = {
            "code": price.get("code", symbol),
            "bid_price_1": float(bid),
            "bid_qty_1": float(price.get("bid_qty_1") or 0.0),
            "ask_price_1": float(ask),
            "ask_qty_1": float(price.get("ask_qty_1") or 0.0),
            "spread": (
                float(price["spread"])
                if price.get("spread") is not None
                else float(ask) - float(bid)
            ),
            "timestamp": price.get("timestamp"),
        }
        return snapshot

    def set_tick_callback(
        self, callback: Callable[[str, dict[str, Any], datetime], None] | None
    ) -> None:
        """Register a per-tick callback (mirrors ``KIS*PriceFeed.set_tick_callback``).

        When set, each tick invokes ``callback(symbol, price_dict, ts)`` and the
        built-in indicator push is skipped — the callback owns per-tick processing.
        """
        self._tick_callback = callback

    def _apply_entry(self, fields: dict[Any, Any]) -> None:
        parsed = _parse_entry_fields(fields)
        if parsed is None:
            return
        symbol, price = parsed
        self._prices[symbol] = price
        now = time.time()
        self._symbol_tick_ts[symbol] = now
        self._last_tick_ts = now
        if price.get("bid_price_1") and price.get("ask_price_1"):
            self._last_orderbook_ts = now
        if self._tick_callback is not None:
            ts = datetime.fromtimestamp(price.get("timestamp", time.time()), UTC)
            try:
                self._tick_callback(symbol, price, ts)
            except Exception:
                logger.exception("tick_callback failed symbol=%s", symbol)
        elif self.indicator_engine is not None:
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
            # None until an entry carrying a usable top of book arrives. A
            # stream whose ticks are trade-only reports a fresh
            # `staleness_seconds` and a null orderbook age — the pair is what
            # tells an operator the orderbook path is the dark one.
            "orderbook_age_seconds": (
                None
                if self._last_orderbook_ts is None
                else max(0.0, now - self._last_orderbook_ts)
            ),
            "is_healthy": self.is_healthy(),
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._read_loop())
        await asyncio.sleep(0)  # yield so _read_loop reaches its first xread

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:  # noqa: SIM105
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _read_loop(self) -> None:
        while self._running:
            try:
                resp = await self.redis.xread(
                    {self.stream: self._last_id},
                    count=self.xread_count,
                    block=self.xread_block_ms,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self._xread_error_log.exception(
                    logger,
                    format_audit_kv(
                        event="tick_stream_read_error",
                        stream=self.stream,
                        sleep_seconds=_READ_ERROR_SLEEP_SECONDS,
                    ),
                )
                await asyncio.sleep(_READ_ERROR_SLEEP_SECONDS)
                continue
            self._xread_error_log.reset()
            if not resp:
                continue
            for _stream, entries in resp:
                for entry_id, fields in entries:
                    self._last_id = (
                        entry_id.decode()
                        if isinstance(entry_id, bytes)
                        else str(entry_id)
                    )
                    self._apply_entry(fields)
