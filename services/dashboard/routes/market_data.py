"""Historical OHLCV bars for dashboard price charts (read-only).

Thin HTTP wrapper over ``shared.storage.market_data_store`` (Parquet/DuckDB).
No control/execution endpoints belong here. Degrades gracefully to an empty
series when the Parquet dataset or a symbol is absent, so the dashboard never
500s on missing history.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Query

from services.dashboard.domain.assets import normalize_asset_class

router = APIRouter(prefix="/api/market-data", tags=["market-data"])
logger = logging.getLogger(__name__)

_MAX_DAYS = 400
_BAR_FIELDS = ("open", "high", "low", "close", "volume")


def _serialize_bars(df: Any) -> list[dict[str, Any]]:
    """Convert a bars DataFrame to JSON rows: {t, open, high, low, close, volume}."""
    if df is None or getattr(df, "empty", True):
        return []
    rows: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        dt = record.get("datetime")
        # datetime may be a pandas Timestamp; isoformat() works on both.
        t = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
        row: dict[str, Any] = {"t": t}
        for field in _BAR_FIELDS:
            value = record.get(field)
            row[field] = float(value) if value is not None else None
        rows.append(row)
    return rows


@router.get("/bars")
async def get_market_bars(
    symbol: str = Query(..., min_length=1),
    asset_class: str = Query(default="stock"),
    timeframe: Literal["minute", "daily"] = Query(default="minute"),
    days: int = Query(default=5, ge=1, le=_MAX_DAYS),
) -> dict[str, Any]:
    """Return OHLCV bars for one symbol over the trailing ``days`` window.

    Used by the price-chart-with-markers view; markers themselves come from the
    signals / trades-fills routes and are overlaid client-side by timestamp.
    """
    asset = normalize_asset_class(asset_class)
    # event/context is futures-or-stock; "all" has no single symbol series.
    if asset not in ("stock", "futures"):
        asset = "stock"

    end: date = datetime.now().date()
    start: date = end - timedelta(days=days)
    empty: dict[str, Any] = {
        "status": "empty",
        "symbol": symbol,
        "asset_class": asset,
        "timeframe": timeframe,
        "count": 0,
        "bars": [],
    }

    try:
        from shared.storage.market_data_store import create_market_data_store

        store = create_market_data_store(asset_class=asset)  # type: ignore[arg-type]
        if timeframe == "daily":
            df = store.get_daily_bars(symbol, start=start, end=end)
        else:
            df = store.get_minute_bars(symbol, start=start, end=end)
    except Exception:  # noqa: BLE001 - price history is best-effort read-only
        logger.debug("market-data bars query failed", exc_info=True)
        return empty

    bars = _serialize_bars(df)
    if not bars:
        return empty
    return {
        "status": "ok",
        "symbol": symbol,
        "asset_class": asset,
        "timeframe": timeframe,
        "count": len(bars),
        "bars": bars,
    }
