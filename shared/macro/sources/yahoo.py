"""Yahoo Finance macro source via yfinance."""

from __future__ import annotations

import asyncio
import logging
import time

import yfinance as yf  # noqa: F401 — re-exported for tests to monkey-patch

from shared.macro.base import MacroSnapshot

logger = logging.getLogger(__name__)


_TICKER_MAP = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
}


def _fetch_close_and_change(ticker_symbol: str) -> tuple[float | None, float | None]:
    """Sync helper, run in a thread."""
    try:
        t = yf.Ticker(ticker_symbol)
        hist = t.history(period="5d")
        if getattr(hist, "empty", True) or len(hist) < 2:
            return None, None
        last = float(hist.iloc[-1]["Close"])
        prev = float(hist.iloc[-2]["Close"])
        if prev == 0:
            return last, None
        return last, (last - prev) / prev * 100.0
    except Exception:
        logger.exception("yfinance fetch failed ticker=%s", ticker_symbol)
        return None, None


class YahooMacroSource:
    async def fetch_us_close_snapshot(self) -> MacroSnapshot:
        # Fetch in thread pool (yfinance is sync)
        loop = asyncio.get_running_loop()

        async def _t(sym: str):
            return await loop.run_in_executor(None, _fetch_close_and_change, sym)

        sp500, sp500_pct = await _t(_TICKER_MAP["sp500"])
        nasdaq, nasdaq_pct = await _t(_TICKER_MAP["nasdaq"])
        vix, _ = await _t(_TICKER_MAP["vix"])
        dxy, _ = await _t(_TICKER_MAP["dxy"])
        us10y, _ = await _t(_TICKER_MAP["us10y"])

        return MacroSnapshot(
            ts_ms=int(time.time() * 1000),
            session="overnight_us_close",
            sp500_close=sp500,
            sp500_change_pct=sp500_pct,
            nasdaq_close=nasdaq,
            nasdaq_change_pct=nasdaq_pct,
            vix=vix,
            dxy=dxy,
            us10y_yield=us10y,
            collected_from=["yahoo"],
        )
