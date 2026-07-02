"""Yahoo Finance macro source via yfinance."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping

import yfinance as yf  # noqa: F401 — re-exported for tests to monkey-patch

from shared.macro.base import MacroSnapshot
from shared.macro.config import DEFAULT_YAHOO_SYMBOLS

logger = logging.getLogger(__name__)

# Snapshot field prefixes fetched by the pre-market session (07:45 KST).
# Each key doubles as the ticker-map key and yields ``<key>``/
# ``<key>_change_pct`` MacroSnapshot fields.
_PREMARKET_FIELDS: tuple[str, ...] = (
    "es_futures",
    "nq_futures",
    "sox",
    "usdkrw_realtime",
)


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
    """Fetches macro snapshots from Yahoo Finance.

    Args:
        ticker_map: MacroSnapshot field prefix -> Yahoo symbol. Normally
            injected from ``MacroCollectorConfig.yahoo_symbols`` so symbol
            additions are config-only; defaults to the legacy hardcoded map.
    """

    def __init__(self, ticker_map: Mapping[str, str] | None = None) -> None:
        self._ticker_map: dict[str, str] = (
            dict(ticker_map) if ticker_map is not None else dict(DEFAULT_YAHOO_SYMBOLS)
        )

    async def _fetch(self, key: str) -> tuple[float | None, float | None]:
        """Fetch (close, change_pct) for a ticker-map key; None-safe."""
        symbol = self._ticker_map.get(key)
        if not symbol:
            logger.warning("yahoo ticker map missing key=%s — skipping", key)
            return None, None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _fetch_close_and_change, symbol)

    async def fetch_us_close_snapshot(self) -> MacroSnapshot:
        sp500, sp500_pct = await self._fetch("sp500")
        nasdaq, nasdaq_pct = await self._fetch("nasdaq")
        vix, _ = await self._fetch("vix")
        dxy, _ = await self._fetch("dxy")
        us10y, _ = await self._fetch("us10y")

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

    async def fetch_premarket_snapshot(self) -> MacroSnapshot:
        """Pre-market (07:45 KST) snapshot: ES/NQ futures, SOX, offshore KRW.

        Covers the gap before the ECOS same-day USD/KRW fixing (published
        after 08:30 KST) so the 08:00 pre-open Risk Score has fresh inputs.
        """
        values: dict[str, float | None] = {}
        for key in _PREMARKET_FIELDS:
            close, change_pct = await self._fetch(key)
            values[key] = close
            values[f"{key}_change_pct"] = change_pct

        return MacroSnapshot(
            ts_ms=int(time.time() * 1000),
            session="premarket",
            collected_from=["yahoo"],
            **values,
        )
