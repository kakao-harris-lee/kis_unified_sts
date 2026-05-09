# Stock Strategy Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign stock trading from screener-driven dynamic universe to static universe with multi-timeframe strategies, achieving Sharpe > 1.0 after costs.

**Architecture:** Phase 1 builds infrastructure (daily candle backfill via pykrx, pre-market daily scanner, orchestrator static universe mode). Phase 2 builds two multi-timeframe strategies (trend_pullback, momentum_breakout) with a unified ATR dynamic exit and cost-aware minimum edge filter.

**Tech Stack:** Python 3.11+, ClickHouse (existing `market.daily_candles` table), pykrx, Redis, existing `shared/strategy/` framework, `shared/backtest/engine.py`

**Design doc:** `docs/plans/2026-02-26-stock-strategy-redesign.md`

---

## Task 1: Daily Candle pykrx Backfill Script

Populate `market.daily_candles` (table already exists in ClickHouse) with 1 year of OHLCV for 50 liquid stocks via pykrx.

**Files:**
- Create: `scripts/data/backfill_daily_pykrx.py`
- Reference: `shared/collector/historical/daily_stock.py` (existing `ensure_daily_candles_table()`, `insert_daily_candles_batch()`)
- Reference: `shared/db/client.py` (`ClickHouseClient.get_daily_candles()`, `insert_daily_candles()`)
- Reference: `shared/db/models.py` (`DailyCandle` dataclass)

**Step 1: Write the backfill script**

```python
#!/usr/bin/env python3
"""Backfill daily candles from pykrx into ClickHouse.

Usage:
    python scripts/data/backfill_daily_pykrx.py [--days 365] [--symbols 005930,000660]
"""
import argparse
import logging
import sys
import time
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Top-50 liquid KOSPI/KOSDAQ stocks for static universe
UNIVERSE_50 = [
    # Top tier (large-cap, KOSPI200 core)
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "207940", "name": "삼성바이오로직스"},
    {"code": "005380", "name": "현대차"},
    {"code": "000270", "name": "기아"},
    {"code": "068270", "name": "셀트리온"},
    {"code": "035420", "name": "NAVER"},
    {"code": "005490", "name": "POSCO홀딩스"},
    {"code": "035720", "name": "카카오"},
    {"code": "051910", "name": "LG화학"},
    # Mid tier
    {"code": "006400", "name": "삼성SDI"},
    {"code": "028260", "name": "삼성물산"},
    {"code": "012330", "name": "현대모비스"},
    {"code": "055550", "name": "신한지주"},
    {"code": "105560", "name": "KB금융"},
    {"code": "034730", "name": "SK"},
    {"code": "003550", "name": "LG"},
    {"code": "066570", "name": "LG전자"},
    {"code": "032830", "name": "삼성생명"},
    {"code": "086790", "name": "하나금융지주"},
    # Bottom tier (theme/volatile)
    {"code": "247540", "name": "에코프로비엠"},
    {"code": "086520", "name": "에코프로"},
    {"code": "373220", "name": "LG에너지솔루션"},
    {"code": "196170", "name": "알테오젠"},
    {"code": "003670", "name": "포스코퓨처엠"},
    {"code": "009150", "name": "삼성전기"},
    {"code": "000810", "name": "삼성화재"},
    {"code": "018260", "name": "삼성에스디에스"},
    {"code": "033780", "name": "KT&G"},
    {"code": "036570", "name": "엔씨소프트"},
    # Additional 20 for expanded universe
    {"code": "003490", "name": "대한항공"},
    {"code": "034020", "name": "두산에너빌리티"},
    {"code": "010130", "name": "고려아연"},
    {"code": "015760", "name": "한국전력"},
    {"code": "017670", "name": "SK텔레콤"},
    {"code": "030200", "name": "KT"},
    {"code": "011200", "name": "HMM"},
    {"code": "024110", "name": "기업은행"},
    {"code": "316140", "name": "우리금융지주"},
    {"code": "259960", "name": "크래프톤"},
    {"code": "010950", "name": "S-Oil"},
    {"code": "009540", "name": "한국조선해양"},
    {"code": "036460", "name": "한국가스공사"},
    {"code": "011170", "name": "롯데케미칼"},
    {"code": "002790", "name": "아모레퍼시픽그룹"},
    {"code": "138040", "name": "메리츠금융지주"},
    {"code": "128940", "name": "한미약품"},
    {"code": "005830", "name": "DB손해보험"},
    {"code": "326030", "name": "SK바이오팜"},
    {"code": "352820", "name": "하이브"},
]


def backfill_daily(days: int = 365, symbols: list[str] | None = None) -> None:
    """Backfill daily candles from pykrx."""
    from pykrx import stock as pykrx_stock

    from shared.collector.historical.daily_stock import (
        ensure_daily_candles_table,
        insert_daily_candles_batch,
    )

    ensure_daily_candles_table()

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    codes = symbols or [s["code"] for s in UNIVERSE_50]
    names = {s["code"]: s["name"] for s in UNIVERSE_50}

    logger.info(f"Backfilling {len(codes)} symbols, {start_str} ~ {end_str}")

    total_rows = 0
    for i, code in enumerate(codes):
        try:
            df = pykrx_stock.get_market_ohlcv(start_str, end_str, code)
            if df.empty:
                logger.warning(f"[{i+1}/{len(codes)}] {code} — no data")
                continue

            rows = []
            for idx, row in df.iterrows():
                date_val = idx.date() if hasattr(idx, "date") else idx
                rows.append((
                    code,
                    date_val,
                    float(row["시가"]),
                    float(row["고가"]),
                    float(row["저가"]),
                    float(row["종가"]),
                    int(row["거래량"]),
                    int(row.get("거래대금", 0)),
                    float(row.get("등락률", 0.0)),
                ))

            inserted = insert_daily_candles_batch(rows)
            total_rows += inserted
            logger.info(
                f"[{i+1}/{len(codes)}] {code} {names.get(code, '')} — "
                f"{inserted} rows inserted"
            )
            time.sleep(0.5)  # pykrx rate limit
        except Exception as e:
            logger.error(f"[{i+1}/{len(codes)}] {code} failed: {e}")

    logger.info(f"Backfill complete: {total_rows} total rows for {len(codes)} symbols")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="Backfill daily candles from pykrx")
    parser.add_argument("--days", type=int, default=365, help="Days to backfill")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated codes")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    backfill_daily(days=args.days, symbols=symbols)


if __name__ == "__main__":
    main()
```

