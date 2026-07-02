"""Pure derived-value computations for the market-structure daily series.

Shared by the forward collector (``main.py``) and the backfill script
(``scripts/backfill_market_structure.py``). All functions are side-effect
free and return ``None`` when inputs are insufficient — derived values are
never fabricated from partial data (roadmap: 결측 허용, 합성값 금지).

Series arguments are ordered oldest → newest and must already include the
"current" observation when the derived value is for the current day.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

# oi_price_signal labels — OI change combined with price direction
# (docs/plans/2026-07-02-unified-investment-system-roadmap.md §4.1: 가격 하락 +
# OI 증가 = 신규 숏 축적 = 위험↑). Consumers map labels to sub-scores in YAML.
SIGNAL_NEW_LONGS = "new_longs"
SIGNAL_NEW_SHORTS = "new_shorts"
SIGNAL_SHORT_COVERING = "short_covering"
SIGNAL_LONG_LIQUIDATION = "long_liquidation"
SIGNAL_NEUTRAL = "neutral"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not (
        isinstance(value, float) and math.isnan(value)
    )


def clean_series(values: Sequence[object]) -> list[float]:
    """Drop None/NaN entries and coerce the rest to float (order preserved)."""
    return [float(v) for v in values if _is_number(v)]


def update_cum_window(
    window: Sequence[Sequence[object]],
    trade_date: date,
    value: float,
    size: int,
) -> list[list[object]]:
    """Insert/replace one (date, value) point and trim to the last ``size`` days.

    ``window`` entries are ``[iso_date, value]`` pairs (the JSON layout of the
    ``market:structure:cum20:foreign_futures`` Redis key). Re-runs for the same
    date replace the existing point, keeping the update idempotent.
    """
    day_iso = trade_date.isoformat()
    merged: dict[str, float] = {}
    for entry in window:
        if len(entry) != 2 or not _is_number(entry[1]):
            continue
        merged[str(entry[0])] = float(entry[1])
    merged[day_iso] = float(value)
    ordered = sorted(merged.items())[-max(int(size), 1) :]
    return [[day, qty] for day, qty in ordered]


def cum_window_sum(window: Sequence[Sequence[object]]) -> float | None:
    """Sum of the window values; ``None`` for an empty window."""
    values = [float(entry[1]) for entry in window if len(entry) == 2]
    if not values:
        return None
    return float(sum(values))


def oi_price_signal(
    price_change_pct: float | None, oi_change: float | None
) -> str | None:
    """Classify the OI-change x price-direction combination.

    Returns one of the ``SIGNAL_*`` labels, or ``None`` when either input is
    missing (never guesses a direction).
    """
    if not _is_number(price_change_pct) or not _is_number(oi_change):
        return None
    if price_change_pct == 0 or oi_change == 0:
        return SIGNAL_NEUTRAL
    if oi_change > 0:
        return SIGNAL_NEW_LONGS if price_change_pct > 0 else SIGNAL_NEW_SHORTS
    return SIGNAL_SHORT_COVERING if price_change_pct > 0 else SIGNAL_LONG_LIQUIDATION


def moving_average(values: Sequence[object], window: int) -> float | None:
    """Trailing mean of the last ``window`` values; ``None`` if underfilled."""
    series = clean_series(values)
    if window <= 0 or len(series) < window:
        return None
    tail = series[-window:]
    return float(sum(tail) / window)


def pct_return(values: Sequence[object], periods: int) -> float | None:
    """Percent return over ``periods`` observations (needs periods+1 points)."""
    series = clean_series(values)
    if periods <= 0 or len(series) < periods + 1:
        return None
    base = series[-(periods + 1)]
    if base == 0:
        return None
    return (series[-1] / base - 1.0) * 100.0


def ma_alignment(mas: Sequence[float | None]) -> str | None:
    """MA 배열 판정 — ``mas`` ordered short → long (e.g. [ma5, ma20, ma60]).

    ``bullish`` when strictly descending window order (정배열), ``bearish``
    when strictly ascending (역배열), otherwise ``mixed``. ``None`` when any
    MA is missing.
    """
    if len(mas) < 2 or any(not _is_number(v) for v in mas):
        return None
    series = [float(v) for v in mas]  # type: ignore[arg-type]
    if all(series[i] > series[i + 1] for i in range(len(series) - 1)):
        return "bullish"
    if all(series[i] < series[i + 1] for i in range(len(series) - 1)):
        return "bearish"
    return "mixed"
