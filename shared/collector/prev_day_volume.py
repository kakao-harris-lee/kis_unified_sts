"""Previous-day volume lookup via pykrx.

Provides a cache-backed helper that fetches previous trading day volumes
for a list of stock codes.  Designed for use by the Screener at startup
so that ``opening_volume_surge`` can compare today's cumulative volume
against yesterday's total.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_pykrx_stock() -> Any:
    """Lazy-import pykrx.stock. Returns the module or raises ImportError."""
    from pykrx import stock
    return stock


def _last_trading_date_str() -> str:
    """Return the most recent *past* trading date in ``YYYYMMDD`` format.

    Falls back up to 7 calendar days to skip weekends / holidays.
    """
    stock = _get_pykrx_stock()
    today = datetime.now()
    for offset in range(1, 8):
        candidate = (today - timedelta(days=offset)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv(candidate, market="KOSPI")
        if len(df) > 0:
            return candidate
    return (today - timedelta(days=1)).strftime("%Y%m%d")


class PrevDayVolumeCache:
    """Caches previous-day volumes fetched from pykrx.

    Usage::

        cache = PrevDayVolumeCache()
        cache.warm_all()            # bulk-load KOSPI + KOSDAQ
        vol = cache.get("005930")   # 12_345_678
        cache.ensure(["005930", "000660"])  # lazy-fill missing codes
    """

    def __init__(self) -> None:
        self._volumes: dict[str, int] = {}
        self._date: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def warm_all(self) -> int:
        """Bulk-load previous-day volumes for all KOSPI + KOSDAQ stocks.

        Returns the number of codes loaded.
        """
        try:
            stock = _get_pykrx_stock()
        except ImportError:
            logger.warning("pykrx not installed — prev_day_volume unavailable")
            return 0

        date = _last_trading_date_str()
        self._date = date
        loaded = 0

        for market in ("KOSPI", "KOSDAQ"):
            try:
                df = stock.get_market_ohlcv(date, market=market)
                if df is None or len(df) == 0:
                    continue
                vol_col = "거래량" if "거래량" in df.columns else None
                if vol_col is None:
                    continue
                for code in df.index:
                    vol = int(df.at[code, vol_col])
                    if vol > 0:
                        self._volumes[str(code)] = vol
                        loaded += 1
            except Exception as e:
                logger.warning("Failed to load prev-day volumes for %s: %s", market, e)

        logger.info(
            "PrevDayVolumeCache: loaded %d codes (date=%s)", loaded, date
        )
        return loaded

    def get(self, code: str) -> int:
        """Return previous-day volume for *code*, or 0 if unknown."""
        return self._volumes.get(code, 0)

    def ensure(self, codes: list[str]) -> int:
        """Lazy-fill any codes missing from the cache.

        Returns the number of newly fetched codes.
        """
        missing = [c for c in codes if c not in self._volumes]
        if not missing:
            return 0

        filled = 0
        try:
            stock = _get_pykrx_stock()
            date = self._date or _last_trading_date_str()
            for code in missing:
                try:
                    df = stock.get_market_ohlcv(date, date, code)
                    if df is not None and len(df) > 0 and "거래량" in df.columns:
                        vol = int(df.iloc[-1]["거래량"])
                        if vol > 0:
                            self._volumes[code] = vol
                            filled += 1
                except Exception:
                    pass
        except ImportError:
            pass

        if filled:
            logger.debug("PrevDayVolumeCache: lazy-filled %d codes", filled)
        return filled

    def build_metadata(self, codes: list[str]) -> dict[str, dict[str, int]]:
        """Build per-symbol metadata dict for Redis payload.

        Returns ``{code: {"prev_day_volume": N}}`` for codes with data.
        """
        result: dict[str, dict[str, int]] = {}
        for code in codes:
            vol = self._volumes.get(code, 0)
            if vol > 0:
                result[code] = {"prev_day_volume": vol}
        return result

    @property
    def date(self) -> Optional[str]:
        return self._date

    def __len__(self) -> int:
        return len(self._volumes)