**Step 2: Run the backfill**

Run: `cd /home/deploy/project/kis_unified_sts && .venv/bin/python scripts/data/backfill_daily_pykrx.py --days 365`
Expected: ~50 stocks × ~250 trading days = ~12,500 rows inserted

**Step 3: Verify data**

Run: `clickhouse-client --port 9000 --user default --password '@1tidh6ls6ls' -q "SELECT code, count(*), min(date), max(date) FROM market.daily_candles GROUP BY code ORDER BY code LIMIT 10"`
Expected: Each stock has ~240-250 rows spanning ~1 year

**Step 4: Commit**

```bash
git add scripts/data/backfill_daily_pykrx.py
git commit -m "feat: add pykrx daily candle backfill script for 50-stock universe"
```

---

## Task 2: Daily Scanner Service

Pre-market service that reads daily candles from ClickHouse, applies Layer 1 filters, and publishes a watchlist to Redis.

**Files:**
- Create: `services/daily_scanner.py`
- Create: `config/daily_scanner.yaml`
- Test: `tests/unit/test_daily_scanner.py`

**Step 1: Write the failing test**

```python
"""Tests for DailyScanner Layer 1 filters."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from services.daily_scanner import DailyScanner, DailyScannerConfig, DailyBar


@pytest.fixture
def config():
    return DailyScannerConfig()


@pytest.fixture
def scanner(config):
    return DailyScanner(config)


def _make_bars(closes: list[float], volumes: list[int] | None = None) -> list[DailyBar]:
    """Create N daily bars with given close prices."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    bars = []
    for i in range(n):
        bars.append(DailyBar(
            code="005930",
            date=date(2026, 1, 1 + i),
            open=closes[i] - 100,
            high=closes[i] + 200,
            low=closes[i] - 200,
            close=closes[i],
            volume=volumes[i],
        ))
    return bars


class TestTrendPullbackFilter:
    """Layer 1: trend_pullback — uptrend + pullback."""

    def test_passes_uptrend_pullback(self, scanner):
        # 20 bars trending up, last few pulling back (RSI < 45)
        closes = [50000 + i * 100 for i in range(25)]  # steady uptrend
        closes[-1] = closes[-2] - 500  # small pullback at end
        bars = _make_bars(closes)
        result = scanner.filter_trend_pullback("005930", bars)
        assert result is True

    def test_rejects_downtrend(self, scanner):
        # Price below SMA(20)
        closes = [60000 - i * 200 for i in range(25)]  # downtrend
        bars = _make_bars(closes)
        result = scanner.filter_trend_pullback("005930", bars)
        assert result is False

    def test_rejects_overbought(self, scanner):
        # Strong uptrend but RSI > 45 (no pullback)
        closes = [50000 + i * 300 for i in range(25)]  # steep uptrend, no pullback
        bars = _make_bars(closes)
        result = scanner.filter_trend_pullback("005930", bars)
        assert result is False

    def test_insufficient_data(self, scanner):
        bars = _make_bars([50000] * 10)  # < 20 bars
        result = scanner.filter_trend_pullback("005930", bars)
        assert result is False


class TestMomentumBreakoutFilter:
    """Layer 1: momentum_breakout — near high + volume trend."""

    def test_passes_near_high_volume_increasing(self, scanner):
        # Price near 20-day high, volume increasing
        closes = [50000 + i * 50 for i in range(25)]
        volumes = [500_000] * 15 + [800_000] * 10  # volume increasing in last 10
        bars = _make_bars(closes, volumes)
        result = scanner.filter_momentum_breakout("005930", bars)
        assert result is True

    def test_rejects_far_from_high(self, scanner):
        # Price well below 20-day high
        closes = [55000] * 15 + [50000] * 10  # dropped 9% from high
        bars = _make_bars(closes)
        result = scanner.filter_momentum_breakout("005930", bars)
        assert result is False

    def test_rejects_overextended(self, scanner):
        # Price too far above SMA(20)
        closes = [50000] * 15 + [60000] * 10  # jumped 20% above average
        bars = _make_bars(closes)
        result = scanner.filter_momentum_breakout("005930", bars)
        assert result is False

    def test_insufficient_data(self, scanner):
        bars = _make_bars([50000] * 10)
        result = scanner.filter_momentum_breakout("005930", bars)
        assert result is False


class TestMinimumEdge:
    """Cost-aware minimum edge filter."""

    def test_passes_high_atr(self, scanner):
        # ATR is ~2% of price → exceeds 2× cost (1%)
        closes = [50000 + (500 if i % 2 == 0 else -500) for i in range(25)]
        bars = _make_bars(closes)
        result = scanner.check_minimum_edge("005930", bars)
        assert result is True

    def test_rejects_low_atr(self, scanner):
        # ATR is tiny — flat price
        closes = [50000 + i for i in range(25)]  # 1-won increments
        bars = _make_bars(closes)
        result = scanner.check_minimum_edge("005930", bars)
        assert result is False


class TestScanAll:
    """Integration: scan_universe returns filtered watchlist."""

    @patch("services.daily_scanner.DailyScanner._load_daily_bars")
    def test_scan_returns_watchlist(self, mock_load, scanner):
        # 005930 passes trend_pullback, 000660 fails
        closes_up = [50000 + i * 100 for i in range(25)]
        closes_up[-1] = closes_up[-2] - 500
        closes_down = [60000 - i * 200 for i in range(25)]

        mock_load.side_effect = [
            _make_bars(closes_up),     # 005930 passes
            _make_bars(closes_down),   # 000660 fails
        ]
        watchlist = scanner.scan_universe(["005930", "000660"])
        assert "005930" in watchlist.get("trend_pullback", [])
        assert "000660" not in watchlist.get("trend_pullback", [])
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_daily_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.daily_scanner'`

**Step 3: Write the DailyScanner config YAML**

Create `config/daily_scanner.yaml`:
```yaml
daily_scanner:
  # Universe
  universe_source: "static"     # "static" (hardcoded) or "redis" (from screener)
  max_watchlist_size: 40        # WebSocket cap

  # Layer 1: trend_pullback filter
  trend_pullback:
    sma_period: 20
    rsi_period: 14
    rsi_max: 45                 # pullback = RSI < 45
    trend_deviation_pct: 5.0    # max 5% below SMA
    min_volume_20d: 500000      # avg daily volume > 500K shares

  # Layer 1: momentum_breakout filter
  momentum_breakout:
    high_period: 20
    proximity_pct: 5.0          # within 5% of 20-day high
    volume_trend_ratio: 1.2     # vol_ma(5) > vol_ma(20) × 1.2
    max_extension_pct: 15.0     # max 15% above SMA(20)

  # Minimum edge filter (cost awareness)
  minimum_edge:
    atr_period: 14
    round_trip_cost: 0.005      # 0.50%
    min_atr_cost_ratio: 2.0     # ATR% must be >= 2× cost

  # Redis output
  redis_key: "system:daily_watchlist:latest"
  redis_ttl_seconds: 86400
```

