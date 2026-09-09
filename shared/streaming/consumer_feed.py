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
from shared.streaming.codec import (
    StreamDecodeError,
    decode,
    normalize_stream_fields,
)

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
        seed_latest: bool = False,
        seed_count: int = 50,
        seed_max_age_seconds: float | None = None,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.indicator_engine = indicator_engine
        self._tick_callback = tick_callback
        self._stale_threshold = stale_threshold_seconds
        self.xread_block_ms = xread_block_ms
        self.xread_count = xread_count
        self.seed_latest = seed_latest
        self.seed_count = seed_count
        self.seed_max_age_seconds = seed_max_age_seconds
        self._prices: dict[str, dict[str, Any]] = {}
        # Last two-sided book seen per symbol, mirroring
        # ``KISFuturesPriceFeed._orderbooks``: a later quote-less entry (a
        # producer cold start, a cutover handoff) must not erase a book we
        # know. Its age is bounded downstream by ``quote_ts``, which is the
        # fail-closed path — an erased book blocks on "unavailable", which
        # reads as a market condition rather than a data gap.
        self._orderbooks: dict[str, dict[str, Any]] = {}
        self._symbol_tick_ts: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self._auxiliary: set[str] = set()
        self._last_tick_ts: float | None = None
        # Event time (producer clock) of the newest book we hold — the same
        # value the gate reads, so a health snapshot and a `quote_stale` block
        # cannot disagree. Deliberately NOT arrival time: a frozen book merged
        # onto fresh trades arrives constantly while its quote ages.
        self._last_orderbook_ts: float | None = None
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

        ``auxiliary_symbols`` mirrors ``KIS*PriceFeed.update_symbols``. A stream
        consumer subscribes to nothing, so whether an auxiliary symbol is
        actually available depends on the PRODUCER: the monolithic orchestrator
        passes its cross-asset reference symbol to the WS feed and republishes
        every tick it receives, so pre-cutover the symbol is on the stream;
        ``services/market_ingest`` subscribes only its trading symbol, so
        post-cutover it is not. Recorded either way so seeding covers it, and
        left to the caller (which knows the deployment) to warn.
        """
        self._subscribed = set(symbols)
        self._auxiliary = set(auxiliary_symbols or [])

    def get_orderbook_snapshot(self, symbol: str) -> dict[str, Any]:
        """Return the last two-sided book seen, or ``{}`` when none is known.

        Contract-identical to the PRIMARY branch of
        ``KISFuturesPriceFeed.get_orderbook_snapshot``: same key set
        (``code``/``timestamp`` + ``bid_price_1``/``bid_qty_1``/``ask_price_1``/
        ``ask_qty_1``/``spread``), same "both sides must be positive"
        precondition, and ``timestamp`` is the ORDERBOOK tick's own event time —
        ``quote_ts`` on the wire — so a freshness check downstream bounds the
        age of the book and not of the last print. Entries written before
        ``quote_ts`` existed fall back to the entry timestamp, which is the old
        (looser) behaviour rather than a hard failure.
        """
        cached = self._orderbooks.get(symbol)
        return dict(cached) if cached else {}

    @staticmethod
    def _orderbook_from_price(symbol: str, price: dict[str, Any]) -> dict[str, Any]:
        """Build the WS-shaped book from a decoded entry, or ``{}``."""
        bid = price.get("bid_price_1")
        ask = price.get("ask_price_1")
        if bid is None or ask is None:
            return {}
        try:
            bid_f = float(bid)
            ask_f = float(ask)
        except (TypeError, ValueError):
            return {}
        if bid_f <= 0 or ask_f <= 0:
            return {}
        spread = price.get("spread")
        quote_ts = price.get("quote_ts", price.get("timestamp"))
        return {
            "code": price.get("code", symbol),
            "bid_price_1": bid_f,
            "bid_qty_1": float(price.get("bid_qty_1") or 0.0),
            "ask_price_1": ask_f,
            "ask_qty_1": float(price.get("ask_qty_1") or 0.0),
            # `spread` is a pure function of bid/ask in the WS feed; derive it
            # when a producer did not carry it so the key set never varies.
            "spread": float(spread) if spread is not None else ask_f - bid_f,
            "timestamp": quote_ts,
        }

    def set_tick_callback(
        self, callback: Callable[[str, dict[str, Any], datetime], None] | None
    ) -> None:
        """Register a per-tick callback (mirrors ``KIS*PriceFeed.set_tick_callback``).

        When set, each tick invokes ``callback(symbol, price_dict, ts)`` and the
        built-in indicator push is skipped — the callback owns per-tick processing.
        """
        self._tick_callback = callback

    def _apply_entry(self, fields: dict[Any, Any], *, seeded: bool = False) -> None:
        parsed = _parse_entry_fields(fields)
        if parsed is None:
            return
        symbol, price = parsed
        if (
            seeded
            and self._subscribed
            and symbol not in self._subscribed
            and symbol not in self._auxiliary
        ):
            return
        self._prices[symbol] = price
        # A live entry is aged from its arrival; a replayed one from the
        # producer's own timestamp, or a cold start would report a 50-entry
        # backlog as if every tick had just landed.
        now = time.time()
        if seeded:
            now = float(price.get("timestamp") or now)
        self._symbol_tick_ts[symbol] = now
        if self._last_tick_ts is None or now > self._last_tick_ts:
            self._last_tick_ts = now
        book = self._orderbook_from_price(symbol, price)
        if book:
            self._orderbooks[symbol] = book
            # Producer event time, not arrival: a frozen book merged onto fresh
            # trades arrives constantly while the quote itself ages.
            quote_ts = book.get("timestamp")
            if quote_ts is not None and (
                self._last_orderbook_ts is None or quote_ts > self._last_orderbook_ts
            ):
                self._last_orderbook_ts = float(quote_ts)
        if seeded:
            # Cache prime, not a live tick: replaying old prints into the
            # volatility baseline or the indicator engine would fabricate
            # history the process never observed.
            return
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
            # Age of the newest BOOK we hold, measured on the producer's clock
            # (`quote_ts`) — the same quantity the order-router's `quote_stale`
            # gate reads, so a block and this snapshot cannot disagree. None
            # until a two-sided book has been seen: a trade-only stream reports
            # a fresh `staleness_seconds` next to a null orderbook age, and that
            # pair is what identifies the orderbook path as the dark one.
            # Consumed by whoever polls the feed (dashboards, tests); the
            # order-router does not currently log a feed heartbeat.
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
        if self.seed_latest:
            await self._seed_from_history()
        self._task = asyncio.create_task(self._read_loop())
        await asyncio.sleep(0)  # yield so _read_loop reaches its first xread

    async def _seed_from_history(self) -> None:
        """Prime the price cache from the tail of the stream before reading.

        The read loop starts at ``$``, so a freshly started consumer is blind
        until the next tick arrives. For the order-router that means the
        send-time gate has no quote for the first signal after a restart and
        blocks it on ``orderbook_unavailable``. Replays the newest
        ``seed_count`` entries oldest-first, for subscribed (and auxiliary)
        symbols only, and leaves ``_last_id`` at ``$`` so the live loop does
        not re-apply them.

        ``seed_max_age_seconds`` bounds what may be replayed at all. Seeding is
        fail-closed on its own rather than leaning on a downstream freshness
        check: a restart after a halt, or on a day-old stream, would otherwise
        hand the router yesterday's book and rely on someone else to reject it.

        Best-effort: a stream that does not exist yet, or a Redis that refuses
        the read, leaves the cache exactly as cold as it was before.
        """
        try:
            entries = await self.redis.xrevrange(self.stream, count=self.seed_count)
        except Exception:
            logger.warning(
                format_audit_kv(
                    event="tick_stream_seed_failed",
                    stream=self.stream,
                    seed_count=self.seed_count,
                ),
                exc_info=True,
            )
            return
        cutoff: float | None = None
        if self.seed_max_age_seconds is not None and self.seed_max_age_seconds > 0:
            cutoff = time.time() - self.seed_max_age_seconds
        applied = 0
        skipped_stale = 0
        for _entry_id, fields in reversed(list(entries or [])):
            if cutoff is not None and self._entry_event_ts(fields) < cutoff:
                skipped_stale += 1
                continue
            self._apply_entry(fields, seeded=True)
            applied += 1
        logger.info(
            format_audit_kv(
                event="tick_stream_seeded",
                stream=self.stream,
                entries_read=len(entries or []),
                entries_applied=applied,
                entries_skipped_stale=skipped_stale,
                max_age_seconds=self.seed_max_age_seconds,
                symbols_cached=len(self._prices),
            )
        )

    @staticmethod
    def _entry_event_ts(fields: dict[Any, Any]) -> float:
        """Producer event time of a raw entry, ``-inf`` when unreadable.

        Prefers ``quote_ts`` (the book's own time) over ``timestamp`` (the trade
        tick's) so an ageing book is judged on the field that ages, and treats
        an unreadable time as infinitely old so it is skipped rather than
        replayed blind.
        """
        raw = normalize_stream_fields(fields)
        for key in ("quote_ts", "timestamp"):
            value = raw.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return float("-inf")

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
