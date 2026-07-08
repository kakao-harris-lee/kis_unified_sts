"""MarketContextReplay — replay historical 1-minute bar data as MarketContext.

Usage::

    replay = MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=macro,
        scheduled_events=[],
        contract_spec=spec,
    )
    for ctx in replay.iter_contexts():
        signal = setup.check(ctx)
        ...

The DataFrame must have columns:
    timestamp (datetime, tz-aware or naive — naive is treated as KST),
    open, high, low, close, volume.

Bars before index 60 are skipped (warmup period required for ATR computation).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from shared.decision.context import MarketContext, ScheduledEvent
from shared.execution.contract_spec import ContractSpec
from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    backtest_indicator_engine,
)
from shared.macro.base import MacroSnapshot

KST = ZoneInfo("Asia/Seoul")

# Number of leading bars reserved for warmup (ATR, VWAP, etc.)
_WARMUP_BARS: int = 60

# ATR period
_ATR_PERIOD: int = 14

# Stub spread: Phase 3 uses LOB-free simulation; real spread comes in Phase 4.
_STUB_SPREAD_TICKS: float = 1.0


@dataclass
class MarketContextReplay:
    """Replay a historical 1-minute OHLCV DataFrame as a stream of MarketContext.

    Attributes:
        df: DataFrame with columns [timestamp, open, high, low, close, volume].
            ``timestamp`` should be tz-aware (KST) or naive (treated as KST).
        symbol: Instrument symbol string (e.g. "A05603").
        macro_snapshot: Optional overnight macro data passed verbatim into
            every context's ``macro_overnight`` field.
        scheduled_events: List of ScheduledEvent objects to include.
        contract_spec: ContractSpec for the instrument (currently unused
            during replay; available for harness consumption).
    """

    df: pd.DataFrame
    symbol: str
    macro_snapshot: MacroSnapshot | None
    scheduled_events: list[ScheduledEvent]
    contract_spec: ContractSpec
    # Optional per-session macro lookup.  When provided, takes precedence over
    # the single ``macro_snapshot`` for every context (look up by the bar's KST
    # date).  Missing dates fall back to ``macro_snapshot``.
    macro_provider: Callable[[date], MacroSnapshot | None] | None = field(default=None)

    # Regular-session open anchor (KST) stamped onto every yielded MarketContext.
    # Defaults to 08:45 — matching current production (config/market_schedule.yaml
    # ::futures.regular.open after 2026-06-28). IMPORTANT: historical backtests on
    # PRE-2026-06-28 data, when the futures day session actually opened at 09:00,
    # MUST pass market_open_hour=9, market_open_minute=0 — otherwise every setup's
    # open-relative window (minutes_since_open) is shifted 15 min earlier and the
    # replayed signals no longer match the regime that produced the historical
    # research numbers (e.g. Setup A / Setup D OOS Sharpe were computed at 09:00).
    market_open_hour: int = 8
    market_open_minute: int = 45

    # Drop bars with volume < min_volume before replay. Legacy KOSPI200 futures
    # datasets can carry phantom ``volume=2`` prints at recurring clock times
    # every day (see docs/runbooks/phase3-verification.md
    # §4). With ``min_volume=30`` the bimodal distribution is cleaned up
    # (26% of rows dropped, anomalous >2% 1-min moves cut 17x to 0.28%).
    # Zero = no filter (backward compatible with existing tests).
    min_volume: int = 0

    # Computed at construction time; None until first iter_contexts() call
    _atr_series: np.ndarray | None = None
    _atr_90th: float | None = None

    def __post_init__(self) -> None:
        if self.min_volume > 0:
            before = len(self.df)
            self.df = self.df[self.df["volume"] >= self.min_volume].reset_index(
                drop=True
            )
            dropped = before - len(self.df)
            if dropped > 0:
                import logging

                logging.getLogger(__name__).info(
                    "min_volume=%d filter dropped %d/%d bars (%.1f%%)",
                    self.min_volume,
                    dropped,
                    before,
                    100 * dropped / before,
                )
        self._validate_df()
        self._precompute()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_df(self) -> None:
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        # Data-quality sanity: if >2% of 1-min bars have >2% return, the
        # data is probably reconstructed from mis-aggregated ticks or
        # contract-stitched without price adjustment. Any Setup A
        # evaluation on such data will be noise, not signal.
        import logging
        import warnings

        log = logging.getLogger(__name__)
        df = self.df
        if len(df) >= 100:
            ret = df["close"].pct_change().abs()
            big = (ret > 0.02).sum()
            big_pct = 100 * big / len(df)
            max_ret = ret.max()
            if big_pct > 2.0 or max_ret > 0.10:
                msg = (
                    f"DataFrame has suspect quality: "
                    f"{big_pct:.1f}% of 1-min bars move >2% "
                    f"(max single-bar move {max_ret:.1%}). Typical clean "
                    f"KOSPI200 futures data is <0.5%. Backtest numbers on "
                    f"this data are unreliable; regenerate the Parquet dataset "
                    f"or filter corrupted bars before trusting Optuna/WF "
                    f"results."
                )
                log.warning(msg)
                warnings.warn(msg, stacklevel=2)

    # ------------------------------------------------------------------
    # Pre-computation (runs once at construction time)
    # ------------------------------------------------------------------

    def _precompute(self) -> None:
        """Compute ATR series and 90th-percentile ATR over the full DataFrame.

        The ATR math is delegated to the backtest-convention indicator engine
        (``atr_partial``: TR seed high-low at bar 0, partial-window means —
        the replay's historical convention, bit-identical; pinned by
        ``tests/unit/backtest/test_indicator_delegation_golden.py``). The ATR
        at bar ``i`` uses only bars ``<= i`` (trailing windows, no look-ahead);
        ``atr_90th_percentile`` is intentionally a fixed full-series reference,
        unchanged from the pre-delegation behavior.
        """
        df = self.df
        if len(df) < 2:
            # Not enough data — fill with zeros; harness will yield nothing anyway.
            self._atr_series = np.zeros(len(df))
            self._atr_90th = 0.0
            return

        window = OHLCVWindow.from_sequences(
            open=df["open"].to_numpy(dtype=float),
            high=df["high"].to_numpy(dtype=float),
            low=df["low"].to_numpy(dtype=float),
            close=df["close"].to_numpy(dtype=float),
            volume=df["volume"].to_numpy(dtype=float),
        )
        self._atr_series = (
            backtest_indicator_engine()
            .compute(
                IndicatorSpec.create("atr_partial", {"period": _ATR_PERIOD}),
                window,
            )
            .series["value"]
        )
        # 90th percentile over the entire series (as a fixed reference)
        self._atr_90th = float(np.nanpercentile(self._atr_series, 90))

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_kst(ts: pd.Timestamp) -> pd.Timestamp:
        """Make a Timestamp timezone-aware in KST."""
        if ts.tzinfo is None:
            return ts.tz_localize(KST)
        return ts.tz_convert(KST)

    @staticmethod
    def _session_date(ts: pd.Timestamp) -> date:
        """Return the trading session date (KST date of the bar)."""
        return ts.date()

    # ------------------------------------------------------------------
    # Iterator
    # ------------------------------------------------------------------

    def iter_contexts(self) -> Iterator[MarketContext]:
        """Yield a MarketContext for each bar from index _WARMUP_BARS onward.

        Skips the first ``_WARMUP_BARS`` bars (index 0..59) so that all
        computed values (ATR, VWAP, etc.) are based on at least 60 bars of
        history.

        For each bar at index ``i``:
        - ``atr_14``: trailing 14-bar ATR value at index ``i``.
        - ``vwap``: from the session start (day boundary) up to and
          including bar ``i``.
        - ``last_15min_high`` / ``last_15min_low``: max/min of the last 15
          bars' high/low (i-14..i inclusive).
        - ``today_open``: open of the first bar of the same session date.
        - ``prev_close``: close of the last bar of the previous session date.
        - ``current_spread_ticks``: stubbed at ``_STUB_SPREAD_TICKS`` (1.0).
        - ``atr_90th_percentile``: fixed 90th percentile over the full series.
        """
        df = self.df
        n = len(df)
        if n <= _WARMUP_BARS:
            return  # nothing to yield

        # Pre-extract arrays for fast access
        ts_col: pd.Series = df["timestamp"]
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        volumes = df["volume"].to_numpy(dtype=float)
        atr_arr = self._atr_series  # type: ignore[assignment]
        atr_90th = self._atr_90th

        # Build session-boundary index: for each bar, record its session date
        # and the index of the first bar in that session.
        session_dates: list[date] = []
        session_start_idx: list[int] = []

        current_date: date | None = None
        current_start: int = 0
        for i in range(n):
            ts_raw = ts_col.iloc[i]
            ts_kst = self._ensure_kst(pd.Timestamp(ts_raw))
            d = self._session_date(ts_kst)
            if d != current_date:
                current_date = d
                current_start = i
            session_dates.append(d)
            session_start_idx.append(current_start)

        # Build prev_close lookup: for each session date, what is the last
        # close of the previous session?  Use None if there is no prev session.
        date_to_last_close: dict[date, float] = {}
        last_d: date | None = None
        last_close: float | None = None
        for i in range(n):
            d = session_dates[i]
            if last_d is not None and d != last_d:
                # Record the last close of last_d
                date_to_last_close[d] = last_close  # type: ignore[assignment]
            last_d = d
            last_close = closes[i]

        # Iterate from warmup boundary
        for i in range(_WARMUP_BARS, n):
            ts_raw = ts_col.iloc[i]
            ts_kst = self._ensure_kst(pd.Timestamp(ts_raw))

            d = session_dates[i]
            sess_start = session_start_idx[i]

            # today_open: open of first bar in this session
            today_open = opens[sess_start]

            # prev_close: last close of previous session
            prev_close_val = date_to_last_close.get(d)
            if prev_close_val is None:
                # No previous session data; skip this bar (can't compute gap)
                continue

            # VWAP: from session start to i (inclusive)
            sess_slice_h = highs[sess_start : i + 1]
            sess_slice_l = lows[sess_start : i + 1]
            sess_slice_c = closes[sess_start : i + 1]
            sess_slice_v = volumes[sess_start : i + 1]
            typical_price = (sess_slice_h + sess_slice_l + sess_slice_c) / 3.0
            total_vol = sess_slice_v.sum()
            if total_vol > 0:
                vwap = float((typical_price * sess_slice_v).sum() / total_vol)
            else:
                vwap = float(closes[i])

            # last_15min_high / last_15min_low: PRIOR 15 bars (i-15..i-1)
            # — exclude the current bar so Setup C's breakout condition
            # ``current_price > last_15min_high`` can actually be true
            # (if we included bar i, high[i] >= close[i] = current_price
            # would make the strict inequality unreachable).
            start_15 = max(0, i - 15)
            if start_15 < i:
                last_15min_high = float(highs[start_15:i].max())
                last_15min_low = float(lows[start_15:i].min())
            else:
                # No prior bars available — use current as a safe fallback.
                last_15min_high = float(highs[i])
                last_15min_low = float(lows[i])

            # ATR at this bar
            atr_14 = float(atr_arr[i])

            if self.macro_provider is not None:
                macro = self.macro_provider(d)
                if macro is None:
                    macro = self.macro_snapshot
            else:
                macro = self.macro_snapshot

            ctx = MarketContext(
                now=ts_kst.to_pydatetime(),
                symbol=self.symbol,
                current_price=float(closes[i]),
                prev_close=float(prev_close_val),
                today_open=float(today_open),
                vwap=vwap,
                atr_14=atr_14,
                atr_90th_percentile=float(atr_90th),  # type: ignore[arg-type]
                last_15min_high=last_15min_high,
                last_15min_low=last_15min_low,
                current_spread_ticks=_STUB_SPREAD_TICKS,
                macro_overnight=macro,
                scheduled_events=list(self.scheduled_events),
                market_open_hour=self.market_open_hour,
                market_open_minute=self.market_open_minute,
            )
            yield ctx