**Step 4: Write the DailyScanner implementation**

Create `services/daily_scanner.py`:
```python
"""Pre-market daily scanner — Layer 1 multi-timeframe filters.

Reads daily candles from ClickHouse, applies per-strategy filters,
publishes watchlist to Redis for orchestrator consumption.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from shared.config.loader import ConfigLoader
from shared.config.mixins import ConfigMixin

logger = logging.getLogger(__name__)


@dataclass
class DailyBar:
    """Single daily OHLCV bar."""
    code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class DailyScannerConfig(ConfigMixin):
    """Configuration for daily scanner filters."""
    # trend_pullback
    tp_sma_period: int = 20
    tp_rsi_period: int = 14
    tp_rsi_max: float = 45.0
    tp_trend_deviation_pct: float = 5.0
    tp_min_volume_20d: int = 500_000

    # momentum_breakout
    mb_high_period: int = 20
    mb_proximity_pct: float = 5.0
    mb_volume_trend_ratio: float = 1.2
    mb_max_extension_pct: float = 15.0

    # minimum edge
    me_atr_period: int = 14
    me_round_trip_cost: float = 0.005
    me_min_atr_cost_ratio: float = 2.0

    # output
    max_watchlist_size: int = 40
    redis_key: str = "system:daily_watchlist:latest"
    redis_ttl_seconds: int = 86400


def _sma(values: list[float], period: int) -> float:
    """Simple moving average of last `period` values."""
    if len(values) < period:
        return 0.0
    return sum(values[-period:]) / period


def _rsi(closes: list[float], period: int = 14) -> float:
    """RSI calculation using SMA method."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(bars: list[DailyBar], period: int = 14) -> float:
    """Average True Range over last `period` bars."""
    if len(bars) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


class DailyScanner:
    """Pre-market daily scanner applying Layer 1 filters."""

    def __init__(self, config: DailyScannerConfig | None = None):
        self.config = config or DailyScannerConfig()

    def filter_trend_pullback(self, code: str, bars: list[DailyBar]) -> bool:
        """Layer 1 filter: uptrend + pullback (RSI < max)."""
        cfg = self.config
        if len(bars) < cfg.tp_sma_period + 1:
            return False

        closes = [b.close for b in bars]
        sma = _sma(closes, cfg.tp_sma_period)
        current_close = closes[-1]

        # Must be above SMA (uptrend)
        if current_close < sma:
            return False

        # Must not be too far below trend
        if current_close < sma * (1 - cfg.tp_trend_deviation_pct / 100):
            return False

        # Must be pulling back (RSI < threshold)
        rsi_val = _rsi(closes, cfg.tp_rsi_period)
        if rsi_val >= cfg.tp_rsi_max:
            return False

        # Volume filter
        volumes = [b.volume for b in bars]
        avg_vol = _sma([float(v) for v in volumes], cfg.tp_sma_period)
        if avg_vol < cfg.tp_min_volume_20d:
            return False

        return True

    def filter_momentum_breakout(self, code: str, bars: list[DailyBar]) -> bool:
        """Layer 1 filter: near 20-day high + volume increasing."""
        cfg = self.config
        if len(bars) < cfg.mb_high_period + 1:
            return False

        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        current_close = closes[-1]

        # Near 20-day high
        high_n = max(highs[-cfg.mb_high_period:])
        if current_close < high_n * (1 - cfg.mb_proximity_pct / 100):
            return False

        # Not overextended
        sma = _sma(closes, cfg.mb_high_period)
        if sma > 0 and current_close > sma * (1 + cfg.mb_max_extension_pct / 100):
            return False

        # Volume trend: recent vol > longer-term vol
        volumes = [float(b.volume) for b in bars]
        vol_ma_5 = _sma(volumes, 5)
        vol_ma_20 = _sma(volumes, 20)
        if vol_ma_20 > 0 and vol_ma_5 < vol_ma_20 * cfg.mb_volume_trend_ratio:
            return False

        return True

    def check_minimum_edge(self, code: str, bars: list[DailyBar]) -> bool:
        """Cost-aware filter: ATR% must exceed 2× round-trip cost."""
        cfg = self.config
        if len(bars) < cfg.me_atr_period + 1:
            return False

        atr_val = _atr(bars, cfg.me_atr_period)
        current_close = bars[-1].close
        if current_close <= 0:
            return False

        atr_pct = atr_val / current_close
        min_edge = cfg.me_round_trip_cost * cfg.me_min_atr_cost_ratio
        return atr_pct >= min_edge

    def _load_daily_bars(self, code: str, lookback_days: int = 60) -> list[DailyBar]:
        """Load daily bars from ClickHouse."""
        try:
            from shared.db.client import get_clickhouse_client
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
                    volume=int(c.volume),
                )
                for c in candles
            ]
        except Exception as e:
            logger.warning(f"Failed to load daily bars for {code}: {e}")
            return []

    def scan_universe(self, codes: list[str]) -> dict[str, list[str]]:
        """Scan all codes, return watchlist grouped by strategy."""
        watchlist: dict[str, list[str]] = {
            "trend_pullback": [],
            "momentum_breakout": [],
        }

        for code in codes:
            bars = self._load_daily_bars(code)
            if not bars:
                continue

            if not self.check_minimum_edge(code, bars):
                continue

            if self.filter_trend_pullback(code, bars):
                watchlist["trend_pullback"].append(code)

            if self.filter_momentum_breakout(code, bars):
                watchlist["momentum_breakout"].append(code)

        # Enforce max size (union of all strategies)
        all_codes = set()
        for codes_list in watchlist.values():
            all_codes.update(codes_list)

        if len(all_codes) > self.config.max_watchlist_size:
            # Prioritize stocks that pass both filters
            both = set(watchlist["trend_pullback"]) & set(watchlist["momentum_breakout"])
            one_only = all_codes - both
            keep = both | set(list(one_only)[:self.config.max_watchlist_size - len(both)])
            for key in watchlist:
                watchlist[key] = [c for c in watchlist[key] if c in keep]

        logger.info(
            f"Daily scan: trend_pullback={len(watchlist['trend_pullback'])}, "
            f"momentum_breakout={len(watchlist['momentum_breakout'])}"
        )
        return watchlist

    def scan_and_publish(self, codes: list[str]) -> dict[str, list[str]]:
        """Scan universe and publish to Redis."""
        import json
        import redis

        watchlist = self.scan_universe(codes)

        try:
            r = redis.Redis.from_url(
                "redis://localhost:6379/1", decode_responses=True
            )
            all_codes = set()
            for v in watchlist.values():
                all_codes.update(v)

            payload = json.dumps({
                "codes": list(all_codes),
                "strategies": watchlist,
                "scan_date": str(date.today()),
            })
            r.set(
                self.config.redis_key,
                payload,
                ex=self.config.redis_ttl_seconds,
            )
            logger.info(f"Published watchlist: {len(all_codes)} symbols to Redis")
        except Exception as e:
            logger.error(f"Failed to publish watchlist to Redis: {e}")

        return watchlist
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_daily_scanner.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add services/daily_scanner.py config/daily_scanner.yaml tests/unit/test_daily_scanner.py
git commit -m "feat: add pre-market daily scanner with Layer 1 filters"
```

