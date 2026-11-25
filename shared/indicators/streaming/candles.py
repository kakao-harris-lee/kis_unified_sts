"""Candle accumulation primitives for the streaming indicator engine."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class Candle:
    """Completed 1-minute candle."""

    open: float
    high: float
    low: float
    close: float
    volume: float
    minute: int  # minute boundary (e.g. 930 for 09:30)


class CandleAccumulator:
    """Accumulates sub-second ticks into 1-minute candles for a single symbol."""

    def __init__(self, maxlen: int = 100):
        self.candles: deque[Candle] = deque(maxlen=maxlen)
        # Monotonic count of completed candles ever appended. `len(self.candles)`
        # saturates at `maxlen`, so it cannot be used to invalidate downstream
        # indicator caches once the deque is full — the cache would freeze.
        self.total_appended: int = 0
        self._current_minute: int | None = None
        self._open: float = 0.0
        self._high: float = 0.0
        self._low: float = 0.0
        self._close: float = 0.0
        self._volume: float = 0.0
        self.last_tick_ts: datetime | None = None

    def add_completed(self, candle: Candle) -> None:
        """Append a completed candle and bump the monotonic counter.

        All append paths (live tick finalize + backtest seed) must go through
        here so `total_appended` stays accurate for cache invalidation.
        """
        self.candles.append(candle)
        self.total_appended += 1

    def on_tick(
        self,
        close: float,
        high: float | None = None,
        low: float | None = None,
        volume: float = 0.0,
        timestamp: datetime | None = None,
    ) -> Candle | None:
        """Process a tick. Returns a completed candle when the minute boundary changes."""
        # tz-aware UTC by default. Caller-supplied ts MAY be tz-naive; we
        # store as-is but the staleness guard normalizes both sides.
        ts = timestamp or datetime.now(UTC)
        self.last_tick_ts = ts
        minute = ts.hour * 100 + ts.minute

        h = high if high is not None else close
        lo = low if low is not None else close

        if self._current_minute is None:
            # First tick
            self._current_minute = minute
            self._open = close
            self._high = h
            self._low = lo
            self._close = close
            self._volume = volume
            return None

        if minute != self._current_minute:
            # Finalize previous candle
            completed = Candle(
                open=self._open,
                high=self._high,
                low=self._low,
                close=self._close,
                volume=self._volume,
                minute=self._current_minute,
            )
            self.add_completed(completed)

            # Start new candle
            self._current_minute = minute
            self._open = close
            self._high = h
            self._low = lo
            self._close = close
            self._volume = volume
            return completed

        # Same minute — update running candle
        self._high = max(self._high, h)
        self._low = min(self._low, lo)
        self._close = close
        self._volume += volume
        return None

    @property
    def latest_close(self) -> float | None:
        """Freshest close price: in-progress candle close, or last completed candle.

        Returns ``None`` when no tick has ever been received (``_current_minute``
        is None). This is the preferred price source for the strategy daemon
        because it reflects the most recent tick, not just the last *completed*
        minute boundary.
        """
        if self._current_minute is None:
            return None
        return self._close


class MultiTimeframeCandleAccumulator:
    """Aggregates 1-minute candles into higher timeframe candles (e.g., 5-minute).

    Called each time a new 1-minute candle is completed. Accumulates into
    N-minute candles based on configurable timeframe.
    """

    def __init__(self, timeframe_minutes: int = 5, maxlen: int = 250):
        """Initialize multi-timeframe accumulator.

        Args:
            timeframe_minutes: Target candle timeframe in minutes.
            maxlen: Maximum number of completed candles to retain.
        """
        self.timeframe = timeframe_minutes
        self.candles: deque[Candle] = deque(maxlen=maxlen)
        # See CandleAccumulator.total_appended — same cache-invalidation reason.
        self.total_appended: int = 0
        self._buffer: list[Candle] = []
        self._current_bucket: int | None = None

    def add_completed(self, candle: Candle) -> None:
        """Append a completed N-min candle and bump the monotonic counter."""
        self.candles.append(candle)
        self.total_appended += 1

    def _get_bucket(self, minute: int) -> int:
        """Compute the time bucket for a given HHMM minute value.

        E.g., with timeframe=5: minute 932 → bucket 930, minute 935 → bucket 935.
        """
        hours = minute // 100
        mins = minute % 100
        total = hours * 60 + mins
        bucket_total = (total // self.timeframe) * self.timeframe
        return (bucket_total // 60) * 100 + (bucket_total % 60)

    def on_1m_candle(self, candle: Candle) -> Candle | None:
        """Process a completed 1-minute candle.

        Returns a completed N-minute candle when the time bucket changes.
        """
        bucket = self._get_bucket(candle.minute)

        if self._current_bucket is None:
            self._current_bucket = bucket
            self._buffer.append(candle)
            return None

        if bucket != self._current_bucket:
            # Finalize previous bucket
            completed = self._finalize_buffer()

            # Start new bucket
            self._current_bucket = bucket
            self._buffer = [candle]

            return completed

        # Same bucket — accumulate
        self._buffer.append(candle)
        return None

    def _finalize_buffer(self) -> Candle | None:
        """Combine buffered 1-min candles into a single higher-TF candle."""
        if not self._buffer:
            return None

        completed = Candle(
            open=self._buffer[0].open,
            high=max(c.high for c in self._buffer),
            low=min(c.low for c in self._buffer),
            close=self._buffer[-1].close,
            volume=sum(c.volume for c in self._buffer),
            minute=self._current_bucket or 0,
        )
        self.add_completed(completed)
        return completed

    def flush(self) -> Candle | None:
        """Force-finalize any buffered candles (e.g., at session end)."""
        if not self._buffer:
            return None
        completed = self._finalize_buffer()
        self._buffer = []
        self._current_bucket = None
        return completed
