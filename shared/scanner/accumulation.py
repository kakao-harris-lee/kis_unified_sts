"""Accumulation Scanner

Overnight stock scoring for volume accumulation patterns.

Scoring (0-100):
- OBV Trend (40 pts): Rising OBV while price flat/narrow range
- RVOL Buildup (30 pts): 5-day avg volume rising vs 20-day avg
- Price Compression (20 pts): Narrow price range (ATR shrinking)
- Relative Strength (10 pts): Stock holding up vs market average

Usage:
    scanner = AccumulationScanner(min_score=60)
    candidates = await scanner.run()
    for c in candidates:
        print(f"{c.code} {c.name}: {c.score}")
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

import clickhouse_connect
import numpy as np
import pandas as pd
import redis

from shared.indicators.volume import OBVCalculator

logger = logging.getLogger(__name__)


@dataclass
class AccumulationCandidate:
    """Accumulation pattern candidate with scoring breakdown."""

    code: str
    name: str
    score: int  # 0-100 (combined)
    obv_score: float  # 0-40
    rvol_score: float  # 0-30
    compression_score: float  # 0-20
    strength_score: float  # 0-10
    rvol_ratio: float  # 5-day / 20-day volume ratio
    obv_trend: float  # OBV linear regression slope (normalized)
    price_range_pct: float  # (high - low) / close percentage
    avg_volume_5d: float
    avg_volume_20d: float
    last_close: float
    scan_date: str  # YYYYMMDD

    def to_dict(self):
        return asdict(self)


def _get_redis_client():
    """Get Redis client for publishing results."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def _get_clickhouse_config():
    """Get ClickHouse config from environment."""
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "username": os.getenv("CLICKHOUSE_USER", "default"),
        "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
        "database": "market",
    }


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Calculate Average True Range for price compression scoring.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)

    Returns:
        Array of ATR values
    """
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    # True Range = max of:
    # 1. high - low
    # 2. abs(high - prev_close)
    # 3. abs(low - prev_close)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]  # First value has no previous

    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)

    true_range = np.maximum(tr1, np.maximum(tr2, tr3))

    # ATR = SMA of True Range
    atr = pd.Series(true_range).rolling(window=period, min_periods=1).mean().values
    return atr


def _calculate_obv_score(df: pd.DataFrame) -> tuple[float, float]:
    """Calculate OBV score (0-40) based on trend strength.

    Returns:
        (score, obv_trend): score is 0-40, obv_trend is normalized slope
    """
    if len(df) < 10:
        return 0.0, 0.0

    calculator = OBVCalculator()
    prices = df["close"].tolist()
    volumes = [int(v) for v in df["volume"].tolist()]
    obv_data = calculator.calculate(prices, volumes)
    obv_values = obv_data.obv_values

    # Linear regression on OBV to detect trend
    x = np.arange(len(obv_values))
    y = np.array(obv_values)

    if len(x) < 2:
        return 0.0, 0.0

    # Normalize y to avoid scale issues
    y_mean = np.mean(y)
    if y_mean == 0:
        return 0.0, 0.0

    y_norm = y / y_mean

    # Fit line: y = mx + b
    coeffs = np.polyfit(x, y_norm, 1)
    slope = coeffs[0]

    # Score based on positive slope strength
    # Strong uptrend: slope > 0.02 → 40 pts
    # Weak uptrend: slope > 0.01 → 20 pts
    # Flat/down: slope <= 0 → 0 pts
    if slope > 0.02:
        score = 40.0
    elif slope > 0.01:
        score = 20.0 + (slope - 0.01) / 0.01 * 20.0
    elif slope > 0:
        score = slope / 0.01 * 20.0
    else:
        score = 0.0

    return min(score, 40.0), slope


def _calculate_rvol_score(df: pd.DataFrame) -> tuple[float, float, float, float]:
    """Calculate RVOL score (0-30) based on volume buildup.

    Returns:
        (score, rvol_ratio, avg_5d, avg_20d)
    """
    if len(df) < 20:
        return 0.0, 0.0, 0.0, 0.0

    volumes = df["volume"].values

    avg_5d = np.mean(volumes[-5:])
    avg_20d = np.mean(volumes[-20:])

    if avg_20d == 0:
        return 0.0, 0.0, avg_5d, avg_20d

    rvol_ratio = avg_5d / avg_20d

    # Score based on RVOL ratio
    # Strong buildup: rvol > 1.5 → 30 pts
    # Moderate: rvol > 1.2 → 15-30 pts
    # Weak: rvol > 1.0 → 0-15 pts
    # Below average: rvol < 1.0 → 0 pts
    if rvol_ratio >= 1.5:
        score = 30.0
    elif rvol_ratio >= 1.2:
        score = 15.0 + (rvol_ratio - 1.2) / 0.3 * 15.0
    elif rvol_ratio >= 1.0:
        score = (rvol_ratio - 1.0) / 0.2 * 15.0
    else:
        score = 0.0

    return min(score, 30.0), rvol_ratio, avg_5d, avg_20d


def _calculate_compression_score(df: pd.DataFrame) -> tuple[float, float]:
    """Calculate price compression score (0-20) based on ATR shrinking.

    Returns:
        (score, price_range_pct): score is 0-20, range_pct is recent range
    """
    if len(df) < 14:
        return 0.0, 0.0

    atr = _calculate_atr(df, period=14)

    if len(atr) < 2:
        return 0.0, 0.0

    # Compression: current ATR < previous ATR (shrinking volatility)
    current_atr = atr[-1]
    prev_atr = atr[-2]

    if prev_atr == 0:
        return 0.0, 0.0

    compression_ratio = current_atr / prev_atr

    # Calculate recent price range percentage
    recent_data = df.tail(5)
    high = recent_data["high"].max()
    low = recent_data["low"].min()
    close = df["close"].iloc[-1]

    if close == 0:
        price_range_pct = 0.0
    else:
        price_range_pct = (high - low) / close * 100

    # Score based on compression (lower ratio = tighter range = higher score)
    # Strong compression: ratio < 0.8 → 20 pts
    # Moderate: ratio < 0.9 → 10-20 pts
    # Weak: ratio < 1.0 → 0-10 pts
    # Expanding: ratio >= 1.0 → 0 pts
    if compression_ratio < 0.8:
        score = 20.0
    elif compression_ratio < 0.9:
        score = 10.0 + (0.9 - compression_ratio) / 0.1 * 10.0
    elif compression_ratio < 1.0:
        score = (1.0 - compression_ratio) / 0.1 * 10.0
    else:
        score = 0.0

    return min(score, 20.0), price_range_pct


def _calculate_strength_score(df: pd.DataFrame, market_df: pd.DataFrame) -> float:
    """Calculate relative strength score (0-10) vs market.

    Args:
        df: Stock DataFrame
        market_df: Market index DataFrame (KOSPI 200)

    Returns:
        Relative strength score (0-10)
    """
    if len(df) < 20 or len(market_df) < 20:
        return 0.0

    # Calculate % change over last 20 days
    stock_start = df["close"].iloc[-20]
    stock_end = df["close"].iloc[-1]
    market_start = market_df["close"].iloc[-20]
    market_end = market_df["close"].iloc[-1]

    if stock_start == 0 or market_start == 0:
        return 0.0

    stock_pct = (stock_end - stock_start) / stock_start * 100
    market_pct = (market_end - market_start) / market_start * 100

    relative_strength = stock_pct - market_pct

    # Score based on relative strength
    # Strong outperformance: RS > +5% → 10 pts
    # Moderate: RS > +2% → 5-10 pts
    # Neutral: RS > 0% → 0-5 pts
    # Underperformance: RS < 0% → 0 pts
    if relative_strength >= 5.0:
        score = 10.0
    elif relative_strength >= 2.0:
        score = 5.0 + (relative_strength - 2.0) / 3.0 * 5.0
    elif relative_strength >= 0:
        score = relative_strength / 2.0 * 5.0
    else:
        score = 0.0

    return min(score, 10.0)


class AccumulationScanner:
    """Overnight scanner for volume accumulation patterns."""

    def __init__(
        self,
        db_config: Optional[dict] = None,
        min_score: int = 60,
        lookback_days: int = 30,
    ):
        """Initialize accumulation scanner.

        Args:
            db_config: ClickHouse config dict (optional, uses env if None)
            min_score: Minimum score threshold (0-100)
            lookback_days: Days of data to analyze
        """
        self.db_config = db_config or _get_clickhouse_config()
        self.min_score = min_score
        self.lookback_days = lookback_days

    async def _fetch_daily_candles(
        self, codes: Optional[list[str]] = None
    ) -> dict[str, pd.DataFrame]:
        """Fetch daily candles from ClickHouse.

        Args:
            codes: List of stock codes (None = all stocks)

        Returns:
            Dict mapping code → DataFrame with OHLCV data
        """
        client = clickhouse_connect.get_client(**self.db_config)

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)

        query = """
            SELECT code, date, open, high, low, close, volume, value
            FROM market.daily_candles
            WHERE date >= {start_date:Date}
              AND date <= {end_date:Date}
        """
        params = {
            "start_date": start_date.date() if hasattr(start_date, 'date') else start_date,
            "end_date": end_date.date() if hasattr(end_date, 'date') else end_date,
        }

        if codes:
            # Validate codes to prevent injection
            if not all(isinstance(c, str) and c.isalnum() for c in codes):
                raise ValueError("Invalid stock codes: all codes must be alphanumeric strings")
            query += " AND code IN {codes:Array(String)}"
            params["codes"] = codes

        query += " ORDER BY code, date"

        result = client.query(query, parameters=params)
        rows = result.result_rows

        # Group by code
        data_by_code = {}
        for row in rows:
            code = row[0]
            if code not in data_by_code:
                data_by_code[code] = []
            data_by_code[code].append(
                {
                    "date": row[1],
                    "open": row[2],
                    "high": row[3],
                    "low": row[4],
                    "close": row[5],
                    "volume": row[6],
                    "value": row[7],
                }
            )

        # Convert to DataFrames
        result_dfs = {}
        for code, records in data_by_code.items():
            df = pd.DataFrame(records)
            df = df.sort_values("date").reset_index(drop=True)
            result_dfs[code] = df

        client.close()
        return result_dfs

    async def _get_market_data(self) -> pd.DataFrame:
        """Fetch KOSPI 200 index data for relative strength calculation.

        Returns:
            DataFrame with market index OHLCV data
        """
        # Use KOSPI 200 futures front month as market proxy
        market_code = "A05601"
        data = await self._fetch_daily_candles([market_code])

        if market_code in data:
            return data[market_code]
        else:
            # Return empty DataFrame if market data not available
            logger.warning(f"Market data not found for {market_code}")
            return pd.DataFrame()

    def _score_candidate(
        self, code: str, df: pd.DataFrame, market_df: pd.DataFrame
    ) -> Optional[AccumulationCandidate]:
        """Score a single stock for accumulation pattern.

        Args:
            code: Stock code
            df: Stock OHLCV DataFrame
            market_df: Market index DataFrame

        Returns:
            AccumulationCandidate if sufficient data, else None
        """
        if len(df) < 20:
            return None

        # Calculate individual scores
        obv_score, obv_trend = _calculate_obv_score(df)
        rvol_score, rvol_ratio, avg_5d, avg_20d = _calculate_rvol_score(df)
        compression_score, price_range_pct = _calculate_compression_score(df)
        strength_score = _calculate_strength_score(df, market_df)

        # Combined score
        total_score = int(
            obv_score + rvol_score + compression_score + strength_score
        )

        # Get stock name (placeholder - should fetch from master table)
        name = code

        return AccumulationCandidate(
            code=code,
            name=name,
            score=total_score,
            obv_score=obv_score,
            rvol_score=rvol_score,
            compression_score=compression_score,
            strength_score=strength_score,
            rvol_ratio=rvol_ratio,
            obv_trend=obv_trend,
            price_range_pct=price_range_pct,
            avg_volume_5d=avg_5d,
            avg_volume_20d=avg_20d,
            last_close=df["close"].iloc[-1],
            scan_date=datetime.now().strftime("%Y%m%d"),
        )

    async def scan(
        self, codes: Optional[list[str]] = None, min_score: Optional[int] = None
    ) -> list[AccumulationCandidate]:
        """Scan all stocks for accumulation patterns.

        Args:
            codes: List of stock codes to scan (None = all stocks)
            min_score: Override min_score threshold (None = use instance default)

        Returns:
            List of candidates sorted by score (descending)
        """
        threshold = min_score if min_score is not None else self.min_score

        logger.info(
            f"Starting accumulation scan (min_score={threshold}, "
            f"lookback={self.lookback_days} days)"
        )

        # Fetch market data
        market_df = await self._get_market_data()

        # Fetch stock data
        stock_data = await self._fetch_daily_candles(codes)
        logger.info(f"Fetched data for {len(stock_data)} stocks")

        # Score each stock
        candidates = []
        for code, df in stock_data.items():
            try:
                candidate = self._score_candidate(code, df, market_df)
                if candidate and candidate.score >= threshold:
                    candidates.append(candidate)
            except Exception as e:
                logger.error(f"Error scoring {code}: {e}")
                continue

        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"Scan complete: {len(candidates)} candidates above threshold "
            f"(scanned {len(stock_data)} stocks)"
        )

        return candidates

    REDIS_KEY = "system:accumulation:latest"

    async def publish_candidates(
        self, candidates: list[AccumulationCandidate]
    ) -> None:
        """Publish scan results to Redis.

        Args:
            candidates: List of candidates to publish
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "count": len(candidates),
            "candidates": [c.to_dict() for c in candidates],
        }

        def _sync_publish():
            redis_client = _get_redis_client()
            redis_client.set(self.REDIS_KEY, json.dumps(data))

        await asyncio.to_thread(_sync_publish)
        logger.info(f"Published {len(candidates)} candidates to Redis key: {self.REDIS_KEY}")

    async def run(
        self, codes: Optional[list[str]] = None
    ) -> list[AccumulationCandidate]:
        """Run full scan: scan + publish + notify.

        Args:
            codes: List of stock codes to scan (None = all stocks)

        Returns:
            List of candidates sorted by score
        """
        candidates = await self.scan(codes)

        if candidates:
            await self.publish_candidates(candidates)

            # Optional Telegram notification
            try:
                from services.monitoring.notifier import (
                    TelegramConfig,
                    TelegramNotifier,
                )

                notifier = TelegramNotifier(TelegramConfig())
                top_5 = candidates[:5]
                message = f"📊 Accumulation Scan ({datetime.now().strftime('%Y-%m-%d')})\n\n"
                message += f"Found {len(candidates)} candidates\n\n"
                message += "Top 5:\n"
                for c in top_5:
                    message += f"• {c.code} ({c.name}): {c.score}\n"
                    message += f"  OBV:{c.obv_score:.0f} RVOL:{c.rvol_score:.0f} "
                    message += f"COMP:{c.compression_score:.0f} RS:{c.strength_score:.0f}\n"

                await notifier.send(message)
            except ImportError:
                logger.debug("Telegram notifier not available")
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")

        return candidates


async def main():
    """CLI entry point for testing."""
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    scanner = AccumulationScanner(min_score=60)

    if len(sys.argv) > 1:
        codes = sys.argv[1:]
        logger.info(f"Scanning specific codes: {codes}")
        candidates = await scanner.run(codes)
    else:
        logger.info("Scanning all stocks")
        candidates = await scanner.run()

    print(f"\n{'='*80}")
    print(f"Accumulation Scan Results ({datetime.now().strftime('%Y-%m-%d')})")
    print(f"{'='*80}\n")
    print(f"Found {len(candidates)} candidates\n")

    if candidates:
        print(
            f"{'Code':<10} {'Name':<20} {'Score':>6} {'OBV':>5} {'RVOL':>5} "
            f"{'COMP':>5} {'RS':>4} {'RVol Ratio':>10}"
        )
        print(f"{'-'*80}")
        for c in candidates:
            print(
                f"{c.code:<10} {c.name:<20} {c.score:>6} "
                f"{c.obv_score:>5.0f} {c.rvol_score:>5.0f} "
                f"{c.compression_score:>5.0f} {c.strength_score:>4.0f} "
                f"{c.rvol_ratio:>10.2f}"
            )


if __name__ == "__main__":
    asyncio.run(main())