---

## Task 3: Orchestrator Static Universe Mode

Add a `universe_mode: "static"` option to the orchestrator that reads the daily watchlist from Redis instead of the dynamic screener.

**Files:**
- Modify: `services/trading/orchestrator.py` — `TradingConfig`, `_universe_refresh_loop()`, `_load_ranked_targets()`
- Test: `tests/unit/trading/test_orchestrator_static_universe.py`

**Step 1: Write the failing test**

```python
"""Tests for orchestrator static universe mode."""
import json
import pytest
from unittest.mock import MagicMock, patch

from services.trading.orchestrator import TradingConfig


class TestStaticUniverseConfig:
    def test_universe_mode_default_is_dynamic(self):
        config = TradingConfig()
        assert config.universe_mode == "dynamic"

    def test_universe_mode_static(self):
        config = TradingConfig(universe_mode="static")
        assert config.universe_mode == "static"


class TestLoadStaticWatchlist:
    @patch("redis.Redis.from_url")
    def test_loads_from_daily_watchlist_key(self, mock_redis_cls):
        """Static mode reads system:daily_watchlist:latest."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({
            "codes": ["005930", "000660"],
            "strategies": {
                "trend_pullback": ["005930"],
                "momentum_breakout": ["000660"],
            },
        })
        mock_redis_cls.return_value = mock_redis

        from services.trading.orchestrator import TradingOrchestrator
        # Test the static loading method directly
        config = TradingConfig(universe_mode="static")
        orch = TradingOrchestrator.__new__(TradingOrchestrator)
        orch.config = config
        orch._daily_watchlist_key = "system:daily_watchlist:latest"

        codes, strategies = orch._load_static_watchlist(mock_redis)
        assert set(codes) == {"005930", "000660"}
        assert "005930" in strategies.get("trend_pullback", [])
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/trading/test_orchestrator_static_universe.py -v`
Expected: FAIL — `AttributeError: universe_mode`

**Step 3: Add `universe_mode` to `TradingConfig` and static watchlist loader**

In `services/trading/orchestrator.py`, add to `TradingConfig` dataclass (~line 290):
```python
    universe_mode: str = "dynamic"  # "dynamic" (screener) or "static" (daily_scanner)
```

Add `_load_static_watchlist` method and modify `_universe_refresh_loop`:
```python
    def _load_static_watchlist(self, redis_client) -> tuple[list[str], dict[str, list[str]]]:
        """Load pre-market watchlist from daily scanner."""
        raw = redis_client.get(self._daily_watchlist_key)
        if not raw:
            return [], {}
        try:
            payload = json.loads(raw)
            codes = [str(c).strip() for c in payload.get("codes", []) if str(c).strip()]
            strategies = payload.get("strategies", {})
            return codes, strategies
        except Exception as e:
            logger.warning(f"Failed to parse daily watchlist: {e}")
            return [], {}
```

Modify `_universe_refresh_loop` — when `universe_mode == "static"`:
- Load watchlist once
- Set `self.config.symbols = codes`
- Set up WebSocket subscriptions
- Prewarm all symbols
- Sleep forever (no 30s refresh loop)

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/trading/test_orchestrator_static_universe.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_static_universe.py
git commit -m "feat: add static universe mode to orchestrator (reads daily_watchlist)"
```

---

## Task 4: `trend_pullback` Entry Strategy

Multi-timeframe entry: requires daily filter pass (from watchlist metadata) + intraday BB/RSI/Williams %R trigger.

**Files:**
- Create: `shared/strategy/entry/trend_pullback.py`
- Create: `config/strategies/stock/trend_pullback.yaml`
- Test: `tests/unit/strategy/test_trend_pullback_entry.py`

**Step 1: Write the failing test**

```python
"""Tests for TrendPullbackEntry."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from shared.strategy.entry.trend_pullback import TrendPullbackEntry, TrendPullbackConfig
from shared.strategy.base import EntryContext


@pytest.fixture
def config():
    return TrendPullbackConfig()


@pytest.fixture
def entry(config):
    return TrendPullbackEntry(config)


def _make_context(
    code: str = "005930",
    close: float = 70000,
    bb_lower: float = 68000,
    bb_middle: float = 72000,
    rsi: float = 30,
    williams_r: float = -75,
    volume: float = 1_000_000,
    volume_ma: float = 800_000,
    atr: float = 1500,
    hour: int = 10,
    minute: int = 0,
    watchlist_strategies: list[str] | None = None,
) -> EntryContext:
    if watchlist_strategies is None:
        watchlist_strategies = ["trend_pullback"]
    return EntryContext(
        market_data={
            "code": code,
            "close": close,
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "rsi": rsi,
            "volume": volume,
            "volume_ma": volume_ma,
            "atr": atr,
        },
        indicators={
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=datetime(2026, 2, 26, hour, minute),
        metadata={
            "daily_watchlist": {
                "strategies": {"trend_pullback": [code]} if "trend_pullback" in watchlist_strategies else {},
            },
        },
    )


class TestTrendPullbackEntry:
    @pytest.mark.asyncio
    async def test_generates_signal_on_pullback(self, entry):
        """BB touch + RSI oversold + in watchlist → signal."""
        # Set prev williams_r to oversold
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(close=68500, rsi=30, williams_r=-70)
        signal = await entry.generate(ctx)
        assert signal is not None
        assert signal.code == "005930"

    @pytest.mark.asyncio
    async def test_rejects_not_in_watchlist(self, entry):
        """Symbol not in daily watchlist → no signal."""
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(watchlist_strategies=[])
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_rejects_no_bb_touch(self, entry):
        """Close not near BB lower → no signal."""
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(close=72000, bb_lower=68000)  # way above BB lower
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_rejects_high_rsi(self, entry):
        """RSI not oversold → no signal."""
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(rsi=55)  # not oversold
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_minimum_edge_filter(self, entry):
        """ATR too low relative to cost → no signal."""
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(atr=10, close=70000)  # ATR/close = 0.014% << 1%
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_skip_market_open(self, entry):
        """Skip first 30 minutes."""
        entry._prev_williams_r["005930"] = -85.0
        ctx = _make_context(hour=9, minute=10)
        signal = await entry.generate(ctx)
        assert signal is None

    @pytest.mark.asyncio
    async def test_config_defaults(self, config):
        assert config.bb_period == 20
        assert config.rsi_oversold == 35
        assert config.min_atr_cost_ratio == 2.0

    @pytest.mark.asyncio
    async def test_required_indicators(self, entry):
        assert "bb_lower" in entry.required_indicators
        assert "rsi" in entry.required_indicators
        assert "momentum_5m" in entry.required_indicators
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/strategy/test_trend_pullback_entry.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `shared/strategy/entry/trend_pullback.py`:
```python
"""Trend Pullback Entry — multi-timeframe uptrend + intraday oversold reversal.

