"""After-close watchlist generation for next-day monitoring/trading.

Goal:
  - Build a list of stocks (KOSPI + KOSDAQ) worth monitoring the next day.
  - Focus on names with strong recent liquidity and improving "capital inflow"
    proxied by increasing trade value/turnover (not investor net flow).
  - Add lightweight "attention" via news headline count + keyword sentiment.

This module is intentionally conservative about external calls:
  - Universe collection uses pykrx (single call per market).
  - News scraping runs only on a small shortlist.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional

from shared.llm.collectors import (
    MKStockNewsCollector,
    NaverFinanceNewsCollector,
    StockDataCollector,
)

logger = logging.getLogger(__name__)


def _get_col(df, candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class WatchlistItem:
    code: str
    name: str
    market: str

    prev_close: float
    prev_volume: int
    prev_trade_value: float
    change_pct: float

    # Trend features (recent / longer baseline)
    volume_trend: float = 1.0
    value_trend: float = 1.0
    momentum_5d: float = 0.0

    # Attention features
    news_count: int = 0
    news_sentiment: str = "중립"
    news_headlines: list[str] = None

    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("news_headlines") is None:
            d["news_headlines"] = []
        return d


class WatchlistGenerator:
    def __init__(
        self,
        stock_collector: Optional[StockDataCollector] = None,
        mk_news: Optional[MKStockNewsCollector] = None,
        naver_news: Optional[NaverFinanceNewsCollector] = None,
    ):
        self.stock_collector = stock_collector or StockDataCollector()
        self.mk_news = mk_news or MKStockNewsCollector()
        self.naver_news = naver_news or NaverFinanceNewsCollector()

    def generate(
        self,
        list_size: int = 30,
        min_price: int = 5_000,
        max_price: int = 500_000,
        min_market_cap: int = 500_000_000_000,  # 5000억
        max_market_cap: int = 100_000_000_000_000,  # 100조
        history_days: int = 30,
        per_market_candidates: int = 250,
        news_shortlist_multiplier: int = 3,
    ) -> list[WatchlistItem]:
        """Generate a next-day watchlist after market close."""
        if list_size <= 0:
            return []

        # Universe: KOSPI + KOSDAQ (best-effort).
        kospi = self.stock_collector.collect("KOSPI")
        kosdaq = self.stock_collector.collect("KOSDAQ")

        if kospi is None and kosdaq is None:
            logger.error("Watchlist generation failed: no market data")
            return []

        frames = []
        if kospi is not None and len(kospi) > 0:
            frames.append(kospi)
        if kosdaq is not None and len(kosdaq) > 0:
            frames.append(kosdaq)

        import pandas as pd  # local import to keep import surface small

        market_df = pd.concat(frames, axis=0) if len(frames) > 1 else frames[0]
        if market_df is None or len(market_df) == 0:
            return []

        price_col = _get_col(market_df, ["종가", "close"])
        open_col = _get_col(market_df, ["시가", "open"])
        vol_col = _get_col(market_df, ["거래량", "volume"])
        cap_col = _get_col(market_df, ["시가총액", "market_cap"])
        value_col = _get_col(market_df, ["거래대금", "거래대금(원)", "trade_value", "거래대금(백만원)"])

        if not price_col or not open_col or not vol_col:
            logger.error(
                f"Watchlist generation failed: missing required cols "
                f"(price={price_col}, open={open_col}, volume={vol_col})"
            )
            return []

        df = market_df.copy()
        if cap_col is None:
            # Keep it permissive if market cap isn't available.
            df["시가총액"] = 0
            cap_col = "시가총액"

        # Best-effort trade value (turnover proxy).
        if value_col is None:
            df["_trade_value"] = df[price_col].astype(float) * df[vol_col].astype(float)
            value_col = "_trade_value"

        # Filters
        df = df[
            (df[price_col] >= min_price)
            & (df[price_col] <= max_price)
            & (df[cap_col] >= min_market_cap)
            & (df[cap_col] <= max_market_cap)
        ].copy()

        if len(df) == 0:
            return []

        # Compute simple daily change
        df["_change_pct"] = (df[price_col] - df[open_col]) / df[open_col] * 100.0

        # Candidate shortlist per market by trade value (liquidity).
        candidates = []
        if "시장" in df.columns:
            for mkt in ("KOSPI", "KOSDAQ"):
                mdf = df[df["시장"] == mkt]
                if len(mdf) == 0:
                    continue
                top = mdf.nlargest(per_market_candidates, value_col)
                candidates.append(top)
        else:
            candidates.append(df.nlargest(per_market_candidates, value_col))

        cand_df = pd.concat(candidates, axis=0) if len(candidates) > 1 else candidates[0]
        cand_df = cand_df[~cand_df.index.duplicated(keep="first")]

        # Build base items with trend features (per-ticker history).
        items: list[WatchlistItem] = []
        for code in cand_df.index:
            row = cand_df.loc[code]
            market = row.get("시장", "") or ""
            name = self.stock_collector.get_stock_name(code)

            prev_close = _safe_float(row.get(price_col))
            prev_volume = _safe_int(row.get(vol_col))
            prev_trade_value = _safe_float(row.get(value_col))
            change_pct = _safe_float(row.get("_change_pct"))

            volume_trend = 1.0
            value_trend = 1.0
            momentum_5d = 0.0

            hist = self.stock_collector.get_stock_history(code, days=history_days)
            if hist is not None and len(hist) >= 10:
                h_vol = _get_col(hist, ["거래량", "volume"])
                h_value = _get_col(hist, ["거래대금", "거래대금(원)", "trade_value"])
                h_close = _get_col(hist, ["종가", "close"])

                try:
                    if h_vol:
                        v5 = float(hist[h_vol].tail(5).mean())
                        v20 = float(hist[h_vol].tail(20).mean()) if len(hist) >= 20 else float(hist[h_vol].mean())
                        volume_trend = v5 / v20 if v20 > 0 else 1.0
                    if h_value:
                        tv5 = float(hist[h_value].tail(5).mean())
                        tv20 = float(hist[h_value].tail(20).mean()) if len(hist) >= 20 else float(hist[h_value].mean())
                        value_trend = tv5 / tv20 if tv20 > 0 else 1.0
                    if h_close and len(hist) >= 6:
                        c_now = float(hist[h_close].iloc[-1])
                        c_5 = float(hist[h_close].iloc[-6])
                        if c_5 > 0:
                            momentum_5d = (c_now - c_5) / c_5 * 100.0
                except Exception:
                    # Keep defaults.
                    pass

            items.append(
                WatchlistItem(
                    code=str(code),
                    name=name,
                    market=str(market),
                    prev_close=prev_close,
                    prev_volume=prev_volume,
                    prev_trade_value=prev_trade_value,
                    change_pct=change_pct,
                    volume_trend=float(volume_trend),
                    value_trend=float(value_trend),
                    momentum_5d=float(momentum_5d),
                    news_headlines=[],
                )
            )

        if not items:
            return []

        # Base score: liquidity + inflow proxy + mild momentum (no news yet).
        # Use log trade value to reduce scale effects.
        for it in items:
            tv = max(1.0, it.prev_trade_value)
            liquidity = math.log(tv)
            trend = (it.value_trend - 1.0) * 100.0 + (it.volume_trend - 1.0) * 50.0
            mom = it.momentum_5d * 0.5
            it.score = liquidity * 0.6 + _clip(trend, -50, 200) * 0.3 + _clip(mom, -20, 50) * 0.1

        items.sort(key=lambda x: x.score, reverse=True)

        # News enrichment: only for a small shortlist.
        news_shortlist = items[: max(list_size * news_shortlist_multiplier, list_size)]

        for it in news_shortlist:
            try:
                mk = self.mk_news.collect(it.code)
            except Exception:
                mk = {}
            try:
                nv = self.naver_news.collect(it.code)
            except Exception:
                nv = {}

            all_news = (mk.get("stock_news", []) or []) + (nv.get("stock_news", []) or [])
            sentiment = self.mk_news.analyze_sentiment(all_news).value if all_news else "중립"

            it.news_count = len(all_news)
            it.news_sentiment = sentiment
            it.news_headlines = [n.get("title", "") for n in all_news[:5] if n.get("title")]

            # News score (lightweight): sentiment + count.
            sentiment_map = {
                "매우 긍정": 2,
                "긍정": 1,
                "중립": 0,
                "부정": -1,
                "매우 부정": -2,
            }
            s = float(sentiment_map.get(sentiment, 0))
            it.score += s * 2.0 + _clip(float(it.news_count), 0.0, 10.0) * 0.2

        # Final re-rank using updated scores.
        items.sort(key=lambda x: x.score, reverse=True)
        return items[:list_size]


def save_watchlist(
    items: list[WatchlistItem],
    output_dir: str = "output/llm",
    filename_prefix: str = "watchlist",
) -> str:
    """Save watchlist as JSON and return path."""
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = os.path.join(output_dir, f"{filename_prefix}_{date_str}.json")

    payload = {
        "generated_at": datetime.now().isoformat(),
        "count": len(items),
        "items": [it.to_dict() for it in items],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Convenience "latest" pointer (best-effort, no symlink).
    latest_path = os.path.join(output_dir, f"{filename_prefix}_latest.json")
    try:
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return path


def build_symbol_metadata(items: list[WatchlistItem]) -> dict[str, dict[str, Any]]:
    """Build per-symbol metadata for the trading engine (baseline for next day)."""
    meta: dict[str, dict[str, Any]] = {}
    for it in items:
        meta[it.code] = {
            "name": it.name,
            "market": it.market,
            "prev_day_close": it.prev_close,
            "prev_day_volume": it.prev_volume,
            "prev_day_trade_value": it.prev_trade_value,
            "watchlist_score": it.score,
        }
    return meta

