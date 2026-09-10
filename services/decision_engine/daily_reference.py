"""Daily reference (prev_close / today_open) for the futures strategy daemon.

The daemon has no MarketDataProvider, so prev_close comes from — in order —
the ``futures:daily_reference:{symbol}`` Redis read-model published by the
session-start KIS REST prefetch (``shared/streaming/daily_reference.py``), then
the parquet daily bars, then 0.0.  ``today_open`` is captured from the first
observed price of the session.

The Redis source exists because the parquet daily partition only ever held the
*training* symbols (``101S6000`` / ``krx_kospi200f_continuous``, stale since
2026-06-25), never the *trading* symbol — so the parquet path alone left Setup A
permanently blind on ``prev_close``.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from shared.streaming.daily_reference import read_futures_daily_reference

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_MARKET_OPEN = time(9, 0)  # KST — matches MarketContext.market_open_time


class FuturesDailyReference:
    """Provide prev_close (Redis read-model → parquet) + today_open."""

    def __init__(self, *, store: Any, symbol: str, redis: Any | None = None) -> None:
        """Wire the prev_close sources.

        Args:
            store: Market-data store exposing ``get_daily_bars(symbol)``.
            symbol: Trading symbol (e.g. ``A05609``).
            redis: SYNC Redis client for the read-model; ``None`` falls back to
                the parquet path alone (tests, and any caller with no Redis).
        """
        self._store = store
        self._symbol = symbol
        self._redis = redis
        self._today_open: float | None = None
        self._today: date | None = None
        # prev_close is a once-per-day constant, but the decision loop asks for
        # it every tick (~60 s). Cache the resolved value per KST trade date;
        # a non-positive result is NOT cached so a late publish is picked up on
        # the next tick.
        self._prev_close: float = 0.0
        self._prev_close_day: date | None = None
        # Once-per-KST-day log latches. Before these existed the parquet miss
        # emitted one WARNING per tick (830 lines on 2026-09-10).
        self._resolved_log_day: date | None = None
        self._missing_log_day: date | None = None

    def prev_close(self) -> float:
        """Most recent close before today, or 0.0 when no source has it.

        Order: (1) the Redis read-model, accepted only while its ``asof_ts``
        falls on the current KST trade date; (2) the parquet daily bars;
        (3) 0.0. Logs the confirmed source at INFO once per KST day, and the
        both-missing state at WARNING once per KST day.
        """
        today = datetime.now(_KST).date()
        if self._prev_close_day == today and self._prev_close > 0:
            return self._prev_close

        value, source, asof = self._prev_close_from_redis(today)
        if value <= 0:
            value, source, asof = self._prev_close_from_parquet(), "parquet", ""

        if value > 0:
            self._prev_close = value
            self._prev_close_day = today
            if self._resolved_log_day != today:
                self._resolved_log_day = today
                logger.info(
                    "prev_close source=%s symbol=%s value=%s asof=%s",
                    source,
                    self._symbol,
                    value,
                    asof or "-",
                )
        elif self._missing_log_day != today:
            self._missing_log_day = today
            logger.warning(
                "prev_close unavailable for %s: no fresh futures:daily_reference "
                "read-model and no daily bar data — Setup A will skip "
                "(next warning: tomorrow KST)",
                self._symbol,
            )
        return value

    def _prev_close_from_redis(self, today: date) -> tuple[float, str, str]:
        """``(prev_close, source, asof_ts)`` from the read-model, or ``(0.0, "", "")``.

        A reference whose ``asof_ts`` is not on ``today`` (KST) is ignored: the
        key's 24 h TTL outlives a trade date, so a surviving key from the
        previous session must never be read as today's reference.
        """
        if self._redis is None:
            return 0.0, "", ""
        payload = read_futures_daily_reference(self._redis, self._symbol)
        if not payload:
            return 0.0, "", ""
        asof_ts = str(payload.get("asof_ts", ""))
        try:
            asof = datetime.fromisoformat(asof_ts)
        except ValueError:
            logger.debug(
                "prev_close: read-model for %s has an unparseable asof_ts=%r",
                self._symbol,
                asof_ts,
            )
            return 0.0, "", ""
        if asof.tzinfo is None:
            asof = asof.replace(tzinfo=_KST)
        if asof.astimezone(_KST).date() != today:
            logger.debug(
                "prev_close: read-model for %s is stale (asof=%s, today=%s)",
                self._symbol,
                asof_ts,
                today,
            )
            return 0.0, "", ""
        return float(payload["prev_close"]), "redis", asof_ts

    def _prev_close_from_parquet(self) -> float:
        """Most recent daily close STRICTLY BEFORE today, or 0.0 if unavailable.

        IMPORTANT: ``ParquetMarketDataStore.get_daily_bars`` orders ``datetime``
        ASC and ``LIMIT`` takes the HEAD — so we must NOT use ``limit`` to get
        recent bars. Fetch the (small) daily history, drop today's in-progress
        bar (``self._today``, set by ``observe``), and take the tail.

        Diagnostics here are DEBUG: the operator-facing signal is the
        once-per-day WARNING in :meth:`prev_close`, which fires only when the
        Redis read-model is missing too.
        """
        import pandas as pd

        try:
            df = self._store.get_daily_bars(self._symbol)
        except Exception:
            logger.debug(
                "prev_close: failed to read daily bars for %s; returning 0.0",
                self._symbol,
            )
            return 0.0
        if df is None or len(df) == 0 or "close" not in df.columns:
            logger.debug(
                "prev_close: no daily bar data for %s; returning 0.0",
                self._symbol,
            )
            return 0.0
        # Exclude today's (partial) bar so prev_close is yesterday's close.
        dt_col = (
            "datetime"
            if "datetime" in df.columns
            else ("date" if "date" in df.columns else None)
        )
        if self._today is not None and dt_col is not None:
            with contextlib.suppress(Exception):
                df = df[pd.to_datetime(df[dt_col]).dt.date < self._today]
        if len(df) == 0:
            return 0.0
        try:
            return float(df["close"].iloc[-1])
        except (TypeError, ValueError, IndexError):
            return 0.0

    def observe(self, *, price: float, now: datetime) -> None:
        """Record the session's first price as today_open (resets daily).

        Silently no-ops before 09:00 KST so that warmup-seeded prices
        (pre-session closes) cannot poison today_open.  Setup A's own
        ``valid_minutes_min`` guard prevents signals before 09:10 KST, so
        a 0.0 today_open before open is harmless.

        ``now`` must already be KST-aware (the caller — FuturesContextProvider
        — converts UTC→KST before calling here).
        """
        if now.time() < _MARKET_OPEN:
            return
        d = now.date()
        if self._today != d:
            self._today = d
            self._today_open = price

    def today_open(self) -> float:
        """Today's session open (0.0 before the first observe())."""
        return self._today_open if self._today_open is not None else 0.0