Layer 1 (daily): Watchlist membership checked via metadata.
Layer 2 (intraday): BB lower touch OR Williams %R reversal + RSI oversold + volume.
Minimum edge: ATR% must exceed 2× round-trip cost.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class TrendPullbackConfig(ConfigMixin):
    """Configuration for trend pullback entry."""
    # Intraday trigger
    bb_period: int = 20
    bb_std: float = 2.0
    bb_touch_buffer: float = 1.005
    rsi_oversold: float = 35.0
    williams_r_oversold: float = -80.0
    williams_r_reversal: float = -70.0
    volume_threshold: float = 1.0

    # Minimum edge filter
    min_atr_cost_ratio: float = 2.0
    round_trip_cost: float = 0.005

    # Time filters
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15

    # Cooldown
    signal_cooldown_seconds: int = 300

    # Short
    allow_short: bool = False

    # Confidence
    confidence_base: float = 0.6
    confidence_rsi_scale: float = 50.0


class TrendPullbackEntry(EntrySignalGenerator[TrendPullbackConfig]):
    """Multi-timeframe trend pullback entry strategy."""

    CONFIG_CLASS = TrendPullbackConfig

    def __init__(self, config: TrendPullbackConfig):
        super().__init__(config)
        self._prev_williams_r: dict[str, float] = {}
        self._last_signal_time: dict[str, datetime] = {}

    @property
    def name(self) -> str:
        return "trend_pullback"

    @property
    def required_indicators(self) -> list[str]:
        return ["bb_lower", "bb_middle", "rsi", "volume", "volume_ma", "atr", "momentum_5m"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        md = context.market_data
        code = md.get("code", "")
        if not code:
            return None

        # --- Layer 1: Daily watchlist check ---
        daily_wl = context.metadata.get("daily_watchlist", {})
        strategies = daily_wl.get("strategies", {})
        tp_codes = strategies.get("trend_pullback", [])
        if code not in tp_codes:
            self._update_prev_williams_r(code, context)
            return None

        # --- Time filter ---
        now = context.timestamp
        market_open = now.replace(
            hour=self.config.market_open_hour,
            minute=self.config.market_open_minute,
            second=0,
        )
        open_cutoff = market_open + timedelta(minutes=self.config.skip_market_open_minutes)
        close_cutoff = now.replace(
            hour=self.config.market_close_hour,
            minute=self.config.market_close_minute,
            second=0,
        ) - timedelta(minutes=self.config.skip_market_close_minutes)

        if now < open_cutoff or now > close_cutoff:
            self._update_prev_williams_r(code, context)
            return None

        # --- Cooldown ---
        last = self._last_signal_time.get(code)
        if last and (now - last).total_seconds() < self.config.signal_cooldown_seconds:
            self._update_prev_williams_r(code, context)
            return None

        # --- Minimum edge filter ---
        atr = md.get("atr", 0.0)
        close = md.get("close", 0.0)
        if close <= 0:
            return None
        atr_pct = atr / close
        min_edge = self.config.round_trip_cost * self.config.min_atr_cost_ratio
        if atr_pct < min_edge:
            self._update_prev_williams_r(code, context)
            return None

        # --- Layer 2: Intraday trigger ---
        bb_lower = md.get("bb_lower", 0.0)
        rsi = md.get("rsi", 50.0)
        volume = md.get("volume", 0.0)
        volume_ma = md.get("volume_ma", 1.0)

        # Get Williams %R from momentum
        momentum = context.indicators.get("momentum_5m", {})
        if isinstance(momentum, dict):
            williams_r = momentum.get("williams_r", -50.0)
        else:
            williams_r = -50.0

        # Trigger 1: BB lower touch + RSI oversold
        bb_touch = close <= bb_lower * self.config.bb_touch_buffer
        rsi_oversold = rsi < self.config.rsi_oversold

        # Trigger 2: Williams %R reversal
        prev_wr = self._prev_williams_r.get(code, -50.0)
        wr_reversal = (
            prev_wr < self.config.williams_r_oversold
            and williams_r >= self.config.williams_r_reversal
        )

        # Need at least one trigger + RSI confirmation
        has_trigger = (bb_touch and rsi_oversold) or (wr_reversal and rsi_oversold)

        if not has_trigger:
            self._update_prev_williams_r(code, context)
            return None

        # Volume confirm
        if volume_ma > 0 and volume < volume_ma * self.config.volume_threshold:
            self._update_prev_williams_r(code, context)
            return None

        # --- Signal ---
        confidence = self.config.confidence_base
        # Boost for deeper oversold
        if rsi < 25:
            confidence += 0.15
        elif rsi < 30:
            confidence += 0.10
        confidence = min(confidence, 0.95)

        self._last_signal_time[code] = now
        self._update_prev_williams_r(code, context)

        return Signal(
            code=code,
            name=md.get("name", ""),
            strategy=self.name,
            price=close,
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "trigger": "bb_touch" if bb_touch else "wr_reversal",
                "rsi": rsi,
                "williams_r": williams_r,
                "atr_pct": round(atr_pct * 100, 3),
                "stop_loss": close - atr * 2.5,
            },
        )

    def _update_prev_williams_r(self, code: str, context: EntryContext) -> None:
        momentum = context.indicators.get("momentum_5m", {})
        if isinstance(momentum, dict):
            wr = momentum.get("williams_r")
            if wr is not None:
                self._prev_williams_r[code] = wr
