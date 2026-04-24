"""Retroactive macro snapshots via yfinance (spec §8.1).

Phase 1 ran for < 2 weeks, so backtests covering 6+ months of history
cannot rely on the live macro pipeline.  This module pulls S&P 500 +
Nasdaq daily closes from Yahoo Finance and builds one :class:`MacroSnapshot`
per KST trading date, keyed by the KR session date.

Mapping rule: a KR session on date D sees "overnight" close data from the
US session on the prior US trading day (D-1 calendar day most of the time,
D-3 over weekends).  For simplicity we attach the most recent completed US
close whose date is strictly before the KR session date.
"""

from __future__ import annotations

from datetime import date, datetime

from shared.macro.base import MacroSnapshot

_DEFAULT_TICKERS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
}


def _pct_change(prev: float, curr: float) -> float:
    if prev == 0 or prev != prev:  # NaN check
        return 0.0
    return (curr - prev) / prev * 100.0


def fetch_macro_history(
    start: date,
    end: date,
    *,
    tickers: dict[str, str] | None = None,
) -> dict[date, MacroSnapshot]:
    """Fetch daily close history and return ``{session_date: MacroSnapshot}``.

    Parameters
    ----------
    start, end:
        Inclusive date range for KR sessions you want to cover.  The fetch
        extends a few days before ``start`` to guarantee a prior US close
        exists for the first requested session.
    tickers:
        Override for Yahoo tickers.  Default pulls ``^GSPC``, ``^IXIC``,
        ``^VIX``, ``DX-Y.NYB``, ``^TNX``.

    Returns
    -------
    dict[date, MacroSnapshot]
        Keyed by the **KR session date** the snapshot applies to (i.e. the
        date whose overnight window sees the fetched US close).
    """
    import pandas as pd

    try:
        import yfinance as yf  # lazy import — only needed for live backtests
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "yfinance is required for retroactive macro backfill but is not "
            "importable. It IS declared in pyproject.toml; the most likely "
            "cause is that you are running the system Python rather than the "
            "project venv.\n\n"
            "Fix:\n"
            "  source .venv/bin/activate && python scripts/...\n"
            "or run the script via the venv Python directly:\n"
            "  .venv/bin/python scripts/...\n"
            "or pass --skip-macro to bypass macro (Setup A will never fire)."
        ) from exc

    tickers = tickers or _DEFAULT_TICKERS
    # Fetch a cushion of 7 days before start so the first KR session has a prior close.
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=10)).date()
    fetch_end = (pd.Timestamp(end) + pd.Timedelta(days=1)).date()

    raw = yf.download(
        list(tickers.values()),
        start=str(fetch_start),
        end=str(fetch_end),
        progress=False,
        auto_adjust=True,
    )
    if raw.empty:
        return {}

    # yfinance returns a multi-index DataFrame when fetching multiple tickers.
    closes = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw

    # Build a per-date dict of the latest close per ticker-name.
    snapshots: dict[date, MacroSnapshot] = {}
    closes = closes.sort_index()
    dates_available = [idx.date() for idx in closes.index]

    # Walk KR session days. For each KR date D, find the most recent US close
    # strictly before D. If none exists (e.g. fetch_start was too tight),
    # skip this KR date.
    kr_days = pd.date_range(start=str(start), end=str(end), freq="D")
    for kr_ts in kr_days:
        kr_d = kr_ts.date()
        # Most recent US close whose date < kr_d
        prior_us = [d for d in dates_available if d < kr_d]
        if len(prior_us) < 2:
            continue
        us_today = prior_us[-1]
        us_prev = prior_us[-2]

        def _lookup(name: str, d: date) -> float:
            sym = tickers[name]
            try:
                return float(closes.loc[str(d), sym])
            except KeyError:
                return float("nan")

        sp500_close = _lookup("sp500", us_today)
        nasdaq_close = _lookup("nasdaq", us_today)
        vix_close = _lookup("vix", us_today)
        dxy_close = _lookup("dxy", us_today)
        us10y_close = _lookup("us10y", us_today)

        sp500_pct = _pct_change(_lookup("sp500", us_prev), sp500_close)
        nasdaq_pct = _pct_change(_lookup("nasdaq", us_prev), nasdaq_close)

        ts_ms = int(datetime.combine(us_today, datetime.min.time()).timestamp() * 1000)
        snapshots[kr_d] = MacroSnapshot(
            ts_ms=ts_ms,
            session="overnight_us_close",
            sp500_close=sp500_close,
            sp500_change_pct=sp500_pct,
            nasdaq_close=nasdaq_close,
            nasdaq_change_pct=nasdaq_pct,
            vix=vix_close,
            dxy=dxy_close,
            us10y_yield=us10y_close,
            collected_from=["yfinance_history"],
        )

    return snapshots


def make_macro_provider(
    history: dict[date, MacroSnapshot],
):
    """Return a callable ``(date) → MacroSnapshot | None`` for MarketContextReplay."""

    def _provider(d: date) -> MacroSnapshot | None:
        return history.get(d)

    return _provider
