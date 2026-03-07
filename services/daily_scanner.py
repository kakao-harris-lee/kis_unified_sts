"""Daily scanner service.

Scans a universe of stock codes and classifies them into watchlists:
  - trend_pullback: uptrend with RSI pullback — buy-the-dip setups
  - momentum_breakout: near multi-day high with rising volume — breakout setups

Publishes results to Redis key ``system:daily_watchlist:latest``.

Usage::

    from services.daily_scanner import DailyScanner, DailyScannerConfig
    config = DailyScannerConfig.from_yaml()
    scanner = DailyScanner(config)
    result = scanner.scan_and_publish(codes)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import ClassVar, Optional

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.db.client import get_clickhouse_client
from shared.db.config import ClickHouseConfig
from shared.exceptions import InfrastructureError
from shared.streaming.client import RedisClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DailyBar:
    """Simplified daily bar for scanner logic."""
    code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class DailyScannerConfig(ServiceConfigBase):
    """Configuration for DailyScanner.

    All thresholds are loaded from ``config/daily_scanner.yaml``.
    """

    _default_config_file: ClassVar[str] = "daily_scanner.yaml"

    # Trend-pullback filter params
    tp_sma_period: int = Field(default=20, description="SMA period for trend detection")
    tp_rsi_period: int = Field(default=14, description="RSI period for pullback detection")
    tp_rsi_max: float = Field(default=45.0, description="Maximum RSI value for pullback zone")
    tp_trend_deviation_pct: float = Field(
        default=5.0, description="Maximum deviation percentage below SMA to consider trend intact"
    )
    tp_min_volume_20d: int = Field(default=500_000, description="Minimum 20-day average volume for liquidity")

    # Momentum-breakout filter params
    mb_high_period: int = Field(default=20, description="Period for N-day high calculation")
    mb_proximity_pct: float = Field(default=5.0, description="Maximum distance below N-day high (percentage)")
    mb_volume_trend_ratio: float = Field(
        default=1.2, description="Required ratio of short-term to long-term volume MA"
    )
    mb_max_extension_pct: float = Field(
        default=15.0, description="Maximum extension above N-day high to avoid overextension"
    )

    # Minimum-edge filter params
    me_atr_period: int = Field(default=14, description="ATR period for volatility measurement")
    me_round_trip_cost: float = Field(default=0.005, description="Round-trip trading cost (slippage + commission)")
    me_min_atr_cost_ratio: float = Field(
        default=2.0, description="Minimum ratio of ATR to round-trip cost for sufficient edge"
    )

    # Redis publish params
    max_watchlist_size: int = Field(default=40, description="Maximum number of stocks per watchlist")
    redis_key: str = Field(
        default="system:daily_watchlist:latest", description="Redis key for publishing watchlist"
    )
    redis_ttl_seconds: int = Field(default=86400, description="TTL for Redis key (seconds)")


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _sma(values: list[float], period: int) -> Optional[float]:
    """Simple moving average of the last ``period`` values.

    Args:
        values: Sequence of floats (oldest → newest).
        period: Lookback window.

    Returns:
        SMA value or ``None`` when fewer than ``period`` data points exist.
    """
    if len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def _rsi(closes: list[float], period: int) -> Optional[float]:
    """Wilder's RSI over the last ``period + 1`` closes.

    Args:
        closes: Sequence of closing prices (oldest → newest).
        period: RSI period (typically 14).

    Returns:
        RSI value in [0, 100] or ``None`` when insufficient data.
    """
    if len(closes) < period + 1:
        return None

    window = closes[-(period + 1):]
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(window)):
        delta = window[i] - window[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(bars: list[DailyBar], period: int) -> Optional[float]:
    """Average True Range over the last ``period`` bars.

    Args:
        bars: Sequence of DailyBar (oldest → newest).
        period: ATR period (typically 14).

    Returns:
        ATR value or ``None`` when fewer than ``period + 1`` bars exist.
    """
    if len(bars) < period + 1:
        return None

    window = bars[-(period + 1):]
    true_ranges: list[float] = []
    for i in range(1, len(window)):
        prev_close = window[i - 1].close
        high = window[i].high
        low = window[i].low
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        true_ranges.append(tr)

    return sum(true_ranges) / period


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class DailyScanner:
    """Scans a stock universe using daily candle data.

    Args:
        config: Scanner configuration. Defaults to ``DailyScannerConfig()``.

    Example::

        scanner = DailyScanner(DailyScannerConfig())
        result = scanner.scan_and_publish(["005930", "000660"])
    """

    def __init__(self, config: Optional[DailyScannerConfig] = None) -> None:
        self.config = config or DailyScannerConfig()

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def filter_trend_pullback(self, code: str, bars: list[DailyBar]) -> bool:
        """Check whether a stock is in an uptrend with an RSI pullback.

        Conditions (all must hold):
        - Sufficient data (≥ max(sma_period, rsi_period+1) bars)
        - Close > SMA(tp_sma_period)  — uptrend confirmed
        - RSI(tp_rsi_period) < tp_rsi_max  — pullback not overbought
        - Average volume over last 20 days ≥ tp_min_volume_20d  — liquidity
        - Close not more than ``tp_trend_deviation_pct``% below SMA  — not broken trend

        Args:
            code: Stock code (for logging).
            bars: Daily bars ordered oldest → newest.

        Returns:
            ``True`` when all conditions pass.
        """
        cfg = self.config
        min_bars = max(cfg.tp_sma_period, cfg.tp_rsi_period + 1)
        if len(bars) < min_bars:
            logger.debug("%s trend_pullback: insufficient bars (%d < %d)", code, len(bars), min_bars)
            return False

        closes = [b.close for b in bars]
        volumes = [b.volume for b in bars]

        sma = _sma(closes, cfg.tp_sma_period)
        rsi = _rsi(closes, cfg.tp_rsi_period)

        if sma is None or rsi is None:
            return False

        current_close = closes[-1]

        # Close must be above SMA — uptrend
        if current_close <= sma:
            logger.debug("%s trend_pullback: close %.2f <= sma %.2f", code, current_close, sma)
            return False

        # RSI must be below threshold — pullback zone
        if rsi >= cfg.tp_rsi_max:
            logger.debug("%s trend_pullback: rsi %.1f >= %.1f", code, rsi, cfg.tp_rsi_max)
            return False

        # Average volume must meet liquidity minimum
        avg_vol = _sma(volumes, min(cfg.tp_sma_period, len(volumes)))
        if avg_vol is None or avg_vol < cfg.tp_min_volume_20d:
            logger.debug("%s trend_pullback: avg_vol %.0f < %d", code, avg_vol or 0, cfg.tp_min_volume_20d)
            return False

        # Close must not have deviated too far below SMA (broken trend guard)
        deviation_pct = (sma - current_close) / sma * 100.0
        if deviation_pct > cfg.tp_trend_deviation_pct:
            logger.debug(
                "%s trend_pullback: deviation %.1f%% > %.1f%%",
                code, deviation_pct, cfg.tp_trend_deviation_pct,
            )
            return False

        logger.debug("%s passes trend_pullback (rsi=%.1f sma=%.2f)", code, rsi, sma)
        return True

    def filter_momentum_breakout(self, code: str, bars: list[DailyBar]) -> bool:
        """Check whether a stock is breaking out near a multi-day high with rising volume.

        Conditions (all must hold):
        - Sufficient data (≥ mb_high_period bars)
        - Close within ``mb_proximity_pct``% of the rolling N-day high
        - Volume MA(5) > Volume MA(20) × mb_volume_trend_ratio  — rising volume
        - Close is not more than ``mb_max_extension_pct``% above the N-day high  — not overextended

        Args:
            code: Stock code (for logging).
            bars: Daily bars ordered oldest → newest.

        Returns:
            ``True`` when all conditions pass.
        """
        cfg = self.config
        if len(bars) < cfg.mb_high_period:
            logger.debug("%s momentum_breakout: insufficient bars (%d < %d)", code, len(bars), cfg.mb_high_period)
            return False

        recent = bars[-cfg.mb_high_period:]
        high_n = max(b.high for b in recent)

        current_close = bars[-1].close
        volumes = [b.volume for b in bars]

        # Close must be within proximity_pct% below the N-day high
        distance_below_pct = (high_n - current_close) / high_n * 100.0
        if distance_below_pct > cfg.mb_proximity_pct:
            logger.debug(
                "%s momentum_breakout: %.1f%% below high_n — too far",
                code, distance_below_pct,
            )
            return False

        # Close must not be more than max_extension_pct% above the N-day high (overextension)
        extension_pct = (current_close - high_n) / high_n * 100.0
        if extension_pct > cfg.mb_max_extension_pct:
            logger.debug(
                "%s momentum_breakout: %.1f%% above high_n — overextended",
                code, extension_pct,
            )
            return False

        # Volume trend: short MA must exceed long MA × ratio
        vol_ma5 = _sma(volumes, 5)
        vol_ma20 = _sma(volumes, min(20, len(volumes)))
        if vol_ma5 is None or vol_ma20 is None or vol_ma20 == 0:
            logger.debug("%s momentum_breakout: insufficient volume history", code)
            return False

        if vol_ma5 < vol_ma20 * cfg.mb_volume_trend_ratio:
            logger.debug(
                "%s momentum_breakout: vol_ma5 %.0f < vol_ma20 %.0f × %.1f",
                code, vol_ma5, vol_ma20, cfg.mb_volume_trend_ratio,
            )
            return False

        logger.debug(
            "%s passes momentum_breakout (high_n=%.2f close=%.2f vol_ma5=%.0f)",
            code, high_n, current_close, vol_ma5,
        )
        return True

    def check_minimum_edge(self, code: str, bars: list[DailyBar]) -> bool:
        """Check whether ATR is large enough to cover round-trip trading costs.

        Condition:
        - ATR(me_atr_period) / close >= me_min_atr_cost_ratio × me_round_trip_cost

        This ensures the typical daily range is at least ``me_min_atr_cost_ratio``×
        the total expected cost (slippage + commission on both legs).

        Args:
            code: Stock code (for logging).
            bars: Daily bars ordered oldest → newest.

        Returns:
            ``True`` when the edge condition is satisfied.
        """
        cfg = self.config
        if len(bars) < cfg.me_atr_period + 1:
            logger.debug(
                "%s minimum_edge: insufficient bars (%d < %d)",
                code, len(bars), cfg.me_atr_period + 1,
            )
            return False

        atr = _atr(bars, cfg.me_atr_period)
        current_close = bars[-1].close

        if atr is None or current_close <= 0:
            return False

        atr_pct = atr / current_close
        required = cfg.me_min_atr_cost_ratio * cfg.me_round_trip_cost

        if atr_pct < required:
            logger.debug(
                "%s minimum_edge: atr_pct=%.3f%% < required=%.3f%%",
                code, atr_pct * 100, required * 100,
            )
            return False

        logger.debug("%s passes minimum_edge (atr_pct=%.3f%%)", code, atr_pct * 100)
        return True

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_daily_bars(self, code: str, lookback_days: int = 60) -> list[DailyBar]:
        """Load daily bars for ``code`` from ClickHouse.

        Args:
            code: Stock code.
            lookback_days: How many calendar days to look back.

        Returns:
            List of ``DailyBar`` ordered oldest → newest. Empty on error.
        """
        try:
            client = get_clickhouse_client()
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)
            candles = client.get_daily_candles(code, start_date, end_date)
            return [
                DailyBar(
                    code=c.code,
                    date=c.date,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    volume=c.volume,
                )
                for c in candles
            ]
        except InfrastructureError as exc:
            logger.warning("Failed to load daily bars for %s: %s", code, exc)
            return []
        except Exception as exc:
            # Catch unexpected errors (e.g., data conversion issues)
            logger.warning("Unexpected error loading daily bars for %s: %s", code, exc, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan_universe(self, codes: list[str]) -> dict[str, list[str]]:
        """Scan all codes and classify into watchlists.

        Each code is evaluated against:
        1. ``check_minimum_edge`` — applied to both strategies as a prerequisite
        2. ``filter_trend_pullback``
        3. ``filter_momentum_breakout``

        A code may appear in both lists.

        Args:
            codes: List of stock codes to evaluate.

        Returns:
            Dictionary with keys ``"trend_pullback"`` and ``"momentum_breakout"``,
            each mapping to a list of passing codes (up to ``max_watchlist_size``).
        """
        # Filter funnel metrics
        total_input = len(codes)
        loaded_count = 0
        min_edge_count = 0
        trend_pullback_raw = 0
        momentum_breakout_raw = 0

        logger.info(f"Starting daily scan on {total_input} stocks")

        trend_pullback: list[str] = []
        momentum_breakout: list[str] = []

        for code in codes:
            bars = self._load_daily_bars(code)
            if not bars:
                logger.debug("Skipping %s — no data", code)
                continue

            loaded_count += 1

            if not self.check_minimum_edge(code, bars):
                logger.debug("Skipping %s — minimum edge not met", code)
                continue

            min_edge_count += 1

            if self.filter_trend_pullback(code, bars):
                trend_pullback.append(code)
                trend_pullback_raw += 1
            if self.filter_momentum_breakout(code, bars):
                momentum_breakout.append(code)
                momentum_breakout_raw += 1

        cfg = self.config

        # Log funnel metrics
        logger.info("=" * 60)
        logger.info("Daily Scanner Filter Funnel:")
        logger.info(f"  Universe (input):        {total_input:>5} stocks")
        logger.info(f"  Data loaded:             {loaded_count:>5} stocks ({loaded_count/total_input*100:.1f}%)")
        logger.info(f"  Minimum edge passed:     {min_edge_count:>5} stocks ({min_edge_count/total_input*100:.1f}%)")
        logger.info(f"  Trend pullback (raw):    {trend_pullback_raw:>5} stocks ({trend_pullback_raw/total_input*100:.1f}%)")
        logger.info(f"  Momentum breakout (raw): {momentum_breakout_raw:>5} stocks ({momentum_breakout_raw/total_input*100:.1f}%)")
        logger.info("-" * 60)

        # Truncate to max watchlist size
        final_tp = trend_pullback[: cfg.max_watchlist_size]
        final_mb = momentum_breakout[: cfg.max_watchlist_size]

        logger.info(f"  Final trend_pullback:    {len(final_tp):>5} stocks (max={cfg.max_watchlist_size})")
        logger.info(f"  Final momentum_breakout: {len(final_mb):>5} stocks (max={cfg.max_watchlist_size})")
        logger.info("=" * 60)

        return {
            "trend_pullback": final_tp,
            "momentum_breakout": final_mb,
        }

    def scan_and_publish(self, codes: list[str]) -> dict[str, list[str]]:
        """Scan universe and publish results to Redis.

        Publishes a JSON payload to ``config.redis_key`` with TTL
        ``config.redis_ttl_seconds``.

        Args:
            codes: List of stock codes to evaluate.

        Returns:
            Same dictionary as :meth:`scan_universe`.
        """
        result = self.scan_universe(codes)

        try:
            redis = RedisClient.get_client()
            payload = {
                "timestamp": date.today().isoformat(),
                "strategies": result,
                "counts": {k: len(v) for k, v in result.items()},
            }
            redis.set(
                self.config.redis_key,
                json.dumps(payload, ensure_ascii=False),
                ex=self.config.redis_ttl_seconds,
            )
            logger.info(
                "Published daily watchlist: trend_pullback=%d momentum_breakout=%d",
                len(result["trend_pullback"]),
                len(result["momentum_breakout"]),
            )
        except InfrastructureError as exc:
            logger.warning("Failed to publish watchlist to Redis: %s", exc)
        except Exception as exc:
            # Catch unexpected errors (e.g., JSON serialization issues)
            logger.warning("Unexpected error publishing watchlist: %s", exc, exc_info=True)

        return result