```

**Step 4: Create YAML config**

Create `config/strategies/stock/trend_pullback.yaml`:
```yaml
# Trend Pullback Strategy (Multi-Timeframe)
#
# Layer 1 (Daily): close > SMA(20) + RSI < 45 + volume filter
# Layer 2 (Intraday): BB lower touch or Williams %R reversal + RSI < 35
# Cost filter: ATR% > 2× round-trip cost (1%)

strategy:
  name: trend_pullback
  asset_class: stock
  enabled: true
  description: "멀티 타임프레임 추세 추종 눌림목 전략"

  entry:
    type: trend_pullback
    params:
      bb_period: 20
      bb_std: 2.0
      bb_touch_buffer: 1.005
      rsi_oversold: 35.0
      williams_r_oversold: -80.0
      williams_r_reversal: -70.0
      volume_threshold: 1.0
      min_atr_cost_ratio: 2.0
      round_trip_cost: 0.005
      skip_market_open_minutes: 30
      skip_market_close_minutes: 15
      signal_cooldown_seconds: 300

  exit:
    type: atr_dynamic
    params:
      atr_period: 14
      stop_atr_multiplier: 2.5
      trail_activation_atr: 1.0
      trail_atr_multiplier: 2.0
      daily_trend_exit: true
      daily_sma_period: 20
      eod_close_enabled: false
      default_exit_confidence: 0.85

  position:
    type: fixed
    params:
      order_amount_per_stock: 1000000
      max_positions: 5

  indicators:
    bollinger_bands:
      period: 20
      std_dev: 2.0
    momentum:
      williams_r_period: 14
```

**Step 5: Register in registry**

In `shared/strategy/registry.py`, in `register_builtin_components()`, add before the `rl_mppo` entry block:
```python
    try:
        from shared.strategy.entry.trend_pullback import TrendPullbackEntry
        EntryRegistry.register_class("trend_pullback", TrendPullbackEntry)
    except ImportError:
        logger.debug("TrendPullbackEntry not available")
```

**Step 6: Run tests**

Run: `.venv/bin/pytest tests/unit/strategy/test_trend_pullback_entry.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add shared/strategy/entry/trend_pullback.py config/strategies/stock/trend_pullback.yaml tests/unit/strategy/test_trend_pullback_entry.py shared/strategy/registry.py
git commit -m "feat: add trend_pullback entry strategy with multi-timeframe Layer 1/2"
```

---

## Task 5: `momentum_breakout` Entry Strategy

**Files:**
- Create: `shared/strategy/entry/momentum_breakout.py`
- Create: `config/strategies/stock/momentum_breakout.yaml`
- Test: `tests/unit/strategy/test_momentum_breakout_entry.py`

Pattern is identical to Task 4. Key differences:

- Layer 1 check: `code in strategies.get("momentum_breakout", [])`
- Intraday trigger: `close > high_N` (daily) + `rvol >= threshold`
- Accumulation score from metadata (optional)
- Tighter stop: 1.5 ATR
- `required_indicators = ["close", "high_5", "rvol", "volume", "volume_ma", "atr"]`

**Step 1: Write failing test, Step 2: verify fail, Step 3: implement, Step 4: YAML, Step 5: register, Step 6: test, Step 7: commit.**

Follow the same TDD cycle as Task 4 with `MomentumBreakoutEntry`, `MomentumBreakoutConfig`.

---

## Task 6: `atr_dynamic` Exit Strategy

Unified ATR-based exit replacing all fixed-% stops.

**Files:**
- Create: `shared/strategy/exit/atr_dynamic.py`
- Test: `tests/unit/strategy/test_atr_dynamic_exit.py`

**Step 1: Write the failing test**

```python
"""Tests for ATR Dynamic Exit."""
import pytest
from datetime import datetime, timedelta

from shared.strategy.exit.atr_dynamic import ATRDynamicExit, ATRDynamicExitConfig
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason


@pytest.fixture
def config():
    return ATRDynamicExitConfig()


@pytest.fixture
def exit_strategy(config):
    return ATRDynamicExit(config)


def _make_position(
    code: str = "005930",
    entry_price: float = 70000,
    side: PositionSide = PositionSide.LONG,
    entry_time: datetime | None = None,
) -> Position:
    return Position(
        code=code,
        name="삼성전자",
        side=side,
        entry_price=entry_price,
        quantity=10,
        entry_time=entry_time or datetime(2026, 2, 26, 10, 0),
        strategy="trend_pullback",
    )


def _make_market_data(
    code: str = "005930",
    close: float = 70000,
    atr: float = 1500,
    volume_velocity: float = 0.0,
) -> dict:
    return {
        code: {
            "close": close,
            "atr": atr,
            "volume_velocity": volume_velocity,
            "high_since_entry": close,
        }
    }


class TestATRDynamicExit:
    @pytest.mark.asyncio
    async def test_hard_stop_triggers(self, exit_strategy):
        """Price drops > ATR × 2.5 from entry → stop loss."""
        pos = _make_position(entry_price=70000)
        md = _make_market_data(close=66000, atr=1500)  # -4000 > 1500*2.5=3750
        signals = await exit_strategy.scan_positions([pos], md)
        assert len(signals) == 1
        assert signals[0].reason == ExitReason.STOP_LOSS

    @pytest.mark.asyncio
    async def test_hard_stop_not_reached(self, exit_strategy):
        """Price within ATR stop → no exit."""
        pos = _make_position(entry_price=70000)
        md = _make_market_data(close=68000, atr=1500)  # -2000 < 3750
        signals = await exit_strategy.scan_positions([pos], md)
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_trailing_stop_activates_and_trails(self, exit_strategy):
        """Price rises > ATR × trail_activation, then drops > ATR × trail_mult."""
        pos = _make_position(entry_price=70000)
        # First: price goes to 73000 (profit > 1500*1.0=1500) → trailing activates
        md = _make_market_data(close=73000, atr=1500)
        md["005930"]["high_since_entry"] = 73000
        signals = await exit_strategy.scan_positions([pos], md)
        assert len(signals) == 0  # trailing active but not triggered

        # Now: price drops from 73000 high to below trail distance
        md = _make_market_data(close=69500, atr=1500)
        md["005930"]["high_since_entry"] = 73000  # peak was 73000
        signals = await exit_strategy.scan_positions([pos], md)
        assert len(signals) == 1
        assert signals[0].reason == ExitReason.TRAILING_STOP

    @pytest.mark.asyncio
    async def test_max_hold_days(self, exit_strategy):
        """Position held > max_hold_days → time cut."""
        exit_strategy.config.max_hold_days = 5
        pos = _make_position(
            entry_time=datetime(2026, 2, 20, 10, 0),  # 6 days ago
        )
        md = _make_market_data(close=70500)  # slightly profitable
        signals = await exit_strategy.scan_positions(
            [pos], md, market_state=None,
        )
        assert any(s.reason == ExitReason.TIME_CUT for s in signals)

    @pytest.mark.asyncio
    async def test_config_defaults(self, config):
        assert config.atr_period == 14
        assert config.stop_atr_multiplier == 2.5
        assert config.trail_activation_atr == 1.0
        assert config.trail_atr_multiplier == 2.0
        assert config.max_hold_days == 0
```

**Step 2: Run test → FAIL**

**Step 3: Write implementation**

Create `shared/strategy/exit/atr_dynamic.py`:
```python
"""ATR Dynamic Exit — unified volatility-adaptive exit strategy.

Priority:
1. Hard stop: entry ± ATR × stop_multiplier
2. Trailing stop: from high_since_entry - ATR × trail_multiplier
3. Momentum decay: retracement > 1 ATR + negative volume velocity
4. Max hold days
5. EOD: optional, disabled by default for swing strategies
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class ATRDynamicExitConfig(ConfigMixin):
    """Configuration for ATR dynamic exit."""
    atr_period: int = 14
    stop_atr_multiplier: float = 2.5
    trail_activation_atr: float = 1.0
    trail_atr_multiplier: float = 2.0
    momentum_decay_exit: bool = False
    max_hold_days: int = 0
    eod_close_enabled: bool = False
    eod_close_hour: int = 15
    eod_close_minute: int = 15
    default_exit_confidence: float = 0.85
    daily_trend_exit: bool = False
    daily_sma_period: int = 20


class ATRDynamicExit(ExitSignalGenerator[ATRDynamicExitConfig]):
    """Volatility-adaptive exit with ATR-based stops."""

    CONFIG_CLASS = ATRDynamicExitConfig

    def __init__(self, config: ATRDynamicExitConfig):
        super().__init__(config)

    @property
    def name(self) -> str:
        return "atr_dynamic"

    async def should_exit(
        self, context: ExitContext
    ) -> tuple[bool, Optional[ExitSignal]]:
        return False, None

    async def scan_positions(
        self,
        positions: list[Position],
        market_data: dict[str, Any],
        market_state: Optional[Any] = None,
    ) -> list[ExitSignal]:
        signals = []
        now = datetime.now()

        for pos in positions:
            signal = self._check_position(pos, market_data, now)
            if signal:
                signals.append(signal)

        return signals

    def _check_position(
        self,
        pos: Position,
        market_data: dict[str, Any],
        now: datetime,
    ) -> Optional[ExitSignal]:
        md = market_data.get(pos.code, {})
        if not md:
            return None

        close = md.get("close", 0.0)
        atr = md.get("atr", 0.0)
        if close <= 0 or atr <= 0:
            return None

        entry_price = pos.entry_price
        profit_pct = (close - entry_price) / entry_price if pos.side == PositionSide.LONG else (entry_price - close) / entry_price
        profit_amount = (close - entry_price) * pos.quantity if pos.side == PositionSide.LONG else (entry_price - close) * pos.quantity

        # --- 1. Hard stop ---
        stop_distance = atr * self.config.stop_atr_multiplier
        if pos.side == PositionSide.LONG:
            stop_price = entry_price - stop_distance
            if close <= stop_price:
                return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.STOP_LOSS, 1)
        else:
            stop_price = entry_price + stop_distance
            if close >= stop_price:
                return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.STOP_LOSS, 1)

        # --- 2. EOD ---
        if self.config.eod_close_enabled:
            eod = now.replace(
                hour=self.config.eod_close_hour,
                minute=self.config.eod_close_minute,
                second=0,
            )
            if now >= eod:
                return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.EOD_CLOSE, 2)

        # --- 3. Trailing stop ---
        high_since = md.get("high_since_entry", close)
        profit_from_entry = high_since - entry_price if pos.side == PositionSide.LONG else entry_price - high_since
        trail_activation = atr * self.config.trail_activation_atr

        if profit_from_entry >= trail_activation:
            trail_distance = atr * self.config.trail_atr_multiplier
            if pos.side == PositionSide.LONG:
                trail_stop = high_since - trail_distance
                if close <= trail_stop:
                    return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.TRAILING_STOP, 3)
            else:
                low_since = md.get("low_since_entry", close)
                trail_stop = low_since + trail_distance
                if close >= trail_stop:
                    return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.TRAILING_STOP, 3)

        # --- 4. Momentum decay ---
        if self.config.momentum_decay_exit:
            volume_velocity = md.get("volume_velocity", 0.0)
            retracement = high_since - close if pos.side == PositionSide.LONG else close - high_since
            if retracement > atr and volume_velocity < 0:
                return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.MOMENTUM_DECAY, 4)

        # --- 5. Max hold days ---
        if self.config.max_hold_days > 0 and pos.entry_time:
            hold_days = (now - pos.entry_time).days
            if hold_days >= self.config.max_hold_days:
                return self._make_signal(pos, close, profit_pct, profit_amount, ExitReason.TIME_CUT, 5)

        return None

    def _make_signal(
        self,
        pos: Position,
        close: float,
        profit_pct: float,
        profit_amount: float,
        reason: ExitReason,
        priority: int,
    ) -> ExitSignal:
        return ExitSignal(
            code=pos.code,
            name=pos.name,
            position_id=getattr(pos, "position_id", ""),
            reason=reason,
            strategy=self.name,
            current_price=close,
            exit_price=close,
            entry_price=pos.entry_price,
            profit_pct=round(profit_pct * 100, 4),
            profit_amount=round(profit_amount, 2),
            confidence=self.config.default_exit_confidence,
            priority=priority,
            quantity=pos.quantity,
        )
```

**Step 4: Register in registry**

Add to `register_builtin_components()`:
```python
    try:
        from shared.strategy.exit.atr_dynamic import ATRDynamicExit
        ExitRegistry.register_class("atr_dynamic", ATRDynamicExit)
    except ImportError:
        logger.debug("ATRDynamicExit not available")
```

**Step 5: Run tests → PASS**

**Step 6: Commit**

```bash
git add shared/strategy/exit/atr_dynamic.py tests/unit/strategy/test_atr_dynamic_exit.py shared/strategy/registry.py
git commit -m "feat: add ATR dynamic exit with volatility-adaptive stops and trailing"
```

---

## Task 7: Backtest Validation

Run backtests on new strategies against 50-stock universe with daily + minute data.

**Files:**
- Create: `scripts/analysis/backtest_redesign.py`
- Reference: `shared/backtest/engine.py`, `shared/collector/historical/stock.py`

**Step 1: Write the backtest script**

```python
#!/usr/bin/env python3
"""Backtest redesigned strategies (trend_pullback, momentum_breakout).

Usage:
    python scripts/analysis/backtest_redesign.py [--strategy trend_pullback] [--tier all]
"""
import argparse
import logging
import sys
from datetime import date, timedelta

from scripts.data.backfill_daily_pykrx import UNIVERSE_50
from services.daily_scanner import DailyScanner, DailyScannerConfig
from shared.backtest.config import BacktestConfig, CostConfig
from shared.backtest.engine import BacktestEngine
from shared.collector.historical.stock import load_stock_minute_from_clickhouse
from shared.strategy.registry import StrategyFactory

logger = logging.getLogger(__name__)


def run_backtest(strategy_name: str = "trend_pullback", tier: str = "all"):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # 1. Daily scan to get watchlist
    scanner = DailyScanner(DailyScannerConfig())
    codes = [s["code"] for s in UNIVERSE_50]
    names = {s["code"]: s["name"] for s in UNIVERSE_50}
    watchlist = scanner.scan_universe(codes)

    target_codes = watchlist.get(strategy_name, [])
    if not target_codes:
        logger.warning(f"No symbols passed daily filter for {strategy_name}")
        return

    logger.info(f"Daily filter passed: {len(target_codes)} symbols for {strategy_name}")

    # 2. Load strategy
    strategy = StrategyFactory.create_from_file("stock", strategy_name.replace("_breakout", "_breakout"))

    # 3. Backtest each symbol
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    cost = CostConfig.stock()
    config = BacktestConfig.stock(initial_capital=10_000_000)

    results = []
    for code in target_codes:
        df = load_stock_minute_from_clickhouse(code, start_date, end_date)
        if df is None or df.empty:
            continue

        engine = BacktestEngine(strategy=strategy, config=config)
        result = engine.run(df)
        results.append({
            "code": code,
            "name": names.get(code, ""),
            "trades": result.total_trades,
            "return": result.total_return_pct,
            "sharpe": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "mdd": result.max_drawdown_pct,
        })
        logger.info(
            f"{code} {names.get(code, '')}: "
            f"{result.total_trades} trades, "
            f"return={result.total_return_pct:.2f}%, "
            f"sharpe={result.sharpe_ratio:.2f}"
        )

    # 4. Summary
    if results:
        avg_sharpe = sum(r["sharpe"] for r in results) / len(results)
        avg_return = sum(r["return"] for r in results) / len(results)
        positive = sum(1 for r in results if r["sharpe"] > 0)
        total_trades = sum(r["trades"] for r in results)
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy_name}")
        print(f"Symbols: {len(results)}, Trades: {total_trades}")
        print(f"Avg Return: {avg_return:.3f}%, Avg Sharpe: {avg_sharpe:.2f}")
        print(f"Positive Sharpe: {positive}/{len(results)} ({positive/len(results)*100:.0f}%)")
        print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="trend_pullback")
    parser.add_argument("--tier", default="all")
    args = parser.parse_args()
    run_backtest(args.strategy, args.tier)
```

**Step 2: Run backtest**

Run: `.venv/bin/python scripts/analysis/backtest_redesign.py --strategy trend_pullback`
Expected: Results for filtered symbols, targeting Sharpe > 1.0

**Step 3: Iterate on parameters if needed**

If Sharpe < 1.0, adjust parameters in `config/daily_scanner.yaml` and `config/strategies/stock/trend_pullback.yaml`.

**Step 4: Commit results**

```bash
git add scripts/analysis/backtest_redesign.py
git commit -m "feat: add backtest validation script for redesigned strategies"
```

---

## Task 8: Disable Old Strategies + Final Commit

**Files:**
- Modify: `config/strategies/stock/bb_reversion.yaml` — set `enabled: false`
- Modify: `config/strategies/stock/williams_r.yaml` — set `enabled: false`
- Modify: `config/strategies/stock/volume_accumulation.yaml` — set `enabled: false`
- Modify: `config/strategies/stock/opening_volume_surge.yaml` — set `enabled: false`

**Step 1: Disable old strategies**

For each file, change `enabled: true` → `enabled: false`.

**Step 2: Verify all tests pass**

Run: `.venv/bin/pytest tests/ -v --timeout=60`
Expected: All existing + new tests PASS

**Step 3: Commit**

```bash
git add config/strategies/stock/
git commit -m "refactor: disable old strategies in favor of trend_pullback + momentum_breakout"
```

---

## Summary

| Task | What | Files | Depends On |
|------|------|-------|------------|
| 1 | Daily candle backfill (pykrx) | `scripts/data/backfill_daily_pykrx.py` | — |
| 2 | Daily scanner service | `services/daily_scanner.py`, config, tests | Task 1 |
| 3 | Orchestrator static universe | `orchestrator.py` modifications, tests | Task 2 |
| 4 | `trend_pullback` entry | `shared/strategy/entry/trend_pullback.py`, YAML, tests | Task 2 |
| 5 | `momentum_breakout` entry | `shared/strategy/entry/momentum_breakout.py`, YAML, tests | Task 2 |
| 6 | `atr_dynamic` exit | `shared/strategy/exit/atr_dynamic.py`, tests | — |
| 7 | Backtest validation | `scripts/analysis/backtest_redesign.py` | Tasks 1-6 |
| 8 | Disable old strategies | YAML config changes | Task 7 |
